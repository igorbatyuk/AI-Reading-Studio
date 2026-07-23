"""Aggregated processing / cache status for the UI."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QObject, QTimer, Signal


@dataclass
class ProcessingSnapshot:
    summary_level: str  # ok | working | error
    summary_text: str
    online: bool
    ollama_ready: bool
    book_title: str
    block_position: str
    tts_mode_label: str
    tts_engine_label: str
    tts_slow_hint: str
    highlight_sync: str  # exact | estimated | idle | na
    tts_generating: int
    tts_cache_memory: int
    tts_cache_disk: int
    tts_playback: str  # playing | paused | idle
    audio_current: str
    audio_current_error: str
    audio_next: str
    audio_next_error: str
    translation_busy: int
    translation_provider_label: str
    translation_words_cached: int
    translation_sentences_cached: int
    translation_current: str
    translation_next: str
    translation_activity: str
    import_status: str
    last_error: str


class ProcessingStatusTracker(QObject):
    changed = Signal()

    def __init__(
        self,
        tts,
        translator,
        reading_view,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.tts = tts
        self.translator = translator
        self.reading_view = reading_view
        self._import_status = ""
        self._emit_timer = QTimer(self)
        self._emit_timer.setSingleShot(True)
        self._emit_timer.setInterval(300)
        self._emit_timer.timeout.connect(self.changed.emit)
        self._cached_online: bool | None = None
        self._cached_ollama: bool | None = None
        self._network_checked_at = 0.0

        tts.generating_changed.connect(self._emit)
        tts.activity_changed.connect(self._emit)
        tts.playback_error.connect(self._emit)
        tts.playback_started.connect(self._emit)
        tts.playback_finished.connect(self._emit)
        tts.sample_finished.connect(self._emit)
        translator.activity_changed.connect(self._emit)
        reading_view.progress_updated.connect(self._emit)

    def set_import_status(self, message: str) -> None:
        self._import_status = message or ""
        self._emit()

    def clear_import_status(self) -> None:
        self._import_status = ""
        self._emit()

    def _emit(self, *_args) -> None:
        self._emit_timer.start()

    def is_busy(self) -> bool:
        view = self.reading_view
        if self._import_status:
            return True
        if self.tts.active_tasks() > 0:
            return True
        if self.translator.pending_tasks() > 0:
            return True
        if view.current_text.strip():
            audio_state, _ = self.tts.audio_status(view.current_text)
            if audio_state in ("generating", "queued", "waiting"):
                return True
        return False

    def snapshot(self) -> ProcessingSnapshot:
        from .i18n import tr
        from .network_status import is_online
        import time

        now = time.monotonic()
        if (
            self._cached_online is None
            or now - self._network_checked_at >= 30.0
        ):
            self._cached_online = is_online(use_cache=False)
            self._cached_ollama = self.translator.can_use_ollama(use_cache=False)
            self._network_checked_at = now

        view = self.reading_view
        engine_info = self.tts.describe_main_engine()
        audio_current, audio_current_error = self._block_status(view.current_text)
        audio_next, audio_next_error = self._next_block_status()

        word_cache, sentence_cache = self.translator.cache_stats()
        tts_stats = self.tts.cache_stats()
        tts_generating = self.tts.active_tasks()

        if view.is_playing and not view.is_paused:
            playback = "playing"
        elif view.is_paused:
            playback = "paused"
        else:
            playback = "idle"

        translation_current = self._translation_status(view.current_text)
        translation_next = self._next_translation_status()

        last_error = (
            self.tts.last_error()
            or self.translator.last_error
            or audio_current_error
            or audio_next_error
            or ""
        )

        summary_level, summary_text = self._summary(
            tr,
            tts_generating=tts_generating,
            audio_current=audio_current,
            audio_next=audio_next,
            translation_busy=self.translator.pending_tasks(),
            translation_current=translation_current,
            translation_next=translation_next,
            import_status=self._import_status,
            last_error=last_error,
            engine_label=engine_info.engine_label,
            is_slow=engine_info.is_slow,
        )

        return ProcessingSnapshot(
            summary_level=summary_level,
            summary_text=summary_text,
            online=bool(self._cached_online),
            ollama_ready=bool(self._cached_ollama),
            book_title=self._book_title(),
            block_position=self._block_position(),
            tts_mode_label=engine_info.mode_label,
            tts_engine_label=engine_info.engine_label,
            tts_slow_hint=tr("status.panel.tts_slow_hint")
            if engine_info.is_slow
            else "",
            highlight_sync=self._highlight_sync(),
            tts_generating=tts_generating,
            tts_cache_memory=tts_stats["memory"],
            tts_cache_disk=tts_stats["disk"],
            tts_playback=playback,
            audio_current=audio_current,
            audio_current_error=audio_current_error,
            audio_next=audio_next,
            audio_next_error=audio_next_error,
            translation_busy=self.translator.pending_tasks(),
            translation_provider_label=self.translator.provider_label("block"),
            translation_words_cached=word_cache,
            translation_sentences_cached=sentence_cache,
            translation_current=translation_current,
            translation_next=translation_next,
            translation_activity=self.translator.last_activity(),
            import_status=self._import_status,
            last_error=last_error,
        )

    def _book_title(self) -> str:
        book = self.reading_view.current_book
        if not book:
            return ""
        return book.title or ""

    def _block_position(self) -> str:
        from .i18n import tr

        view = self.reading_view
        if not view.current_book:
            return ""
        total = view.current_book.total_blocks
        if total <= 0:
            return ""
        return tr(
            "status.panel.block_position",
            current=view.current_block_index + 1,
            total=total,
        )

    def _highlight_sync(self) -> str:
        view = self.reading_view
        if not view.is_playing:
            return "idle"
        sync_mode = getattr(view, "highlight_sync_mode", "idle")
        return sync_mode if sync_mode in ("exact", "estimated") else "idle"

    def _block_status(self, text: str) -> tuple[str, str]:
        if not text.strip():
            return "none", ""
        return self.tts.audio_status(text)

    def _next_block_status(self) -> tuple[str, str]:
        view = self.reading_view
        if not view.current_book:
            return "na", ""
        next_index = view.current_block_index + 1
        if next_index >= view.current_book.total_blocks:
            return "na", ""
        next_block = view.db.get_block(view.current_book.id, next_index)
        if not next_block:
            return "na", ""
        return self.tts.audio_status(next_block[0])

    def _translation_status(self, text: str) -> str:
        if not text.strip():
            return "none"
        if self.translator.is_sentence_cached(text):
            return "ready"
        if self.translator.pending_tasks() > 0:
            return "preparing"
        return "waiting"

    def _next_translation_status(self) -> str:
        view = self.reading_view
        if not view.current_book:
            return "na"
        next_index = view.current_block_index + 1
        if next_index >= view.current_book.total_blocks:
            return "na"
        next_block = view.db.get_block(view.current_book.id, next_index)
        if not next_block:
            return "na"
        return self._translation_status(next_block[0])

    @staticmethod
    def _summary(
        tr,
        *,
        tts_generating: int,
        audio_current: str,
        audio_next: str,
        translation_busy: int,
        translation_current: str,
        translation_next: str,
        import_status: str,
        last_error: str,
        engine_label: str,
        is_slow: bool,
    ) -> tuple[str, str]:
        if audio_current == "failed" or audio_next == "failed":
            return "error", tr("status.panel.summary_error")
        if last_error and audio_current not in ("ready", "none"):
            return "error", tr("status.panel.summary_error")

        working_parts: list[str] = []
        if tts_generating > 0 or audio_current in ("generating", "queued") or (
            audio_next in ("generating", "queued")
        ):
            if is_slow and audio_current in ("generating", "queued"):
                return "working", tr(
                    "status.panel.summary_generating_slow",
                    engine=engine_label,
                )
            working_parts.append(tr("status.panel.summary_audio"))
        if translation_busy > 0 or translation_current == "preparing" or (
            translation_next == "preparing"
        ):
            working_parts.append(tr("status.panel.summary_translation"))
        if import_status:
            working_parts.append(tr("status.panel.summary_import"))

        if working_parts:
            return "working", tr(
                "status.panel.summary_working", items=", ".join(working_parts)
            )

        if audio_current == "waiting" or audio_next == "waiting":
            return "working", tr("status.panel.summary_waiting")

        return "ok", tr("status.panel.summary_ok")
