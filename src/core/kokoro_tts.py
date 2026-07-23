"""Neural offline TTS via Kokoro (Python 3.12 worker subprocess)."""

from __future__ import annotations

import importlib.util
import logging
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

logger = logging.getLogger(__name__)


class _GenerationQueue:
    """FIFO gate: one Kokoro subprocess at a time; others wait in order."""

    def __init__(self) -> None:
        self._guard = threading.Lock()
        self._condition = threading.Condition(self._guard)
        self._active = False
        self._waiting = 0

    @property
    def waiting_count(self) -> int:
        with self._guard:
            return self._waiting

    def acquire(self) -> None:
        with self._condition:
            while self._active:
                self._waiting += 1
                self._condition.wait()
                self._waiting -= 1
            self._active = True

    def release(self) -> None:
        with self._condition:
            self._active = False
            self._condition.notify()

    def __enter__(self) -> "_GenerationQueue":
        self.acquire()
        return self

    def __exit__(self, *args: object) -> None:
        self.release()


_GENERATION_QUEUE = _GenerationQueue()

MODEL_ONNX = "kokoro-v1.0.onnx"
MODEL_VOICES = "voices-v1.0.bin"
WORKER_SCRIPT = "kokoro_worker.py"

KOKORO_LANG_CODES: dict[str, str] = {
    "en": "en-us",
    "uk": "en-us",
    "ru": "en-us",
    "nb": "en-us",
    "de": "en-us",
    "es": "en-us",
    "pt": "en-us",
    "pl": "en-us",
    "nl": "en-us",
    "sv": "en-us",
    "da": "en-us",
    "fi": "en-us",
    "cs": "en-us",
    "ko": "en-us",
    "tr": "en-us",
    "fr": "fr-fr",
    "it": "it",
    "ja": "ja",
    "zh": "cmn",
}

# voice_id, kokoro_lang, label suffix, book langs (empty = lang-specific only)
KOKORO_VOICE_DEFS: list[tuple[str, str, str, tuple[str, ...]]] = [
    ("af_alloy", "en-us", "Alloy", ("en", "uk", "ru", "de", "es", "pl", "nb")),
    ("af_aoede", "en-us", "Aoede", ("en", "uk", "ru", "de", "es", "pl", "nb")),
    ("af_bella", "en-us", "Bella", ("en", "uk", "ru", "de", "es", "pl", "nb")),
    ("af_heart", "en-us", "Heart", ("en", "uk", "ru", "de", "es", "pl", "nb")),
    ("af_jessica", "en-us", "Jessica", ("en", "uk", "ru", "de", "es", "pl", "nb")),
    ("af_kore", "en-us", "Kore", ("en", "uk", "ru", "de", "es", "pl", "nb")),
    ("af_nicole", "en-us", "Nicole", ("en", "uk", "ru", "de", "es", "pl", "nb")),
    ("af_nova", "en-us", "Nova", ("en", "uk", "ru", "de", "es", "pl", "nb")),
    ("af_river", "en-us", "River", ("en", "uk", "ru", "de", "es", "pl", "nb")),
    ("af_sarah", "en-us", "Sarah", ("en", "uk", "ru", "de", "es", "pl", "nb")),
    ("af_sky", "en-us", "Sky", ("en", "uk", "ru", "de", "es", "pl", "nb")),
    ("am_adam", "en-us", "Adam", ("en", "uk", "ru", "de", "es", "pl", "nb")),
    ("am_echo", "en-us", "Echo", ("en", "uk", "ru", "de", "es", "pl", "nb")),
    ("am_eric", "en-us", "Eric", ("en", "uk", "ru", "de", "es", "pl", "nb")),
    ("am_fenrir", "en-us", "Fenrir", ("en", "uk", "ru", "de", "es", "pl", "nb")),
    ("am_liam", "en-us", "Liam", ("en", "uk", "ru", "de", "es", "pl", "nb")),
    ("am_michael", "en-us", "Michael", ("en", "uk", "ru", "de", "es", "pl", "nb")),
    ("am_onyx", "en-us", "Onyx", ("en", "uk", "ru", "de", "es", "pl", "nb")),
    ("am_puck", "en-us", "Puck", ("en", "uk", "ru", "de", "es", "pl", "nb")),
    ("bf_alice", "en-gb", "Alice (UK)", ("en",)),
    ("bf_emma", "en-gb", "Emma (UK)", ("en",)),
    ("bf_isabella", "en-gb", "Isabella (UK)", ("en",)),
    ("bf_lily", "en-gb", "Lily (UK)", ("en",)),
    ("bm_daniel", "en-gb", "Daniel (UK)", ("en",)),
    ("bm_fable", "en-gb", "Fable (UK)", ("en",)),
    ("bm_george", "en-gb", "George (UK)", ("en",)),
    ("bm_lewis", "en-gb", "Lewis (UK)", ("en",)),
    ("ff_siwis", "fr-fr", "Siwis", ("fr",)),
    ("if_sara", "it", "Sara", ("it",)),
    ("im_nicola", "it", "Nicola", ("it",)),
    ("jf_alpha", "ja", "Alpha", ("ja",)),
    ("jf_gongitsune", "ja", "Gongitsune", ("ja",)),
    ("jf_nezumi", "ja", "Nezumi", ("ja",)),
    ("jf_tebukuro", "ja", "Tebukuro", ("ja",)),
    ("jm_kumo", "ja", "Kumo", ("ja",)),
    ("zf_xiaobei", "cmn", "Xiaobei", ("zh",)),
    ("zf_xiaoni", "cmn", "Xiaoni", ("zh",)),
    ("zf_xiaoxiao", "cmn", "Xiaoxiao", ("zh",)),
    ("zf_xiaoyi", "cmn", "Xiaoyi", ("zh",)),
    ("zm_yunjian", "cmn", "Yunjian", ("zh",)),
    ("zm_yunxi", "cmn", "Yunxi", ("zh",)),
    ("zm_yunxia", "cmn", "Yunxia", ("zh",)),
    ("zm_yunyang", "cmn", "Yunyang", ("zh",)),
]

