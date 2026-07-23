"""Google Cloud Text-to-Speech API client."""

from __future__ import annotations

import base64
import logging

import requests

logger = logging.getLogger(__name__)

BOOK_TO_LOCALE: dict[str, str] = {
    "en": "en-US",
    "uk": "uk-UA",
    "ru": "ru-RU",
    "de": "de-DE",
    "fr": "fr-FR",
    "es": "es-ES",
    "it": "it-IT",
    "pt": "pt-BR",
    "pl": "pl-PL",
    "nl": "nl-NL",
    "sv": "sv-SE",
    "da": "da-DK",
    "fi": "fi-FI",
    "cs": "cs-CZ",
    "ja": "ja-JP",
    "ko": "ko-KR",
    "nb": "nb-NO",
    "tr": "tr-TR",
    "zh": "cmn-CN",
}

VOICES_BY_LANG: dict[str, list[tuple[str, str]]] = {
    "en": [
        ("en-US-Neural2-F", "Neural2 F (US)"),
        ("en-US-Neural2-D", "Neural2 D (US Male)"),
        ("en-US-Neural2-J", "Neural2 J (US Female)"),
        ("en-GB-Neural2-F", "Neural2 F (UK)"),
        ("en-GB-Neural2-A", "Neural2 A (UK Male)"),
    ],
    "uk": [
        ("uk-UA-Wavenet-A", "Wavenet A (Female)"),
        ("uk-UA-Standard-A", "Standard A (Female)"),
    ],
    "ru": [
        ("ru-RU-Wavenet-A", "Wavenet A (Female)"),
        ("ru-RU-Wavenet-B", "Wavenet B (Male)"),
    ],
    "de": [
        ("de-DE-Neural2-F", "Neural2 F"),
        ("de-DE-Neural2-D", "Neural2 D (Male)"),
    ],
    "fr": [
        ("fr-FR-Neural2-A", "Neural2 A (Female)"),
        ("fr-FR-Neural2-D", "Neural2 D (Male)"),
    ],
    "es": [
        ("es-ES-Neural2-A", "Neural2 A (Female)"),
        ("es-ES-Neural2-D", "Neural2 D (Male)"),
    ],
    "it": [
        ("it-IT-Neural2-A", "Neural2 A (Female)"),
        ("it-IT-Neural2-C", "Neural2 C (Male)"),
    ],
    "pt": [
        ("pt-BR-Neural2-A", "Neural2 A (Female)"),
        ("pt-BR-Neural2-B", "Neural2 B (Male)"),
    ],
    "pl": [
        ("pl-PL-Wavenet-A", "Wavenet A (Female)"),
        ("pl-PL-Wavenet-B", "Wavenet B (Male)"),
    ],
    "ja": [
        ("ja-JP-Neural2-B", "Neural2 B (Female)"),
        ("ja-JP-Neural2-C", "Neural2 C (Male)"),
    ],
    "zh": [
        ("cmn-CN-Wavenet-A", "Wavenet A (Female)"),
        ("cmn-CN-Wavenet-B", "Wavenet B (Male)"),
    ],
}

DEFAULT_VOICE = "en-US-Neural2-F"


def locale_for_lang(lang: str) -> str:
    return BOOK_TO_LOCALE.get(lang, "en-US")


def list_voices_for_language(lang_code: str) -> list[tuple[str, str]]:
    voices = VOICES_BY_LANG.get(lang_code)
    if voices:
        return voices
    return VOICES_BY_LANG.get("en", [(DEFAULT_VOICE, "Neural2 F (US)")])


def default_voice_for_language(lang_code: str) -> str:
    voices = list_voices_for_language(lang_code)
    return voices[0][0] if voices else DEFAULT_VOICE


def synthesize_mp3(
    text: str,
    *,
    voice: str,
    lang: str,
    api_key: str,
    speed: float = 1.0,
    timeout: int = 60,
) -> bytes:
    text = text.strip()
    if not text:
        return b""
    if not api_key:
        raise RuntimeError("Google Cloud TTS API key is missing")

    voice_name = voice or default_voice_for_language(lang)
    locale = locale_for_lang(lang)
    if "-" not in voice_name:
        voice_name = f"{locale}-Neural2-F"

    from .tts_speed import normalize_ui_speech_rate

    resp = requests.post(
        "https://texttospeech.googleapis.com/v1/text:synthesize",
        params={"key": api_key.strip()},
        json={
            "input": {"text": text},
            "voice": {"languageCode": locale, "name": voice_name},
            "audioConfig": {
                "audioEncoding": "MP3",
                "speakingRate": normalize_ui_speech_rate(speed),
            },
        },
        timeout=timeout,
    )
    if resp.status_code != 200:
        detail = resp.text[:300]
        try:
            detail = resp.json().get("error", {}).get("message", detail)
        except Exception:
            pass
        raise RuntimeError(f"Google Cloud TTS HTTP {resp.status_code}: {detail}")

    payload = resp.json()
    encoded = payload.get("audioContent") or ""
    if not encoded:
        raise RuntimeError("Google Cloud TTS returned empty audio")
    return base64.b64decode(encoded)
