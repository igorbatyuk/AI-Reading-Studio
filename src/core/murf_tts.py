"""Murf.ai Text-to-Speech API client (Gen2 non-streaming)."""

from __future__ import annotations

import base64
import logging
import time

import requests

logger = logging.getLogger(__name__)

API_BASE = "https://api.murf.ai"
DEFAULT_VOICE = "Natalie"

DEFAULT_VOICES: list[tuple[str, str]] = [
    (DEFAULT_VOICE, "Natalie (Female, EN-US)"),
    ("Ken", "Ken (Male, EN-US)"),
    ("Ariana", "Ariana (Female, EN-US)"),
]

_voices_cache: tuple[float, list[tuple[str, str]]] | None = None
_VOICES_CACHE_TTL = 3600.0

BOOK_TO_LOCALE: dict[str, str] = {
    "en": "en-US",
    "uk": "uk-UA",
    "ru": "ru-RU",
    "de": "de-DE",
    "fr": "fr-FR",
    "es": "es-ES",
    "it": "it-IT",
    "pt": "pt-PT",
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


def _api_headers(api_key: str) -> dict[str, str]:
    return {
        "api-key": api_key.strip(),
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def locale_for_lang(lang: str) -> str:
    return BOOK_TO_LOCALE.get(lang, "en-US")


def fetch_voices(
    api_key: str, timeout: int = 15, *, force: bool = False
) -> list[tuple[str, str]]:
    """Return Gen2 voices from Murf API (cached)."""
    global _voices_cache
    if not api_key:
        return list(DEFAULT_VOICES)

    now = time.monotonic()
    if (
        not force
        and _voices_cache is not None
        and now - _voices_cache[0] < _VOICES_CACHE_TTL
    ):
        return list(_voices_cache[1])

    resp = requests.get(
        f"{API_BASE}/v1/speech/voices",
        headers=_api_headers(api_key),
        params={"model": "gen2"},
        timeout=timeout,
    )
    if resp.status_code != 200:
        detail = resp.text[:300]
        raise RuntimeError(f"Murf voices HTTP {resp.status_code}: {detail}")

    voices: list[tuple[str, str]] = []
    for item in resp.json():
        voice_id = str(item.get("voiceId") or "").strip()
        display = str(item.get("displayName") or voice_id).strip()
        locale = str(item.get("locale") or "en-US").strip()
        gender_raw = str(
            item.get("gender") or item.get("voiceGender") or ""
        ).strip().lower()
        gender_tag = ""
        if gender_raw in ("female", "f"):
            gender_tag = "Female"
        elif gender_raw in ("male", "m"):
            gender_tag = "Male"
        if voice_id:
            if gender_tag:
                voices.append((voice_id, f"{display} ({gender_tag}, {locale})"))
            else:
                voices.append((voice_id, f"{display} ({locale})"))

    if not voices:
        voices = list(DEFAULT_VOICES)
    _voices_cache = (now, voices)
    return list(voices)


def list_voices_for_language(lang_code: str, api_key: str = "") -> list[tuple[str, str]]:
    locale = locale_for_lang(lang_code)
    if api_key:
        try:
            voices = fetch_voices(api_key)
            matched = [
                (voice_id, label)
                for voice_id, label in voices
                if f"({locale})" in label or locale.split("-")[0] in label.lower()
            ]
            return matched or voices
        except Exception as exc:
            logger.debug("Murf voice list fetch failed: %s", exc)
    return list(DEFAULT_VOICES)


def default_voice_for_language(lang_code: str) -> str:
    _ = lang_code
    return DEFAULT_VOICE


def resolve_voice_id(voice: str, api_key: str = "") -> str:
    cleaned = (voice or "").strip() or DEFAULT_VOICE
    if api_key:
        try:
            valid = {voice_id for voice_id, _label in fetch_voices(api_key)}
            if cleaned not in valid:
                logger.warning(
                    "Murf voice %s unavailable; using %s", cleaned, DEFAULT_VOICE
                )
                return DEFAULT_VOICE
            return cleaned
        except Exception as exc:
            logger.debug("Murf voice resolve fetch failed: %s", exc)
    if cleaned not in {voice_id for voice_id, _label in DEFAULT_VOICES}:
        return DEFAULT_VOICE
    return cleaned


def parse_word_durations(data: dict) -> list[tuple[int, int]]:
    """Extract (start_ms, end_ms) pairs from Murf GenerateSpeechResponse."""
    timings: list[tuple[int, int]] = []
    for item in data.get("wordDurations") or []:
        if not isinstance(item, dict):
            continue
        start = int(item.get("startMs") or 0)
        end = int(item.get("endMs") or start + 1)
        if end <= start:
            end = start + 1
        timings.append((start, end))
    return timings


def synthesize_mp3(
    text: str,
    *,
    voice: str,
    lang: str,
    api_key: str,
    speed: float = 1.0,
    timeout: int = 120,
) -> tuple[bytes, dict[str, int], list[tuple[int, int]]]:
    from .tts_speed import murf_speech_rate

    text = text.strip()
    if not text:
        return b"", {}, []
    if not api_key:
        raise RuntimeError("Murf API key is missing")

    voice_id = resolve_voice_id(voice or DEFAULT_VOICE, api_key)
    rate_value = murf_speech_rate(speed)
    logger.info("Murf TTS speed ui=%.2f rate=%d", speed, rate_value)
    payload: dict[str, object] = {
        "text": text,
        "voiceId": voice_id,
        "format": "MP3",
        "locale": locale_for_lang(lang),
        "sampleRate": 44100,
        "modelVersion": "GEN2",
        "encodeAsBase64": True,
        "rate": rate_value,
        "wordDurationsAsOriginalText": True,
    }

    resp = requests.post(
        f"{API_BASE}/v1/speech/generate",
        headers=_api_headers(api_key),
        json=payload,
        timeout=timeout,
    )
    if resp.status_code != 200:
        detail = resp.text[:300]
        try:
            detail = resp.json().get("message", detail)
        except Exception:
            pass
        if resp.status_code == 402:
            detail = "Murf character limit exhausted or subscription expired."
        raise RuntimeError(f"Murf TTS HTTP {resp.status_code}: {detail}")

    data = resp.json()
    encoded = data.get("encodedAudio") or ""
    if encoded:
        audio = base64.b64decode(encoded)
    else:
        audio_url = data.get("audioFile") or ""
        if not audio_url:
            raise RuntimeError("Murf TTS returned no audio")
        audio_resp = requests.get(audio_url, timeout=timeout)
        if audio_resp.status_code != 200 or not audio_resp.content:
            raise RuntimeError("Murf TTS audio download failed")
        audio = audio_resp.content

    usage = {
        "consumed": int(data.get("consumedCharacterCount") or 0),
        "remaining": int(data.get("remainingCharacterCount") or 0),
    }
    word_timings = parse_word_durations(data)
    return audio, usage, word_timings