DEFAULT_KOKORO_VOICE = "af_heart"

_kokoro_text_module = None


def _kokoro_text():
    global _kokoro_text_module
    if _kokoro_text_module is not None:
        return _kokoro_text_module
    module_path = bundled_kokoro_dir() / "kokoro_text.py"
    spec = importlib.util.spec_from_file_location("kokoro_text", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Kokoro text helpers not found: {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _kokoro_text_module = module
    return module


def prepare_text_for_kokoro(text: str) -> str:
    return _kokoro_text().prepare_text_for_kokoro(text)


def split_text_for_kokoro(text: str, max_chars: int | None = None) -> list[str]:
    if max_chars is None:
        max_chars = _kokoro_text().MAX_CHUNK_CHARS
    return _kokoro_text().split_text_for_kokoro(text, max_chars)


def timeout_for_text(text: str) -> int:
    """Scale subprocess timeout with passage length and chunk count."""
    cleaned = prepare_text_for_kokoro(text)
    chunks = split_text_for_kokoro(cleaned)
    chunk_count = max(1, len(chunks))
    per_chunk = 75
    base = 120 + len(cleaned) // 8 + chunk_count * per_chunk
    return min(900, max(180, base))


def kokoro_lang_for_voice(voice_id: str, book_lang: str) -> str:
    voice_id = (voice_id or DEFAULT_KOKORO_VOICE).strip()
    for vid, kokoro_lang, _name, _langs in KOKORO_VOICE_DEFS:
        if vid == voice_id:
            return kokoro_lang
    return kokoro_lang_for_book(book_lang)


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def bundled_kokoro_dir() -> Path:
    return project_root() / "tts" / "kokoro"


def find_kokoro_worker() -> Path | None:
    worker = bundled_kokoro_dir() / WORKER_SCRIPT
    return worker if worker.is_file() else None


def find_kokoro_python() -> Path | None:
    base = bundled_kokoro_dir()
    if sys.platform == "win32":
        candidates = (
            base / ".venv" / "Scripts" / "python.exe",
            base / ".venv" / "Scripts" / "python3.exe",
        )
    else:
        candidates = (
            base / ".venv" / "bin" / "python3",
            base / ".venv" / "bin" / "python",
        )
    for path in candidates:
        if path.is_file():
            return path
    return None


def worker_is_available() -> bool:
    return find_kokoro_worker() is not None and find_kokoro_python() is not None


def find_kokoro_binary() -> str | None:
    for name in ("kokoro-tts", "kokoro-tts.exe"):
        path = shutil.which(name)
        if path:
            return path
    return None


def _models_in_dir(models_dir: Path) -> bool:
    return (
        models_dir.is_dir()
        and (models_dir / MODEL_ONNX).is_file()
        and (models_dir / MODEL_VOICES).is_file()
    )


def resolve_model_dir(app_dir: Path) -> Path | None:
    bundled_models = bundled_kokoro_dir() / "models"
    if _models_in_dir(bundled_models):
        return bundled_models

    legacy_models = app_dir / "kokoro_models"
    if _models_in_dir(legacy_models):
        return legacy_models
    return None


def is_available(app_dir: Path) -> bool:
    if resolve_model_dir(app_dir) is None:
        return False
    return worker_is_available() or find_kokoro_binary() is not None


def kokoro_lang_for_book(lang: str) -> str:
    return KOKORO_LANG_CODES.get(lang, "en-us")


def list_voices_for_language(lang_code: str) -> list[tuple[str, str]]:
    if lang_code == "uk":
        return []
    voices: list[tuple[str, str]] = []
    seen: set[str] = set()
    for voice_id, kokoro_lang, name, langs in KOKORO_VOICE_DEFS:
        if lang_code not in langs:
            continue
        if voice_id in seen:
            continue
        seen.add(voice_id)
        region = kokoro_lang.upper().replace("-", " ")
        gender = (
            "Female"
            if voice_id.startswith(("af_", "bf_", "ff_", "if_", "jf_", "zf_"))
            else "Male"
        )
        label = f"Kokoro — {region} — {name} ({gender})"
        voices.append((voice_id, label))
    if voices:
        return voices
    return [(DEFAULT_KOKORO_VOICE, "Kokoro — US — Heart (Female)")]


def _generate_via_worker(
    text: str,
    voice: str,
    lang: str,
    model_dir: Path,
    speed: float,
    out_path: Path,
) -> Path:
    worker = find_kokoro_worker()
    python_bin = find_kokoro_python()
    if not worker or not python_bin:
        raise RuntimeError(
            "Kokoro worker not found. Run tts/kokoro/setup.bat (Python 3.12 venv)."
        )

    kokoro_lang = kokoro_lang_for_voice(voice or DEFAULT_KOKORO_VOICE, lang)
    from .tts_speed import kokoro_speech_rate

    speed_value = kokoro_speech_rate(speed)
    prepared = prepare_text_for_kokoro(text)
    if not prepared:
        raise RuntimeError("Empty text after Kokoro cleanup")

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, encoding="utf-8"
    ) as tmp_in:
        tmp_in.write(prepared)
        text_file = Path(tmp_in.name)

    timeout = timeout_for_text(prepared)
    try:
        cmd = [
            str(python_bin),
            str(worker),
            "--text-file",
            str(text_file),
            "--output",
            str(out_path),
            "--voice",
            voice or DEFAULT_KOKORO_VOICE,
            "--lang",
            kokoro_lang,
            "--speed",
            str(speed_value),
            "--models-dir",
            str(model_dir),
        ]
        with _GENERATION_QUEUE:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                cwd=str(worker.parent),
            )
    except subprocess.TimeoutExpired as exc:
        out_path.unlink(missing_ok=True)
        raise RuntimeError(
            f"Kokoro timed out after {timeout}s ({len(prepared)} chars). "
            "Try a smaller block size in Settings → Reading."
        ) from exc
    finally:
        text_file.unlink(missing_ok=True)

    if result.returncode != 0:
        out_path.unlink(missing_ok=True)
        detail = (result.stderr or result.stdout or "Kokoro worker failed").strip()
        raise RuntimeError(detail)

    if not out_path.exists() or out_path.stat().st_size == 0:
        out_path.unlink(missing_ok=True)
        raise RuntimeError("Kokoro produced no audio")

    return out_path


