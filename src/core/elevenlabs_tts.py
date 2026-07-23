"""ElevenLabs Text-to-Speech API client."""

from __future__ import annotations

import logging
import time

import requests

logger = logging.getLogger(__name__)

API_BASE = "https://api.elevenlabs.io/v1"
# Flash v2.5: lower latency and ~half the credits vs Multilingual v2 on free tier.
DEFAULT_MODEL = "eleven_flash_v2_5"
DEFAULT_VOICE = "EXAVITQu4vr4xnSDxMaL"  # Sarah — works on free API (2026)

# Deprecated IDs that ElevenLabs now treats as Voice Library on free API.
LEGACY_VOICE_ALIASES: dict[str, str] = {
    "21m00Tcm4TlvDq8ikWAM": DEFAULT_VOICE,  # old default Rachel
}

# Premade voices available on the free API (synced with /v1/voices category=premade).
PREMADE_VOICES: list[tuple[str, str]] = [
    (DEFAULT_VOICE, "Sarah (Female, EN)"),
    ("CwhRBWXzGAHq8TQ4Fs17", "Roger (Male, EN)"),
    ("FGY2WhTYpPnrIDTdsKH5", "Laura (Female, EN)"),
    ("IKne3meq5aSn9XLyUdCD", "Charlie (Male, EN)"),
    ("JBFqnCBsd6RMkjVDRZzb", "George (Male, EN)"),
    ("N2lVS1w4EtoT3dr4eOWO", "Callum (Male, EN)"),
    ("SAz9YHcvj6GT2YYXdXww", "River (Neutral, EN)"),
    ("SOYHLrjzK2X1ezoPC6cr", "Harry (Male, EN)"),
    ("TX3LPaxmHKxFdv7VOQHJ", "Liam (Male, EN)"),
    ("Xb7hH8MSUJpSbSDYk0k2", "Alice (Female, EN)"),
    ("XrExE9yKIg1WjnnlVkGX", "Matilda (Female, EN)"),
    ("bIHbv24MWmeRgasZH58o", "Will (Male, EN)"),
    ("cgSgspJ2msm6clMCkdW9", "Jessica (Female, EN)"),
    ("cjVigY5qzO86Huf0OWal", "Eric (Male, EN)"),
    ("hpp4J3VqNfWAUOO0d1Us", "Bella (Female, EN)"),
    ("iP95p4xoKVk53GoZ742B", "Chris (Male, EN)"),
    ("nPczCjzI2devNBz1zQrb", "Brian (Male, EN)"),
    ("onwK4e9ZLuTAKqWW03F9", "Daniel (Male, EN)"),
    ("pFZP5JQG7iQjIQuC4Bku", "Lily (Female, EN)"),
    ("pNInz6obpgDQGcFmaJgB", "Adam (Male, EN)"),
    ("pqHfZKP75CvOlQylNhV4", "Bill (Male, EN)"),
]

_voices_cache: tuple[float, list[tuple[str, str]]] | None = None
_VOICES_CACHE_TTL = 3600.0

