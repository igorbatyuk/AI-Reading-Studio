"""Text-to-speech engine using edge-tts with cache."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import shutil
import threading
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, QUrl, Signal, Slot
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer

from .tts_speed import PLAYBACK_RATES, UI_SPEECH_RATES, edge_rate_string

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _TTSContext:
    voice: str
    tts_mode: str
    online_engine: str
    offline_engine: str
    offline_lang: str


@dataclass(frozen=True)
class TTSEngineInfo:
    mode_label: str
    engine_label: str
    is_slow: bool
    loading_hint: str


class TTSEngine(QObject):
    playback_finished = Signal()
    playback_started = Signal()
    playback_position = Signal(int, int)  # position_ms, duration_ms
    timings_ready = Signal(str)  # block text after Whisper alignment saved
    sample_finished = Signal()
    playback_error = Signal(str)
    generating_changed = Signal(bool)
    activity_changed = Signal()
    provider_skipped = Signal(str)  # cloud provider name when quota blocks it in Auto
    _play_request = Signal(str, bool)  # path, advance_on_finish
    _word_play_request = Signal(str)

    SPEEDS = UI_SPEECH_RATES
    PLAYBACK_RATES = PLAYBACK_RATES
    REWIND_STEP_MS = 5000

    def __init__(self, voice: str = "en-US-AriaNeural") -> None:
        super().__init__()
        self.voice = voice
        self.speed = 1.0
        self._playback_rate = 1.0
        self.tts_mode = "auto"  # online | offline | auto
        self.online_engine = "edge"  # edge | azure | google
        self.offline_lang = "en"
        self.offline_engine = "system"  # system | piper | kokoro | xtts | styletts2
        self.whisper_word_align = "auto"  # off | auto | on
        self.piper_model_path = ""
        self.styletts2_model_path = ""
        self.azure_speech_key = ""
        self.azure_speech_region = ""
        self.google_tts_api_key = ""
        self.elevenlabs_api_key = ""
        self.cartesia_api_key = ""
        self.murf_api_key = ""
        self._azure_tts_usage = None
        self._google_tts_usage = None
        self._elevenlabs_tts_usage = None
        self._cartesia_tts_usage = None
        self._murf_tts_usage = None
        self.word_tts_profile = "same"  # same | custom
        self.word_voice = ""
        self.word_tts_mode = "auto"
        self.word_online_engine = "edge"
        self.word_offline_engine = "system"
        self.app_dir = Path.home() / ".ai_reading_studio"
        self._cache_dir = self.app_dir / "audio"
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._temp_files: list[Path] = []
        self._advance_on_finish = True
        self._current_file: Path | None = None
        self._audio_cache: dict[str, Path] = {}
        self._word_timings_cache: dict[str, tuple[list[tuple[int, int]], bool]] = {}
        self._prefetch_generation = 0
        self._reading_book_id: int | None = None
        self._reading_block_index = -1
        self._prefetch_ahead = 1
        self._book_block_texts: list[str] = []
        self._book_prefetch_generation = 0
        self._book_prefetch_lock = threading.Lock()
        self._bulk_generation_generation = 0
        self._bulk_generation_lock = threading.Lock()
        self._use_saved_audio = True
        self._job_meta: dict[str, dict[str, object]] = {}
        self._word_prefetch_by_sentence: dict[int, int] = {}
        self._generating_tasks = 0
        self._cache_key_prefix = ""
        self._word_cache_key_prefix = ""
        self._refresh_cache_prefixes()
        self._jobs_lock = threading.Lock()
        self._jobs: dict[str, str] = {}
        self._job_errors: dict[str, str] = {}
        self._last_error = ""
        self._active_speak_key = ""
        self._speak_lock = threading.Lock()
        self._playback_active = False
        self._playback_paused = False
        self._held_playback = False
        self._align_scheduled: set[str] = set()
        self._align_lock = threading.Lock()

        self._player = QMediaPlayer()
        self._audio = QAudioOutput()
        self._player.setAudioOutput(self._audio)
        self._player.mediaStatusChanged.connect(self._on_main_media_status)
        self._player.positionChanged.connect(self._emit_playback_position)
        self._player.durationChanged.connect(self._emit_playback_position)

        self._word_player = QMediaPlayer()
        self._word_audio = QAudioOutput()
        self._word_player.setAudioOutput(self._word_audio)
        self._word_player.mediaStatusChanged.connect(self._on_word_media_status)
        self._word_temp_file: Path | None = None
        self._word_preview_pending = False

        self._play_request.connect(self._play_on_main_thread)
        self._word_play_request.connect(self._play_word_on_main)

    def set_voice(self, voice: str) -> None:
        if voice != self.voice:
            self.voice = voice
            self._clear_cache()

    def playback_rate(self) -> float:
        return self._playback_rate

    def set_playback_rate(self, rate: float) -> None:
        from .tts_speed import clamp_playback_rate

        rate = clamp_playback_rate(rate)
        self._playback_rate = rate
        self._player.setPlaybackRate(rate)

    def set_playback_intent(self, *, active: bool, paused: bool) -> None:
        """Mirror reading UI play/pause so audio does not start while paused."""
        self._playback_active = active
        self._playback_paused = paused

    def sync_engine_name(self) -> str:
        """Engine id used for highlight sync offsets (online or offline profile)."""
        ctx = self._main_context()
        if ctx.tts_mode == "online":
            return ctx.online_engine
        if ctx.tts_mode == "offline":
            return ctx.offline_engine
        return ctx.online_engine

    def cycle_playback_rate(self) -> float:
        rates = self.PLAYBACK_RATES
        try:
            idx = rates.index(self._playback_rate)
            next_idx = (idx + 1) % len(rates)
        except ValueError:
            next_idx = 0
        rate = rates[next_idx]
        self.set_playback_rate(rate)
        return rate

    def can_control_playback(self) -> bool:
        return (
            self._current_file is not None
            and self._player.source().isValid()
        )

    def restart_playback(self) -> bool:
        if not self.can_control_playback():
            return False
        self._stop_event.clear()
        self._player.setPosition(0)
        if self._player.playbackState() != QMediaPlayer.PlaybackState.PlayingState:
            self._player.play()
        return True

    def rewind_playback(self, ms: int | None = None) -> bool:
        if not self.can_control_playback():
            return False
        step = self.REWIND_STEP_MS if ms is None else max(0, ms)
        self._player.setPosition(max(0, self._player.position() - step))
        return True

    def set_speed(self, speed: float) -> None:
        from .tts_speed import normalize_speech_rate_to_combo

        speed = normalize_speech_rate_to_combo(speed)
        if speed != self.speed:
            logger.info("TTS speech rate changed: %.2f -> %.2f", self.speed, speed)
            self.speed = speed
            self._release_main_player()
            with self._book_prefetch_lock:
                self._book_prefetch_generation += 1
            with self._bulk_generation_lock:
                self._bulk_generation_generation += 1
            self._clear_cache()

    def set_mode(self, mode: str) -> None:
        if mode in ("online", "offline", "auto") and mode != self.tts_mode:
            self.tts_mode = mode
            self._clear_cache()

    def set_online_engine(self, engine: str) -> None:
        if engine in ("edge", "azure", "google", "elevenlabs", "cartesia", "murf") and engine != self.online_engine:
            self.online_engine = engine
            self._clear_cache()

    def set_offline_language(self, lang: str) -> None:
        self.offline_lang = lang or "en"

    def set_offline_engine(self, engine: str) -> None:
        allowed = ("system", "piper", "kokoro", "xtts", "styletts2")
        if engine in allowed and engine != self.offline_engine:
            self.offline_engine = engine
            self._clear_cache()

    def set_whisper_word_align(self, mode: str) -> None:
        from .whisper_align import normalize_mode

        cleaned = normalize_mode(mode)
        if cleaned != self.whisper_word_align:
            self.whisper_word_align = cleaned

    def set_piper_model_path(self, path: str) -> None:
        if path != self.piper_model_path:
            self.piper_model_path = path or ""
            self._clear_cache()

    def set_styletts2_model_path(self, path: str) -> None:
        if path != self.styletts2_model_path:
            self.styletts2_model_path = path or ""
            self._clear_cache()

    def set_azure_credentials(self, key: str, region: str) -> None:
        key = key or ""
        region = region or ""
        if key != self.azure_speech_key or region != self.azure_speech_region:
            self.azure_speech_key = key
            self.azure_speech_region = region
            self._clear_cache()

    def set_google_tts_api_key(self, key: str) -> None:
        key = key or ""
        if key != self.google_tts_api_key:
            self.google_tts_api_key = key
            self._clear_cache()

    def set_elevenlabs_api_key(self, key: str) -> None:
        key = key or ""
        if key != self.elevenlabs_api_key:
            self.elevenlabs_api_key = key
            self._clear_cache()

    def set_cartesia_api_key(self, key: str) -> None:
        key = key or ""
        if key != self.cartesia_api_key:
            self.cartesia_api_key = key
            self._clear_cache()

    def set_murf_api_key(self, key: str) -> None:
        key = key or ""
        if key != self.murf_api_key:
            self.murf_api_key = key
            self._clear_cache()

    def set_azure_tts_usage(self, tracker) -> None:
        self._azure_tts_usage = tracker

    def set_google_tts_usage(self, tracker) -> None:
        self._google_tts_usage = tracker

    def set_elevenlabs_tts_usage(self, tracker) -> None:
        self._elevenlabs_tts_usage = tracker

    def set_cartesia_tts_usage(self, tracker) -> None:
        self._cartesia_tts_usage = tracker

    def set_murf_tts_usage(self, tracker) -> None:
        self._murf_tts_usage = tracker

    def uses_elevenlabs_online(self) -> bool:
        return self._uses_elevenlabs(self._main_context())

    def _uses_elevenlabs(self, ctx: _TTSContext) -> bool:
        return (
            ctx.tts_mode == "online"
            and ctx.online_engine == "elevenlabs"
            and bool(self.elevenlabs_api_key)
        )

    def _uses_cartesia(self, ctx: _TTSContext) -> bool:
        return (
            ctx.tts_mode == "online"
            and ctx.online_engine == "cartesia"
            and bool(self.cartesia_api_key)
        )

    def _uses_murf(self, ctx: _TTSContext) -> bool:
        return (
            ctx.tts_mode == "online"
            and ctx.online_engine == "murf"
            and bool(self.murf_api_key)
        )

    def should_prefetch_words(self) -> bool:
        """Word prefetch can burn cloud credits — skip for metered online TTS."""
        return not self._uses_metered_online(self._word_context())

    def should_prefetch_blocks(self) -> bool:
        """Prefetch current + next blocks (including metered online APIs)."""
        return True

    def block_prefetch_ahead(self) -> int:
        """How many blocks after current to prefetch ahead."""
        if self._uses_metered_online(self._main_context()):
            return 1
        from .tts_policy import prefetch_ahead_blocks

        ctx = self._main_context()
        return prefetch_ahead_blocks(
            tts_mode=ctx.tts_mode,
            offline_engine=ctx.offline_engine,
        )

    def set_reading_book(self, book_id: int | None) -> None:
        self._reading_book_id = book_id

    def set_use_saved_audio(self, enabled: bool) -> None:
        self._use_saved_audio = bool(enabled)

    def use_saved_audio(self) -> bool:
        return self._use_saved_audio

    def set_reading_focus(
        self,
        block_index: int,
        block_texts: list[str] | None = None,
        *,
        ahead: int | None = None,
    ) -> None:
        """Move reading cursor; cancel queued prefetch for skipped blocks."""
        self._reading_block_index = block_index
        if ahead is not None:
            self._prefetch_ahead = ahead
        if block_texts is not None:
            self._book_block_texts = block_texts
        self._prefetch_generation += 1
        if block_texts:
            with self._jobs_lock:
                for idx, raw in enumerate(block_texts):
                    if idx >= block_index:
                        continue
                    text = raw.strip()
                    if not text:
                        continue
                    key = self._cache_key(text)
                    if self._jobs.get(key) == "queued":
                        self._jobs.pop(key, None)
        self.activity_changed.emit()

    def clear_book_cache(self, book_id: int) -> int:
        """Remove on-disk audio cache for one book."""
        book_dir = self._cache_dir / "books" / str(book_id)
        if not book_dir.is_dir():
            return 0
        removed = sum(
            1
            for path in book_dir.iterdir()
            if path.is_file() and path.suffix in (".mp3", ".wav", ".json")
        )
        shutil.rmtree(book_dir, ignore_errors=True)
        stale = [
            key
            for key, path in self._audio_cache.items()
            if str(book_id) in str(path)
        ]
        for key in stale:
            self._audio_cache.pop(key, None)
            self._word_timings_cache.pop(key, None)
        return removed

    def schedule_book_audio_prefetch(
        self,
        focus_index: int,
        block_texts: list[str],
    ) -> None:
        """Background fill of book audio cache (forward from focus only)."""
        if not block_texts or focus_index < 0:
            return
        with self._book_prefetch_lock:
            self._book_prefetch_generation += 1
            generation = self._book_prefetch_generation
        threading.Thread(
            target=self._book_prefetch_worker,
            args=(focus_index, block_texts, generation),
            daemon=True,
        ).start()

    def schedule_full_book_generation(
        self,
        book_id: int,
        block_texts: list[str],
    ) -> None:
        """Generate audio for every block in the book (book audio menu)."""
        if not block_texts:
            return
        self.set_reading_book(book_id)
        with self._bulk_generation_lock:
            self._bulk_generation_generation += 1
            generation = self._bulk_generation_generation
        threading.Thread(
            target=self._bulk_generation_worker,
            args=(block_texts, generation),
            daemon=True,
        ).start()

    def stop_background_generation(self) -> int:
        """Cancel queued jobs and stop background book/bulk prefetch workers."""
        with self._book_prefetch_lock:
            self._book_prefetch_generation += 1
        with self._bulk_generation_lock:
            self._bulk_generation_generation += 1
        self._prefetch_generation += 1
        return self.cancel_queued_jobs()

    def list_queue_jobs(self) -> list[dict[str, object]]:
        with self._jobs_lock:
            items: list[dict[str, object]] = []
            for key, state in self._jobs.items():
                if state not in ("queued", "generating"):
                    continue
                meta = self._job_meta.get(key, {})
                preview = str(meta.get("text") or key[:12])
                items.append(
                    {
                        "key": key,
                        "state": state,
                        "text": preview,
                        "block_index": meta.get("block_index"),
                        "for_word": bool(meta.get("for_word")),
                        "error": self._job_errors.get(key, ""),
                    }
                )
            items.sort(
                key=lambda item: (
                    0 if item["state"] == "generating" else 1,
                    item.get("block_index") if item.get("block_index") is not None else 10**9,
                )
            )
            return items

    def cancel_queued_jobs(self, keys: list[str] | None = None) -> int:
        cancelled = 0
        with self._jobs_lock:
            target_keys = keys
            if target_keys is None:
                target_keys = [
                    key for key, state in self._jobs.items() if state == "queued"
                ]
            for key in target_keys:
                if self._jobs.get(key) == "queued":
                    self._jobs.pop(key, None)
                    self._job_meta.pop(key, None)
                    self._job_errors.pop(key, None)
                    cancelled += 1
        if cancelled:
            self.activity_changed.emit()
        return cancelled

    def book_audio_overview(
        self,
        block_texts: list[str],
    ) -> dict[str, object]:
        ready = 0
        queued = 0
        generating = 0
        failed = 0
        blocks: list[dict[str, object]] = []
        for index, raw in enumerate(block_texts):
            text = raw.strip()
            if not text:
                continue
            on_disk = self.is_on_disk(text)
            state, error = self.audio_status(text)
            if on_disk:
                ready += 1
                status = "ready"
            elif state in ("queued", "generating", "failed"):
                status = state
                if state == "queued":
                    queued += 1
                elif state == "generating":
                    generating += 1
                else:
                    failed += 1
            else:
                status = "missing"
            blocks.append(
                {
                    "index": index,
                    "text": text,
                    "status": status,
                    "error": error,
                    "on_disk": on_disk,
                }
            )
        total = len(blocks)
        return {
            "total": total,
            "ready": ready,
            "queued": queued,
            "generating": generating,
            "failed": failed,
            "missing": max(0, total - ready - queued - generating - failed),
            "blocks": blocks,
        }

    def _uses_metered_online(self, ctx: _TTSContext) -> bool:
        return (
            self._uses_elevenlabs(ctx)
            or self._uses_cartesia(ctx)
            or self._uses_murf(ctx)
        )

    def describe_main_engine(self) -> TTSEngineInfo:
        return self.describe_context(self._main_context())

    def describe_context(self, ctx: _TTSContext) -> TTSEngineInfo:
        from .i18n import tr

        online_label = tr(f"settings.online_engine.{ctx.online_engine}")
        offline_label = tr(f"settings.offline_engine.{ctx.offline_engine}")

        if ctx.tts_mode == "auto":
            mode_label = tr("settings.tts_mode.auto")
            engine_label = tr(
                "status.panel.tts_engine_auto",
                online=online_label,
                offline=offline_label,
            )
            slow_offline = ctx.offline_engine in ("kokoro", "xtts", "styletts2")
        elif ctx.tts_mode == "online":
            mode_label = tr("settings.tts_mode.online")
            engine_label = online_label
            slow_offline = False
        else:
            mode_label = tr("settings.tts_mode.offline")
            engine_label = offline_label
            slow_offline = ctx.offline_engine in ("kokoro", "xtts", "styletts2")

        is_slow = slow_offline and (
            ctx.tts_mode == "offline"
            or (ctx.tts_mode == "auto" and not self._network_online())
        )
        loading_hint = (
            tr("reading.tts_loading_slow", engine=engine_label)
            if is_slow
            else tr("reading.tts_loading_engine", engine=engine_label)
        )
        return TTSEngineInfo(
            mode_label=mode_label,
            engine_label=engine_label,
            is_slow=is_slow,
            loading_hint=loading_hint,
        )

    @staticmethod
    def _network_online() -> bool:
        from .network_status import is_online

        return is_online()

    def set_word_tts_settings(
        self,
        profile: str,
        voice: str,
        mode: str,
        online_engine: str,
        offline_engine: str,
    ) -> None:
        profile = profile if profile in ("same", "custom") else "same"
        mode = mode if mode in ("online", "offline", "auto") else "auto"
        online_engine = online_engine or "edge"
        offline_engine = offline_engine or "system"
        changed = (
            profile != self.word_tts_profile
            or voice != self.word_voice
            or mode != self.word_tts_mode
            or online_engine != self.word_online_engine
            or offline_engine != self.word_offline_engine
        )
        if not changed:
            return
        self.word_tts_profile = profile
        self.word_voice = voice or ""
        self.word_tts_mode = mode
        self.word_online_engine = online_engine
        self.word_offline_engine = offline_engine
        self._clear_cache()

    def _main_context(self) -> _TTSContext:
        return _TTSContext(
            voice=self.voice,
            tts_mode=self.tts_mode,
            online_engine=self.online_engine,
            offline_engine=self.offline_engine,
            offline_lang=self.offline_lang,
        )

    def _word_context(self) -> _TTSContext:
        if self.word_tts_profile != "custom":
            return self._main_context()
        voice = self.word_voice or self.voice
        return _TTSContext(
            voice=voice,
            tts_mode=self.word_tts_mode,
            online_engine=self.word_online_engine,
            offline_engine=self.word_offline_engine,
            offline_lang=self.offline_lang,
        )

    def set_app_dir(self, app_dir: Path) -> None:
        self.app_dir = app_dir
        self._cache_dir = app_dir / "audio"
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    def _make_cache_prefix(self, ctx: _TTSContext) -> str:
        from .tts_voices import parse_stored_voice

        engine, raw_voice = parse_stored_voice(ctx.voice)
        from .tts_speed import speed_cache_token

        return (
            f"{engine}:{raw_voice}:{speed_cache_token(self.speed)}:{ctx.tts_mode}:"
            f"{ctx.online_engine}:{ctx.offline_lang}:{ctx.offline_engine}:"
            f"{self.piper_model_path}:{self.styletts2_model_path}:"
            f"{self.azure_speech_region}"
        )

    def _refresh_cache_prefixes(self) -> None:
        self._cache_key_prefix = self._make_cache_prefix(self._main_context())
        self._word_cache_key_prefix = self._make_cache_prefix(self._word_context())

    def _cache_key(self, text: str, *, for_word: bool = False) -> str:
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
        prefix = self._word_cache_key_prefix if for_word else self._cache_key_prefix
        return f"{prefix}:{digest}"

    def _cache_digest(self, key: str) -> str:
        return hashlib.sha256(key.encode("utf-8")).hexdigest()[:32]

    def _cache_storage_dir(self, *, for_word: bool = False) -> Path:
        if for_word or self._reading_book_id is None:
            path = self._cache_dir / "shared"
        else:
            path = self._cache_dir / "books" / str(self._reading_book_id)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _find_cached_file(self, key: str, *, for_word: bool = False) -> Path | None:
        digest = self._cache_digest(key)
        dirs: list[Path] = []
        if not for_word and self._reading_book_id is not None:
            dirs.append(self._cache_dir / "books" / str(self._reading_book_id))
        dirs.append(self._cache_dir / "shared")
        dirs.append(self._cache_dir)
        for folder in dirs:
            if not folder.is_dir():
                continue
            for ext in (".mp3", ".wav"):
                path = folder / f"{digest}{ext}"
                if path.exists() and path.stat().st_size > 0:
                    return path
        return None

    def _cache_file_path(self, key: str, suffix: str, *, for_word: bool = False) -> Path:
        return self._cache_storage_dir(for_word=for_word) / (
            f"{self._cache_digest(key)}{suffix}"
        )

    def _is_persistent(self, path: Path) -> bool:
        try:
            path.resolve().relative_to(self._cache_dir.resolve())
            return True
        except ValueError:
            return False

    def _clear_cache(self) -> None:
        self._refresh_cache_prefixes()
        self._audio_cache.clear()
        self._word_timings_cache.clear()
        self._word_prefetch_by_sentence.clear()
        self._prefetch_generation += 1
        with self._jobs_lock:
            self._jobs.clear()
            self._job_errors.clear()
        self.activity_changed.emit()

    def _prepare_speak(self, key: str) -> None:
        """Stop playback and mark the only speak request allowed to start audio."""
        self._active_speak_key = key
        self._stop_event.set()
        self._release_main_player()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=0)
        self._thread = None
        self._stop_event.clear()

    def invalidate_pending_speak(self) -> None:
        """Cancel in-flight speak workers without starting a new block."""
        self._active_speak_key = ""
        self._stop_event.set()

    def reset_memory_cache(self) -> None:
        self._clear_cache()

    def last_error(self) -> str:
        return self._last_error

    def audio_status(self, text: str) -> tuple[str, str]:
        """Return (state, error). state: ready|generating|queued|failed|waiting|none"""
        if not text.strip():
            return "none", ""
        key = self._cache_key(text)
        if self.is_cached(text):
            return "ready", ""
        with self._jobs_lock:
            error = self._job_errors.get(key, "")
            state = self._jobs.get(key, "")
        if state == "failed" or error:
            return "failed", error
        if state == "generating":
            return "generating", ""
        if state == "queued":
            return "queued", ""
        return "waiting", ""

    def _set_job(
        self,
        key: str,
        state: str | None,
        error: str = "",
        *,
        text: str = "",
        block_index: int | None = None,
        for_word: bool = False,
    ) -> None:
        with self._jobs_lock:
            if state is None:
                self._jobs.pop(key, None)
                if not error:
                    self._job_errors.pop(key, None)
                if not error and state is None:
                    self._job_meta.pop(key, None)
            else:
                self._jobs[key] = state
                if text or block_index is not None or for_word:
                    meta = self._job_meta.setdefault(key, {})
                    if text:
                        meta["text"] = text[:120]
                    if block_index is not None:
                        meta["block_index"] = block_index
                    if for_word:
                        meta["for_word"] = True
            if error:
                self._job_errors[key] = error
            elif state != "failed":
                self._job_errors.pop(key, None)
        self.activity_changed.emit()

    def _finish_job(self, key: str) -> None:
        self._set_job(key, None)

    def is_on_disk(self, text: str, *, for_word: bool = False) -> bool:
        key = self._cache_key(text, for_word=for_word)
        cached = self._audio_cache.get(key) or self._find_cached_file(
            key, for_word=for_word
        )
        return bool(cached and cached.exists())

    def is_cached(self, text: str, *, for_word: bool = False) -> bool:
        if not for_word and not self._use_saved_audio:
            return False
        return self.is_on_disk(text, for_word=for_word)

    def _cache_hit(self, text: str, *, for_word: bool = False) -> Path | None:
        if not for_word and not self._use_saved_audio:
            return None
        key = self._cache_key(text, for_word=for_word)
        cached = self._audio_cache.get(key) or self._find_cached_file(
            key, for_word=for_word
        )
        if cached and cached.exists():
            return cached
        return None

    def word_timings_for(self, text: str) -> list[tuple[int, int]] | None:
        """Per-word (start_ms, end_ms) boundaries when available."""
        info = self.word_timings_info_for(text)
        return info.timings if info else None

    def timings_bundle_for(self, text: str):
        """Load cached word timings without triggering alignment."""
        from .word_highlight import WordTimingsBundle

        if not text.strip():
            return None
        loaded = self._load_word_timings(self._cache_key(text))
        if not loaded:
            return None
        timings, estimated = loaded
        return WordTimingsBundle(timings, estimated)

    def word_timings_info_for(self, text: str):
        """Word timings plus whether they are estimated (offline) or exact (Edge)."""
        from .media_duration import media_duration_ms
        from .word_highlight import WordTimingsBundle, estimate_word_timings_from_text

        if not text.strip():
            return None
        key = self._cache_key(text)
        loaded = self._load_word_timings(key)
        if loaded:
            timings, estimated = loaded
            return WordTimingsBundle(timings, estimated)
        cached = self._find_cached_file(key, for_word=False)
        if cached:
            self._schedule_timings_alignment(text, key, cached)
            duration_ms = media_duration_ms(cached)
            if duration_ms > 0:
                return WordTimingsBundle(
                    estimate_word_timings_from_text(text, duration_ms),
                    True,
                )
        return None

    def _timings_path(self, key: str, *, for_word: bool = False) -> Path:
        cached = self._find_cached_file(key, for_word=for_word)
        if cached:
            return cached.with_suffix(".timings.json")
        return self._cache_file_path(key, ".timings.json", for_word=for_word)

    def _load_word_timings(self, key: str) -> tuple[list[tuple[int, int]], bool] | None:
        if key in self._word_timings_cache:
            return self._word_timings_cache[key]
        path = self._timings_path(key)
        if not path.exists():
            return None
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                items = raw.get("words") or raw.get("timings") or []
                estimated = bool(raw.get("estimated", False))
            elif isinstance(raw, list):
                items = raw
                estimated = True
            else:
                return None
            timings = [(int(item[0]), int(item[1])) for item in items]
            if timings:
                payload = (timings, estimated)
                self._word_timings_cache[key] = payload
                return payload
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
            logger.debug("Failed to load word timings for %s: %s", key, exc)
        return None

    def _save_word_timings(
        self,
        key: str,
        timings: list[tuple[int, int]],
        *,
        estimated: bool = False,
    ) -> None:
        if not timings:
            return
        path = self._timings_path(key)
        path.write_text(
            json.dumps(
                {
                    "estimated": estimated,
                    "words": [[start, end] for start, end in timings],
                }
            ),
            encoding="utf-8",
        )
        self._word_timings_cache[key] = (timings, estimated)

    def is_generating(self) -> bool:
        return self._generating_tasks > 0

    def active_tasks(self) -> int:
        return self._generating_tasks

    def cache_stats(self) -> dict[str, int]:
        disk = 0
        if self._cache_dir.exists():
            for path in self._cache_dir.rglob("*"):
                if path.is_file() and path.suffix in (".mp3", ".wav"):
                    if path.stat().st_size > 0:
                        disk += 1
        return {"memory": len(self._audio_cache), "disk": disk}

    def _generating_begin(self) -> None:
        self._generating_tasks += 1
        if self._generating_tasks == 1:
            self.generating_changed.emit(True)

    def _generating_end(self) -> None:
        self._generating_tasks = max(0, self._generating_tasks - 1)
        if self._generating_tasks == 0:
            self.generating_changed.emit(False)

    def speak(self, text: str, *, advance: bool = True) -> None:
        self._advance_on_finish = advance
        key = self._cache_key(text)
        self._prepare_speak(key)
        cached = self._cache_hit(text, for_word=False)
        if cached:
            if key != self._active_speak_key:
                return
            self._audio_cache[key] = cached
            if not self._load_word_timings(key):
                self._schedule_timings_alignment(text, key, cached)
            self._deliver_playback(str(cached), advance, key)
            return
        self._start_speak_worker(text, key)

    def _deliver_playback(self, path: str, advance: bool, speak_key: str) -> None:
        with self._speak_lock:
            if self._stop_event.is_set():
                return
            if not speak_key or speak_key != self._active_speak_key:
                return
        self.playback_started.emit()
        self._play_request.emit(path, advance)

    def preview(self, text: str) -> None:
        """Play a short voice sample (e.g. in settings)."""
        self.set_playback_intent(active=True, paused=False)
        self._held_playback = False
        self.speak(text, advance=False)

    def preview_word(self, text: str) -> None:
        """Play a short sample with the word TTS profile."""
        word = text.strip()
        if not word:
            return
        self.set_playback_intent(active=True, paused=False)
        self._word_preview_pending = True
        self.speak_word(word)

    def speak_word(self, word: str) -> None:
        word = word.strip()
        if not word:
            return
        key = self._cache_key(word, for_word=True)
        cached = self._audio_cache.get(key) or self._find_cached_file(
            key, for_word=True
        )
        if cached and cached.exists():
            self._audio_cache[key] = cached
            self._word_play_request.emit(str(cached))
            return
        with self._jobs_lock:
            if self._jobs.get(key) in ("queued", "generating"):
                return
        threading.Thread(
            target=self._word_speak_worker, args=(word,), daemon=True
        ).start()

    def prefetch_words(self, sentence: str, max_words: int = 25) -> None:
        from .translation_service import extract_lookup_words

        sentence = sentence.strip()
        if not sentence:
            return
        words = extract_lookup_words(sentence)[:max_words]
        if not words:
            return
        sentence_id = hash(sentence)
        generation = self._word_prefetch_by_sentence.get(sentence_id, 0) + 1
        self._word_prefetch_by_sentence[sentence_id] = generation
        threading.Thread(
            target=self._prefetch_words_worker,
            args=(sentence, words, sentence_id, generation),
            daemon=True,
        ).start()

    def _prefetch_words_worker(
        self, sentence: str, words: list[str], sentence_id: int, generation: int
    ) -> None:
        for word in words:
            if self._word_prefetch_by_sentence.get(sentence_id) != generation:
                return
            if self.is_cached(word, for_word=True):
                continue
            key = self._cache_key(word, for_word=True)
            with self._jobs_lock:
                if self._jobs.get(key) in ("queued", "generating"):
                    continue
            self.prefetch(word, for_word=True)

    def prefetch(
        self,
        text: str,
        *,
        for_word: bool = False,
        block_index: int | None = None,
        force: bool = False,
    ) -> None:
        if not for_word and not force and block_index is not None:
            if block_index < self._reading_block_index:
                return
        key = self._cache_key(text, for_word=for_word)
        cached = self._cache_hit(text, for_word=for_word)
        if cached:
            self._audio_cache[key] = cached
            self._finish_job(key)
            return
        with self._jobs_lock:
            if self._jobs.get(key) in ("queued", "generating"):
                return
        self._set_job(
            key,
            "queued",
            text=text,
            block_index=block_index,
            for_word=for_word,
        )
        generation = self._prefetch_generation
        threading.Thread(
            target=self._prefetch_worker,
            args=(text, key, for_word, generation, block_index),
            daemon=True,
        ).start()

    def stop(self, emit_finished: bool = False) -> None:
        self._active_speak_key = ""
        self._held_playback = False
        self._stop_event.set()
        self._release_main_player()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=0)
        self._thread = None
        if emit_finished:
            self.playback_finished.emit()

    def pause(self) -> bool:
        """Pause at current position without tearing down the player."""
        state = self._player.playbackState()
        if (
            state == QMediaPlayer.PlaybackState.PlayingState
            and self._current_file is not None
        ):
            self._player.pause()
            return True
        if self._held_playback and self._current_file is not None:
            return True
        return False

    def resume(self) -> bool:
        """Continue paused playback from the same position."""
        if self._current_file is None:
            return False
        state = self._player.playbackState()
        if state == QMediaPlayer.PlaybackState.PausedState:
            self._stop_event.clear()
            self._held_playback = False
            self._player.setPlaybackRate(self._playback_rate)
            self._player.play()
            return True
        if self._held_playback and self._player.source().isValid():
            self._stop_event.clear()
            self._held_playback = False
            self._player.setPlaybackRate(self._playback_rate)
            self._player.play()
            return True
        return False

    def can_resume(self) -> bool:
        if self._current_file is None:
            return False
        state = self._player.playbackState()
        if state == QMediaPlayer.PlaybackState.PausedState:
            return True
        return self._held_playback and self._player.source().isValid()

    def playback_duration_ms(self) -> int:
        duration = self._player.duration()
        return duration if duration > 0 else 0

    def playback_position_ms(self) -> int:
        return max(0, self._player.position())

    def _release_main_player(self) -> None:
        self._player.stop()
        current = self._current_file
        self._player.setSource(QUrl())
        self._current_file = None
        if current and not self._is_persistent(current):
            self._schedule_cleanup(current)

    def _start_speak_worker(self, text: str, key: str) -> None:
        self._set_job(key, "queued", text=text)
        self._thread = threading.Thread(
            target=self._speak_worker, args=(text, key), daemon=True
        )
        self._thread.start()

    def _generate_audio(
        self,
        text: str,
        key: str,
        ctx: _TTSContext,
        *,
        for_word: bool = False,
    ) -> Path:
        existing = None
        if for_word or self._use_saved_audio:
            existing = self._find_cached_file(key, for_word=for_word)
        if existing:
            self._ensure_timings_for_audio(text, key, existing)
            return existing

        self._generating_begin()
        try:
            if ctx.tts_mode == "offline":
                path = self._generate_offline(text, key, ctx, for_word=for_word)
            elif ctx.tts_mode == "online":
                path = self._generate_online(text, key, ctx, for_word=for_word)
            else:
                path = self._generate_auto(text, key, ctx, for_word=for_word)
            return self._finalize_generated_audio(text, key, path)
        finally:
            self._generating_end()

    def _generate_online(
        self,
        text: str,
        key: str,
        ctx: _TTSContext,
        *,
        for_word: bool = False,
    ) -> Path:
        engine = ctx.online_engine or "edge"
        if engine == "azure":
            return self._generate_azure(text, key, ctx, for_word=for_word)
        if engine == "google":
            return self._generate_google(text, key, ctx, for_word=for_word)
        if engine == "elevenlabs":
            return self._generate_elevenlabs(text, key, ctx, for_word=for_word)
        if engine == "cartesia":
            return self._generate_cartesia(text, key, ctx, for_word=for_word)
        if engine == "murf":
            return self._generate_murf(text, key, ctx, for_word=for_word)
        return self._generate_edge(text, key, ctx, for_word=for_word)

    def _generate_auto(
        self,
        text: str,
        key: str,
        ctx: _TTSContext,
        *,
        for_word: bool = False,
    ) -> Path:
        errors: list[str] = []
        for provider_name, generator in self._auto_generators(ctx, for_word=for_word):
            try:
                return generator(text, key)
            except Exception as exc:
                msg = str(exc)
                logger.warning(
                    "%s failed, trying next TTS engine: %s", provider_name, exc
                )
                errors.append(msg)
                if self._is_quota_exhausted_error(msg):
                    self.provider_skipped.emit(provider_name)
        raise RuntimeError(
            errors[-1] if errors else "All TTS engines failed"
        )

    @staticmethod
    def _is_quota_exhausted_error(message: str) -> bool:
        lower = message.lower()
        return (
            "monthly limit reached" in lower
            or "limit exhausted" in lower
            or "character limit" in lower
        )

    def _auto_generators(self, ctx: _TTSContext, *, for_word: bool = False):
        fw = for_word
        chain: list[tuple[str, object]] = [
            ("Edge", lambda t, k: self._generate_edge(t, k, ctx, for_word=fw))
        ]
        if self.azure_speech_key and self.azure_speech_region:
            chain.append(
                (
                    "Azure Speech",
                    lambda t, k: self._generate_azure(t, k, ctx, for_word=fw),
                )
            )
        if self.google_tts_api_key:
            chain.append(
                (
                    "Google Cloud",
                    lambda t, k: self._generate_google(t, k, ctx, for_word=fw),
                )
            )
        if self.elevenlabs_api_key:
            chain.append(
                (
                    "ElevenLabs",
                    lambda t, k: self._generate_elevenlabs(t, k, ctx, for_word=fw),
                )
            )
        if self.cartesia_api_key:
            chain.append(
                (
                    "Cartesia",
                    lambda t, k: self._generate_cartesia(t, k, ctx, for_word=fw),
                )
            )
        if self.murf_api_key:
            chain.append(
                ("Murf", lambda t, k: self._generate_murf(t, k, ctx, for_word=fw))
            )
        chain.append(
            ("Offline", lambda t, k: self._generate_offline(t, k, ctx, for_word=fw))
        )
        return chain

    _CREDIT_PROVIDERS = frozenset({"ElevenLabs", "Cartesia"})

    def _check_cloud_usage(self, tracker, text: str, provider: str) -> None:
        if tracker is None:
            return
        if hasattr(tracker, "can_spend") and not tracker.can_spend(len(text)):
            stats = tracker.status()
            unit = "credits" if provider in self._CREDIT_PROVIDERS else "characters"
            raise RuntimeError(
                f"{provider} TTS monthly limit reached "
                f"({stats['used']:,}/{stats['limit']:,} {unit})"
            )
        stats = tracker.status()
        needed = len(text)
        if stats["remaining"] < needed:
            unit = "credits" if provider in self._CREDIT_PROVIDERS else "characters"
            raise RuntimeError(
                f"{provider} TTS monthly limit reached "
                f"({stats['used']:,}/{stats['limit']:,} {unit})"
            )

    def _record_cloud_usage(self, tracker, text: str) -> None:
        if tracker is not None:
            tracker.record(len(text))

    def _generate_edge(
        self, text: str, key: str, ctx: _TTSContext, *, for_word: bool = False
    ) -> Path:
        import edge_tts

        from .tts_voices import parse_stored_voice

        _engine, edge_voice = parse_stored_voice(ctx.voice)
        if _engine != "edge":
            edge_voice = "en-US-AriaNeural"
        out_path = self._cache_file_path(key, ".mp3", for_word=for_word)
        rate = edge_rate_string(self.speed)
        communicate = edge_tts.Communicate(text, edge_voice, rate=rate)

        async def _stream_to_file() -> list[tuple[int, int]]:
            from .word_highlight import derive_word_timings_from_sentences

            sentence_bounds: list[tuple[int, int, str]] = []
            word_timings: list[tuple[int, int]] = []
            audio = bytearray()
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio.extend(chunk["data"])
                elif chunk["type"] == "WordBoundary":
                    start_ms = int(chunk["offset"] // 10_000)
                    end_ms = start_ms + int(chunk["duration"] // 10_000)
                    word_timings.append((start_ms, end_ms))
                elif chunk["type"] == "SentenceBoundary":
                    start_ms = int(chunk["offset"] // 10_000)
                    end_ms = start_ms + int(chunk["duration"] // 10_000)
                    sentence_bounds.append((start_ms, end_ms, chunk.get("text", "")))
            out_path.write_bytes(audio)
            if word_timings:
                return word_timings
            if sentence_bounds:
                return derive_word_timings_from_sentences(sentence_bounds)
            return []

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            timings = loop.run_until_complete(_stream_to_file())
        finally:
            loop.close()

        self._save_word_timings(key, timings, estimated=False)
        return out_path

    def _ensure_timings_for_audio(self, text: str, key: str, path: Path) -> None:
        if not text.strip() or self._load_word_timings(key):
            return
        from . import whisper_align
        from .media_duration import media_duration_ms
        from .word_highlight import estimate_word_timings_from_text

        aligned = whisper_align.try_align_words(
            text,
            path,
            lang=self.offline_lang,
            mode=self.whisper_word_align,
        )
        if aligned:
            self._save_word_timings(key, aligned, estimated=False)
            return

        duration_ms = media_duration_ms(path)
        if duration_ms <= 0:
            return
        timings = estimate_word_timings_from_text(text, duration_ms)
        self._save_word_timings(key, timings, estimated=True)

    def _schedule_timings_alignment(self, text: str, key: str, path: Path) -> None:
        from . import whisper_align

        if whisper_align.normalize_mode(self.whisper_word_align) == "off":
            return
        if not whisper_align.is_worker_available():
            return
        with self._align_lock:
            if key in self._align_scheduled or self._load_word_timings(key):
                return
            self._align_scheduled.add(key)
        threading.Thread(
            target=self._align_timings_worker,
            args=(text, key, path),
            daemon=True,
        ).start()

    def _align_timings_worker(self, text: str, key: str, path: Path) -> None:
        try:
            self._ensure_timings_for_audio(text, key, path)
        finally:
            with self._align_lock:
                self._align_scheduled.discard(key)
        if self._load_word_timings(key):
            self.timings_ready.emit(text)

    def _finalize_generated_audio(self, text: str, key: str, path: Path) -> Path:
        self._ensure_timings_for_audio(text, key, path)
        return path

    def _generate_azure(
        self, text: str, key: str, ctx: _TTSContext, *, for_word: bool = False
    ) -> Path:
        from . import azure_tts
        from .tts_voices import parse_stored_voice

        self._check_cloud_usage(self._azure_tts_usage, text, "Azure Speech")
        _engine, raw_voice = parse_stored_voice(ctx.voice)
        if _engine != "azure":
            raw_voice = azure_tts.default_voice_for_language(ctx.offline_lang)
        out_path = self._cache_file_path(key, ".mp3", for_word=for_word)
        audio = azure_tts.synthesize_mp3(
            text,
            voice=raw_voice,
            lang=ctx.offline_lang,
            api_key=self.azure_speech_key,
            region=self.azure_speech_region,
            speed=self.speed,
        )
        out_path.write_bytes(audio)
        self._record_cloud_usage(self._azure_tts_usage, text)
        return out_path

    def _generate_google(
        self, text: str, key: str, ctx: _TTSContext, *, for_word: bool = False
    ) -> Path:
        from . import google_cloud_tts
        from .tts_voices import parse_stored_voice

        self._check_cloud_usage(self._google_tts_usage, text, "Google Cloud")
        _engine, raw_voice = parse_stored_voice(ctx.voice)
        if _engine != "google":
            raw_voice = google_cloud_tts.default_voice_for_language(ctx.offline_lang)
        out_path = self._cache_file_path(key, ".mp3", for_word=for_word)
        audio = google_cloud_tts.synthesize_mp3(
            text,
            voice=raw_voice,
            lang=ctx.offline_lang,
            api_key=self.google_tts_api_key,
            speed=self.speed,
        )
        out_path.write_bytes(audio)
        self._record_cloud_usage(self._google_tts_usage, text)
        return out_path

    def _generate_elevenlabs(
        self, text: str, key: str, ctx: _TTSContext, *, for_word: bool = False
    ) -> Path:
        from . import elevenlabs_tts
        from .tts_voices import parse_stored_voice

        self._check_cloud_usage(self._elevenlabs_tts_usage, text, "ElevenLabs")
        _engine, raw_voice = parse_stored_voice(ctx.voice)
        if _engine != "elevenlabs":
            raw_voice = elevenlabs_tts.default_voice_for_language(ctx.offline_lang)
        raw_voice = elevenlabs_tts.resolve_voice_id(
            raw_voice, self.elevenlabs_api_key
        )
        out_path = self._cache_file_path(key, ".mp3", for_word=for_word)
        audio = elevenlabs_tts.synthesize_mp3(
            text,
            voice=raw_voice,
            lang=ctx.offline_lang,
            api_key=self.elevenlabs_api_key,
            speed=self.speed,
        )
        out_path.write_bytes(audio)
        self._record_cloud_usage(self._elevenlabs_tts_usage, text)
        return out_path

    def _generate_cartesia(
        self, text: str, key: str, ctx: _TTSContext, *, for_word: bool = False
    ) -> Path:
        from . import cartesia_tts
        from .tts_voices import parse_stored_voice

        self._check_cloud_usage(self._cartesia_tts_usage, text, "Cartesia")
        _engine, raw_voice = parse_stored_voice(ctx.voice)
        if _engine != "cartesia":
            raw_voice = cartesia_tts.default_voice_for_language(ctx.offline_lang)
        raw_voice = cartesia_tts.resolve_voice_id(
            raw_voice, self.cartesia_api_key
        )
        out_path = self._cache_file_path(key, ".mp3", for_word=for_word)
        audio = cartesia_tts.synthesize_mp3(
            text,
            voice=raw_voice,
            lang=ctx.offline_lang,
            api_key=self.cartesia_api_key,
            speed=self.speed,
        )
        out_path.write_bytes(audio)
        self._record_cloud_usage(self._cartesia_tts_usage, text)
        return out_path

    def _generate_murf(
        self, text: str, key: str, ctx: _TTSContext, *, for_word: bool = False
    ) -> Path:
        from . import murf_tts
        from .tts_voices import parse_stored_voice

        self._check_cloud_usage(self._murf_tts_usage, text, "Murf")
        _engine, raw_voice = parse_stored_voice(ctx.voice)
        if _engine != "murf":
            raw_voice = murf_tts.default_voice_for_language(ctx.offline_lang)
        raw_voice = murf_tts.resolve_voice_id(raw_voice, self.murf_api_key)
        out_path = self._cache_file_path(key, ".mp3", for_word=for_word)
        audio, usage, word_timings = murf_tts.synthesize_mp3(
            text,
            voice=raw_voice,
            lang=ctx.offline_lang,
            api_key=self.murf_api_key,
            speed=self.speed,
        )
        out_path.write_bytes(audio)
        if word_timings:
            self._save_word_timings(key, word_timings, estimated=False)
        if self._murf_tts_usage is not None and usage:
            if hasattr(self._murf_tts_usage, "sync_from_response"):
                self._murf_tts_usage.sync_from_response(
                    consumed=int(usage.get("consumed", 0)),
                    remaining=int(usage.get("remaining", 0)),
                )
            else:
                self._murf_tts_usage.record(len(text))
        elif self._murf_tts_usage is not None:
            self._murf_tts_usage.record(len(text))
        return out_path

    def _generate_offline(
        self, text: str, key: str, ctx: _TTSContext, *, for_word: bool = False
    ) -> Path:
        from .tts_voices import parse_stored_voice

        engine, raw_voice = parse_stored_voice(ctx.voice)
        active = ctx.offline_engine

        if active == "styletts2":
            return self._generate_styletts2(
                text,
                key,
                raw_voice if engine == "styletts2" else None,
                for_word=for_word,
            )
        if active == "xtts":
            return self._generate_xtts(
                text,
                key,
                raw_voice if engine == "xtts" else None,
                for_word=for_word,
            )
        if active == "kokoro":
            return self._generate_kokoro(
                text,
                key,
                raw_voice if engine == "kokoro" else None,
                for_word=for_word,
            )
        if active == "piper":
            return self._generate_piper(
                text,
                key,
                raw_voice if engine == "piper" else None,
                for_word=for_word,
            )

        from . import offline_tts

        if not offline_tts.is_available():
            raise RuntimeError(
                "Offline TTS unavailable. Install pyttsx3 or configure Piper/Kokoro/XTTS/StyleTTS2."
            )
        out_path = self._cache_file_path(key, ".wav", for_word=for_word)
        return offline_tts.generate_wav(
            text, ctx.offline_lang, self.speed, out_path=out_path
        )

    def _generate_kokoro(
        self,
        text: str,
        key: str,
        voice: str | None = None,
        *,
        for_word: bool = False,
    ) -> Path:
        from . import kokoro_tts

        if not kokoro_tts.is_available(self.app_dir):
            raise RuntimeError("Kokoro not configured")
        out_path = self._cache_file_path(key, ".wav", for_word=for_word)
        return kokoro_tts.generate_wav(
            text,
            voice or kokoro_tts.DEFAULT_KOKORO_VOICE,
            self.offline_lang,
            self.app_dir,
            self.speed,
            out_path=out_path,
        )

    def _generate_piper(
        self,
        text: str,
        key: str,
        voice: str | None = None,
        *,
        for_word: bool = False,
    ) -> Path:
        from . import piper_tts

        if not piper_tts.is_available(
            self.offline_lang, self.piper_model_path, self.app_dir
        ):
            raise RuntimeError("Piper not configured")
        out_path = self._cache_file_path(key, ".wav", for_word=for_word)
        return piper_tts.generate_wav(
            text,
            self.offline_lang,
            self.piper_model_path,
            self.app_dir,
            self.speed,
            out_path=out_path,
            voice=voice or "",
        )

    def _generate_xtts(
        self,
        text: str,
        key: str,
        voice: str | None = None,
        *,
        for_word: bool = False,
    ) -> Path:
        from . import xtts_tts

        if not xtts_tts.is_available(self.app_dir):
            raise RuntimeError("XTTS not configured")
        out_path = self._cache_file_path(key, ".wav", for_word=for_word)
        return xtts_tts.generate_wav(
            text,
            voice or xtts_tts.DEFAULT_SPEAKER,
            self.offline_lang,
            self.app_dir,
            self.speed,
            out_path=out_path,
        )

    def _generate_styletts2(
        self,
        text: str,
        key: str,
        voice: str | None = None,
        *,
        for_word: bool = False,
    ) -> Path:
        from . import styletts2_tts

        if not styletts2_tts.is_available(self.app_dir, self.styletts2_model_path):
            raise RuntimeError("StyleTTS2 not configured")
        out_path = self._cache_file_path(key, ".wav", for_word=for_word)
        return styletts2_tts.generate_wav(
            text,
            voice or styletts2_tts.DEFAULT_MODEL,
            self.offline_lang,
            self.app_dir,
            self.styletts2_model_path,
            self.speed,
            out_path=out_path,
        )

    def _speak_worker(self, text: str, speak_key: str) -> None:
        tmp_path: Path | None = None
        ctx = self._main_context()
        key = self._cache_key(text)
        self._set_job(key, "generating", text=text)
        try:
            tmp_path = self._generate_audio(text, key, ctx, for_word=False)
            if self._stop_event.is_set() or speak_key != self._active_speak_key:
                if tmp_path and not self._is_persistent(tmp_path):
                    self._schedule_cleanup(tmp_path)
                self._set_job(key, None)
                return

            self._audio_cache[key] = tmp_path
            self._finish_job(key)
            self._deliver_playback(str(tmp_path), self._advance_on_finish, speak_key)
        except Exception as exc:
            if tmp_path and not self._is_persistent(tmp_path):
                self._schedule_cleanup(tmp_path)
            if speak_key != self._active_speak_key:
                self._set_job(key, None)
                return
            if not self._stop_event.is_set():
                self._last_error = str(exc)
                self._set_job(key, "failed", str(exc))
                self.playback_error.emit(str(exc))
            else:
                self._set_job(key, None)

    def _prefetch_worker(
        self,
        text: str,
        key: str,
        for_word: bool,
        generation: int,
        block_index: int | None,
    ) -> None:
        if not for_word:
            if generation != self._prefetch_generation:
                self._set_job(key, None)
                return
            if block_index is not None and block_index < self._reading_block_index:
                self._set_job(key, None)
                return
        if key in self._audio_cache and self._audio_cache[key].exists():
            self._finish_job(key)
            return
        cached = self._cache_hit(text, for_word=for_word)
        if cached:
            self._audio_cache[key] = cached
            self._finish_job(key)
            self.activity_changed.emit()
            return
        self._set_job(
            key,
            "generating",
            text=text,
            block_index=block_index,
            for_word=for_word,
        )
        ctx = self._word_context() if for_word else self._main_context()
        try:
            path = self._generate_audio(text, key, ctx, for_word=for_word)
            if not for_word and (
                generation != self._prefetch_generation
                or (
                    block_index is not None
                    and block_index < self._reading_block_index
                )
            ):
                self._audio_cache[key] = path
                self._set_job(key, None)
                return
            self._audio_cache[key] = path
            self._finish_job(key)
        except Exception as exc:
            logger.warning("TTS prefetch failed: %s", exc)
            self._last_error = str(exc)
            self._set_job(key, "failed", str(exc))

    def _book_prefetch_worker(
        self,
        focus_index: int,
        block_texts: list[str],
        generation: int,
    ) -> None:
        """Sequentially cache all blocks from focus forward (no backlog behind cursor)."""
        ahead = self.block_prefetch_ahead()
        priority: list[int] = []
        for offset in range(0, ahead + 1):
            idx = focus_index + offset
            if idx < len(block_texts):
                priority.append(idx)
        for idx in range(focus_index, len(block_texts)):
            if idx not in priority:
                priority.append(idx)

        for index in priority:
            if generation != self._book_prefetch_generation:
                return
            if index < self._reading_block_index:
                continue
            text = block_texts[index].strip()
            if not text:
                continue
            if self.is_cached(text):
                continue
            key = self._cache_key(text)
            with self._jobs_lock:
                state = self._jobs.get(key, "")
            if state == "generating":
                continue
            self.prefetch(text, block_index=index)
            # One block at a time in this worker — wait until job finishes or fails.
            for _ in range(600):
                if generation != self._book_prefetch_generation:
                    return
                if index < self._reading_block_index:
                    break
                with self._jobs_lock:
                    state = self._jobs.get(key, "")
                if state in ("", "failed") or self.is_cached(text):
                    break
                threading.Event().wait(0.5)

    def _bulk_generation_worker(
        self,
        block_texts: list[str],
        generation: int,
    ) -> None:
        """Generate audio for every block (book audio menu)."""
        for index, raw in enumerate(block_texts):
            if generation != self._bulk_generation_generation:
                return
            text = raw.strip()
            if not text:
                continue
            if self.is_on_disk(text):
                continue
            key = self._cache_key(text)
            with self._jobs_lock:
                state = self._jobs.get(key, "")
            if state == "generating":
                continue
            self.prefetch(text, block_index=index, force=True)
            for _ in range(600):
                if generation != self._bulk_generation_generation:
                    return
                with self._jobs_lock:
                    state = self._jobs.get(key, "")
                if state in ("", "failed") or self.is_on_disk(text):
                    break
                threading.Event().wait(0.5)

    def _word_speak_worker(self, word: str) -> None:
        tmp_path: Path | None = None
        ctx = self._word_context()
        key = self._cache_key(word, for_word=True)
        try:
            cached = self._audio_cache.get(key) or self._find_cached_file(
                key, for_word=True
            )
            if cached and cached.exists():
                self._audio_cache[key] = cached
                self._word_play_request.emit(str(cached))
                return
            self._set_job(key, "generating")
            tmp_path = self._generate_audio(word, key, ctx, for_word=True)
            if tmp_path:
                self._audio_cache[key] = tmp_path
                self._finish_job(key)
                self._word_play_request.emit(str(tmp_path))
        except Exception as exc:
            logger.warning("Word TTS failed: %s", exc)
            self._set_job(key, "failed", str(exc))
            if tmp_path and not self._is_persistent(tmp_path):
                self._schedule_cleanup(tmp_path)

    @Slot(str)
    def _play_word_on_main(self, path: str) -> None:
        file_path = Path(path)
        if not file_path.exists():
            return
        if self._word_temp_file and not self._is_persistent(self._word_temp_file):
            self._schedule_cleanup(self._word_temp_file)
        self._word_temp_file = file_path
        self._word_player.setSource(QUrl.fromLocalFile(path))
        self._word_player.play()

    @Slot(str, bool)
    def _play_on_main_thread(self, path: str, advance: bool) -> None:
        file_path = Path(path)
        self._advance_on_finish = advance
        speak_key = self._active_speak_key
        if self._stop_event.is_set() or not speak_key:
            if not self._is_persistent(file_path):
                self._schedule_cleanup(file_path)
            return
        self._current_file = file_path
        self._player.setSource(QUrl.fromLocalFile(path))
        self._player.setPlaybackRate(self._playback_rate)
        if self._playback_paused or not self._playback_active:
            self._held_playback = True
            return
        self._held_playback = False
        self._player.play()
        rate = self._playback_rate
        QTimer.singleShot(0, lambda: self._player.setPlaybackRate(rate))

    def _emit_playback_position(self, *_args) -> None:
        if self._current_file is None:
            return
        duration = self._player.duration()
        if duration <= 0:
            return
        self.playback_position.emit(self._player.position(), duration)

    def _on_main_media_status(self, status: QMediaPlayer.MediaStatus) -> None:
        if status != QMediaPlayer.MediaStatus.EndOfMedia:
            return

        finished_file = self._current_file
        self._player.setSource(QUrl())
        self._current_file = None

        if finished_file and not self._is_persistent(finished_file):
            self._schedule_cleanup(finished_file)

        if not self._stop_event.is_set():
            self.sample_finished.emit()
            if self._advance_on_finish:
                self.playback_finished.emit()

    def _on_word_media_status(self, status: QMediaPlayer.MediaStatus) -> None:
        if status != QMediaPlayer.MediaStatus.EndOfMedia:
            return
        self._word_player.setSource(QUrl())
        if self._word_temp_file and not self._is_persistent(self._word_temp_file):
            self._schedule_cleanup(self._word_temp_file)
            self._word_temp_file = None
        if self._word_preview_pending:
            self._word_preview_pending = False
            self.sample_finished.emit()

    def _schedule_cleanup(self, path: Path) -> None:
        if self._is_persistent(path):
            return
        if path in self._temp_files:
            self._temp_files.remove(path)
        cache_keys = [k for k, v in self._audio_cache.items() if v == path]
        for key in cache_keys:
            del self._audio_cache[key]
        QTimer.singleShot(500, lambda: self._cleanup_file(path))

    def _cleanup_file(self, path: Path, retries: int = 0) -> None:
        if self._is_persistent(path):
            return
        try:
            path.unlink(missing_ok=True)
        except PermissionError:
            if retries < 5:
                QTimer.singleShot(
                    500 * (retries + 1),
                    lambda: self._cleanup_file(path, retries + 1),
                )

    @staticmethod
    def available_voices() -> list[tuple[str, str]]:
        from .tts_voices import get_voices_for_language

        return get_voices_for_language("en")
