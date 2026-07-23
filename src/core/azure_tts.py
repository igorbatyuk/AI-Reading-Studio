"""Microsoft Azure Speech TTS client."""

from __future__ import annotations

import html
import logging
from xml.sax.saxutils import escape

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
    "zh": "zh-CN",
}

VOICES_BY_LANG: dict[str, list[tuple[str, str]]] = {
    "en": [
        ("en-US-JennyNeural", "Jenny (US Female)"),
        ("en-US-GuyNeural", "Guy (US Male)"),
        ("en-US-AriaNeural", "Aria (US Female)"),
        ("en-GB-SoniaNeural", "Sonia (UK Female)"),
        ("en-GB-RyanNeural", "Ryan (UK Male)"),
    ],
    "uk": [
        ("uk-UA-OstapNeural", "Ostap (Male)"),
        ("uk-UA-PolinaNeural", "Polina (Female)"),
    ],
    "ru": [
        ("ru-RU-DmitryNeural", "Dmitry (Male)"),
        ("ru-RU-SvetlanaNeural", "Svetlana (Female)"),
    ],
    "de": [
        ("de-DE-KatjaNeural", "Katja (Female)"),
        ("de-DE-ConradNeural", "Conrad (Male)"),
    ],
    "fr": [
        ("fr-FR-DeniseNeural", "Denise (Female)"),
        ("fr-FR-HenriNeural", "Henri (Male)"),
    ],
    "es": [
        ("es-ES-ElviraNeural", "Elvira (Female)"),
        ("es-ES-AlvaroNeural", "Alvaro (Male)"),
    ],
    "it": [
        ("it-IT-ElsaNeural", "Elsa (Female)"),
        ("it-IT-DiegoNeural", "Diego (Male)"),
    ],
    "pt": [
        ("pt-BR-FranciscaNeural", "Francisca (Female)"),
        ("pt-BR-AntonioNeural", "Antonio (Male)"),
    ],
    "pl": [
        ("pl-PL-AgnieszkaNeural", "Agnieszka (Female)"),
        ("pl-PL-MarekNeural", "Marek (Male)"),
    ],
    "ja": [
        ("ja-JP-NanamiNeural", "Nanami (Female)"),
        ("ja-JP-KeitaNeural", "Keita (Male)"),
    ],
    "zh": [
        ("zh-CN-XiaoxiaoNeural", "Xiaoxiao (Female)"),
        ("zh-CN-YunxiNeural", "Yunxi (Male)"),
    ],
}

DEFAULT_VOICE = "en-US-JennyNeural"


def locale_for_lang(lang: str) -> str:
    return BOOK_TO_LOCALE.get(lang, "en-US")


def list_voices_for_language(lang_code: str) -> list[tuple[str, str]]:
    voices = VOICES_BY_LANG.get(lang_code)
    if voices:
        return voices
    return VOICES_BY_LANG.get("en", [(DEFAULT_VOICE, "Jenny (US Female)")])


def default_voice_for_language(lang_code: str) -> str:
    voices = list_voices_for_language(lang_code)
    return voices[0][0] if voices else DEFAULT_VOICE


def synthesize_mp3(
    text: str,
    *,
    voice: str,
    lang: str,
    api_key: str,
    region: str,
    speed: float = 1.0,
    timeout: int = 60,
) -> bytes:
    text = text.strip()
    if not text:
        return b""
    if not api_key:
        raise RuntimeError("Azure Speech API key is missing")
    if not region:
        raise RuntimeError("Azure Speech region is missing")

    locale = locale_for_lang(lang)
    from .tts_speed import edge_rate_string

    rate_attr = edge_rate_string(speed)
    safe = escape(text)
    ssml = (
        f'<speak version="1.0" xml:lang="{html.escape(locale)}">'
        f'<voice name="{html.escape(voice or DEFAULT_VOICE)}">'
        f'<prosody rate="{rate_attr}">{safe}</prosody>'
        f"</voice></speak>"
    )
    url = f"https://{region.strip()}.tts.speech.microsoft.com/cognitiveservices/v1"
    resp = requests.post(
        url,
        data=ssml.encode("utf-8"),
        headers={
            "Ocp-Apim-Subscription-Key": api_key.strip(),
            "Content-Type": "application/ssml+xml",
            "X-Microsoft-OutputFormat": "audio-16khz-128kbitrate-mono-mp3",
        },
        timeout=timeout,
    )
    if resp.status_code != 200:
        detail = resp.text[:300]
        raise RuntimeError(f"Azure TTS HTTP {resp.status_code}: {detail}")
    if not resp.content:
        raise RuntimeError("Azure TTS returned empty audio")
    return resp.content
