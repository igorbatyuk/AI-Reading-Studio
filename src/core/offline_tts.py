"""Offline TTS via pyttsx3 (Windows SAPI / espeak)."""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

_LANG_HINTS: dict[str, tuple[str, ...]] = {
    "en": ("english", "en-us", "en-gb", "zira", "david"),
    "uk": ("ukrainian", "uk-ua"),
    "ru": ("russian", "ru-ru"),
    "de": ("german", "de-de"),
    "fr": ("french", "fr-fr"),
    "es": ("spanish", "es-es"),
    "pl": ("polish", "pl-pl"),
    "it": ("italian", "it-it"),
    "pt": ("portuguese", "pt-"),
    "nb": ("norwegian", "nb-no"),
}


def is_available() -> bool:
    try:
        import pyttsx3  # noqa: F401

        return True
    except ImportError:
        return False


def generate_wav(
    text: str, lang: str = "en", rate: float = 1.0, out_path: Path | None = None
) -> Path:
    import pyttsx3

    if out_path is None:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            out_path = Path(tmp.name)

    engine = pyttsx3.init()
    _select_voice(engine, lang)
    from .tts_speed import engine_speech_rate

    base_rate = engine.getProperty("rate") or 200
    engine.setProperty("rate", int(base_rate * engine_speech_rate(rate)))
    engine.save_to_file(text, str(out_path))
    engine.runAndWait()
    engine.stop()

    if not out_path.exists() or out_path.stat().st_size == 0:
        raise RuntimeError("Offline TTS produced no audio")
    return out_path


def _select_voice(engine, lang: str) -> None:
    voices = engine.getProperty("voices") or []
    hints = _LANG_HINTS.get(lang, (lang,))
    for voice in voices:
        blob = f"{voice.name} {voice.id}".lower()
        if any(h in blob for h in hints):
            engine.setProperty("voice", voice.id)
            return
    if voices:
        engine.setProperty("voice", voices[0].id)
    else:
        logger.warning("No offline TTS voices found for lang=%s", lang)
