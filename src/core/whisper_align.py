"""Optional Whisper word alignment for offline TTS highlight timings."""

from __future__ import annotations

import json
import logging
import re
import subprocess
import sys
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

WHISPER_MODES = frozenset({"off", "auto", "on"})
DEFAULT_MODE = "auto"
WORKER_SCRIPT = "whisper_worker.py"

BOOK_TO_WHISPER_LANG: dict[str, str] = {
    "en": "en",
    "uk": "uk",
    "ru": "ru",
    "de": "de",
    "fr": "fr",
    "es": "es",
    "it": "it",
    "pt": "pt",
    "pl": "pl",
    "nl": "nl",
    "sv": "sv",
    "da": "da",
    "fi": "fi",
    "cs": "cs",
    "ja": "ja",
    "ko": "ko",
    "nb": "no",
    "tr": "tr",
    "zh": "zh",
}


def normalize_mode(mode: str) -> str:
    cleaned = (mode or DEFAULT_MODE).strip().lower()
    return cleaned if cleaned in WHISPER_MODES else DEFAULT_MODE


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def bundled_whisper_dir() -> Path:
    return project_root() / "tts" / "whisper"


def find_whisper_worker() -> Path | None:
    worker = bundled_whisper_dir() / WORKER_SCRIPT
    return worker if worker.is_file() else None


def find_whisper_python() -> Path | None:
    base = bundled_whisper_dir()
    if sys.platform == "win32":
        candidates = (
            base / ".venv" / "Scripts" / "python.exe",
            base / ".venv" / "Scripts" / "python3.exe",
        )
    else:
        candidates = (
            base / ".venv" / "bin" / "python3",
            base / ".venv" / "python3",
        )
    for path in candidates:
        if path.is_file():
            return path
    return None


def is_worker_available() -> bool:
    return find_whisper_worker() is not None and find_whisper_python() is not None


def whisper_lang_for_book(lang: str) -> str:
    return BOOK_TO_WHISPER_LANG.get(lang, "en")


def _normalize_token(word: str) -> str:
    return re.sub(r"[^\w']+", "", word.lower())


def map_whisper_words_to_text(
    text: str,
    whisper_words: list[dict[str, object]],
) -> list[tuple[int, int]]:
    """Map Whisper word timestamps onto tokens from the source text."""
    text_tokens = re.findall(r"\S+", text)
    if not text_tokens or not whisper_words:
        return []

    prepared: list[tuple[str, int, int]] = []
    for item in whisper_words:
        token = _normalize_token(str(item.get("word") or ""))
        if not token:
            continue
        start_ms = int(item.get("start_ms", 0) or 0)
        end_ms = int(item.get("end_ms", start_ms + 1) or start_ms + 1)
        if end_ms <= start_ms:
            end_ms = start_ms + 1
        prepared.append((token, start_ms, end_ms))

    if not prepared:
        return []

    timings: list[tuple[int, int]] = []
    wi = 0
    matched = 0
    for token in text_tokens:
        target = _normalize_token(token)
        if not target:
            continue
        while wi < len(prepared) and prepared[wi][0] != target:
            wi += 1
        if wi >= len(prepared):
            break
        _norm, start_ms, end_ms = prepared[wi]
        timings.append((start_ms, end_ms))
        matched += 1
        wi += 1

    if matched < max(1, len(text_tokens) // 3):
        return []
    return timings


def _run_worker(audio_path: Path, lang: str, *, timeout: int = 300) -> list[dict]:
    worker = find_whisper_worker()
    python_bin = find_whisper_python()
    if not worker or not python_bin:
        return []

    cmd = [
        str(python_bin),
        str(worker),
        "--audio",
        str(audio_path),
        "--lang",
        whisper_lang_for_book(lang),
    ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            cwd=str(worker.parent),
        )
    except subprocess.TimeoutExpired:
        logger.warning("Whisper alignment timed out after %ss", timeout)
        return []
    except OSError as exc:
        logger.debug("Whisper worker failed to start: %s", exc)
        return []

    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        logger.debug("Whisper worker error: %s", detail[:300])
        return []

    try:
        payload = json.loads(result.stdout.strip() or "{}")
    except json.JSONDecodeError:
        logger.debug("Whisper worker returned invalid JSON")
        return []

    words = payload.get("words") or []
    if not isinstance(words, list):
        return []
    return [item for item in words if isinstance(item, dict)]


def try_align_words(
    text: str,
    audio_path: Path,
    *,
    lang: str,
    mode: str = DEFAULT_MODE,
) -> list[tuple[int, int]] | None:
    """Return exact word timings or None to fall back to estimation."""
    text = text.strip()
    if not text or not audio_path.exists() or audio_path.stat().st_size == 0:
        return None

    normalized_mode = normalize_mode(mode)
    if normalized_mode == "off":
        return None
    if not is_worker_available():
        if normalized_mode == "on":
            logger.info(
                "Whisper alignment enabled but worker missing "
                "(run tts/whisper/setup.bat)"
            )
        return None

    from .media_duration import media_duration_ms

    duration_ms = media_duration_ms(audio_path)
    timeout = max(60, min(600, 30 + (duration_ms // 1000) * 3))
    whisper_words = _run_worker(audio_path, lang, timeout=timeout)
    timings = map_whisper_words_to_text(text, whisper_words)
    return timings or None