BOOK_TO_ISO: dict[str, str] = {
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


def resolve_voice_id(voice: str, api_key: str = "") -> str:
    """Map deprecated/library IDs to a free-tier premade voice."""
    cleaned = (voice or "").strip() or DEFAULT_VOICE
    cleaned = LEGACY_VOICE_ALIASES.get(cleaned, cleaned)
    if api_key:
        try:
            valid = {voice_id for voice_id, _label in fetch_premade_voices(api_key)}
            if cleaned not in valid:
                logger.warning(
                    "ElevenLabs voice %s unavailable on this plan; using %s",
                    cleaned,
                    DEFAULT_VOICE,
                )
                return DEFAULT_VOICE
            return cleaned
        except Exception as exc:
            logger.debug("ElevenLabs voice resolve fetch failed: %s", exc)
    if cleaned not in {voice_id for voice_id, _label in PREMADE_VOICES}:
        return DEFAULT_VOICE
    return cleaned


def fetch_premade_voices(
    api_key: str, timeout: int = 15, *, force: bool = False
) -> list[tuple[str, str]]:
    """Return premade voices from ElevenLabs API (cached)."""
    global _voices_cache
    if not api_key:
        return list(PREMADE_VOICES)

    now = time.monotonic()
    if (
        not force
        and _voices_cache is not None
        and now - _voices_cache[0] < _VOICES_CACHE_TTL
    ):
        return list(_voices_cache[1])

    resp = requests.get(
        f"{API_BASE}/voices",
        headers={"xi-api-key": api_key.strip()},
        timeout=timeout,
    )
    if resp.status_code != 200:
        detail = resp.text[:300]
        raise RuntimeError(f"ElevenLabs voices HTTP {resp.status_code}: {detail}")

    voices: list[tuple[str, str]] = []
    for item in resp.json().get("voices", []):
        if item.get("category") != "premade":
            continue
        voice_id = str(item.get("voice_id") or "").strip()
        name = str(item.get("name") or voice_id).strip()
        labels = item.get("labels") or {}
        lang = str(
            labels.get("language") or labels.get("accent") or "en"
        ).strip()
        lang_tag = lang.upper()[:2] if lang else "EN"
        if voice_id:
            voices.append((voice_id, f"{name} ({lang_tag})"))

    if not voices:
        voices = list(PREMADE_VOICES)
    _voices_cache = (now, voices)
    return list(voices)


def list_voices_for_language(lang_code: str, api_key: str = "") -> list[tuple[str, str]]:
    from .tts_voices import filter_voices_for_book_language

    if api_key:
        try:
            voices = fetch_premade_voices(api_key)
        except Exception as exc:
            logger.debug("ElevenLabs voice list fetch failed: %s", exc)
            voices = list(PREMADE_VOICES)
    else:
        voices = list(PREMADE_VOICES)
    filtered = filter_voices_for_book_language(voices, lang_code, BOOK_TO_ISO)
    return filtered or (voices if lang_code == "en" else [])


def default_voice_for_language(lang_code: str) -> str:
    _ = lang_code
    return DEFAULT_VOICE


def iso_language(lang: str) -> str:
    return BOOK_TO_ISO.get(lang, "en")


def fetch_subscription(api_key: str, timeout: int = 15) -> dict[str, int | str]:
    """Return usage from ElevenLabs subscription endpoint."""
    if not api_key:
        raise RuntimeError("ElevenLabs API key is missing")
    resp = requests.get(
        f"{API_BASE}/user/subscription",
        headers={"xi-api-key": api_key.strip()},
        timeout=timeout,
    )
    if resp.status_code != 200:
        detail = resp.text[:300]
        raise RuntimeError(f"ElevenLabs subscription HTTP {resp.status_code}: {detail}")
    data = resp.json()
    used = int(data.get("character_count") or 0)
    limit = int(data.get("character_limit") or 0)
    if limit <= 0:
        limit = 10_000
    return {
        "used": used,
        "limit": limit,
        "remaining": max(0, limit - used),
        "tier": str(data.get("tier") or ""),
    }


def synthesize_mp3(
    text: str,
    *,
    voice: str,
    lang: str,
    api_key: str,
    model_id: str = DEFAULT_MODEL,
    speed: float = 1.0,
    timeout: int = 120,
) -> bytes:
    text = text.strip()
    if not text:
        return b""
    if not api_key:
        raise RuntimeError("ElevenLabs API key is missing")

    voice_id = resolve_voice_id(voice or DEFAULT_VOICE, api_key)
    from .tts_speed import normalize_ui_speech_rate

    speed_value = normalize_ui_speech_rate(speed)
    url = f"{API_BASE}/text-to-speech/{voice_id}"
    payload: dict[str, object] = {
        "text": text,
        "model_id": model_id,
        "voice_settings": {
            "speed": speed_value,
        },
    }
    language_code = iso_language(lang)
    if language_code:
        payload["language_code"] = language_code

    resp = requests.post(
        url,
        headers={
            "xi-api-key": api_key.strip(),
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        },
        json=payload,
        params={"output_format": "mp3_44100_128"},
        timeout=timeout,
    )
    if resp.status_code != 200:
        detail = resp.text[:300]
        try:
            detail = resp.json().get("detail", {}).get("message", detail)
        except Exception:
            pass
        if resp.status_code == 402:
            detail = (
                "This ElevenLabs voice is not available on the free plan via API. "
                "Choose another voice in Settings → Audio (e.g. Sarah)."
            )
        raise RuntimeError(f"ElevenLabs TTS HTTP {resp.status_code}: {detail}")
    if not resp.content:
        raise RuntimeError("ElevenLabs TTS returned empty audio")
    return resp.content