def _generate_via_cli(
    text: str,
    voice: str,
    lang: str,
    model_dir: Path,
    speed: float,
    out_path: Path,
) -> Path:
    binary = find_kokoro_binary()
    if not binary:
        raise RuntimeError("kokoro-tts not found in PATH. Install: pip install kokoro-tts")

    kokoro_lang = kokoro_lang_for_voice(voice or DEFAULT_KOKORO_VOICE, lang)
    from .tts_speed import kokoro_speech_rate

    speed_value = kokoro_speech_rate(speed)
    prepared = prepare_text_for_kokoro(text)
    if not prepared:
        raise RuntimeError("Empty text after Kokoro cleanup")

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, encoding="utf-8"
    ) as tmp_in:
        tmp_in.write(prepared)
        input_path = Path(tmp_in.name)

    timeout = timeout_for_text(prepared)
    try:
        cmd = [
            binary,
            str(input_path),
            str(out_path),
            "--voice",
            voice or DEFAULT_KOKORO_VOICE,
            "--lang",
            kokoro_lang,
            "--speed",
            str(speed_value),
            "--format",
            "wav",
            "--model",
            str(model_dir / MODEL_ONNX),
            "--voices",
            str(model_dir / MODEL_VOICES),
        ]
        with _GENERATION_QUEUE:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
            )
    except subprocess.TimeoutExpired as exc:
        out_path.unlink(missing_ok=True)
        raise RuntimeError(
            f"Kokoro timed out after {timeout}s ({len(prepared)} chars). "
            "Try a smaller block size in Settings → Reading."
        ) from exc
    finally:
        input_path.unlink(missing_ok=True)

    if result.returncode != 0:
        out_path.unlink(missing_ok=True)
        detail = (result.stderr or result.stdout or "Kokoro failed").strip()
        raise RuntimeError(detail)

    if not out_path.exists() or out_path.stat().st_size == 0:
        out_path.unlink(missing_ok=True)
        raise RuntimeError("Kokoro produced no audio")

    return out_path


def generate_wav(
    text: str,
    voice: str,
    lang: str,
    app_dir: Path,
    speed: float = 1.0,
    out_path: Path | None = None,
) -> Path:
    model_dir = resolve_model_dir(app_dir)
    if not model_dir:
        raise RuntimeError(
            f"Kokoro model files not found. Place {MODEL_ONNX} and {MODEL_VOICES} in "
            f"tts/kokoro/models/ or ~/.ai_reading_studio/kokoro_models/"
        )

    if out_path is None:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            out_path = Path(tmp.name)

    if worker_is_available():
        return _generate_via_worker(text, voice, lang, model_dir, speed, out_path)

    return _generate_via_cli(text, voice, lang, model_dir, speed, out_path)
