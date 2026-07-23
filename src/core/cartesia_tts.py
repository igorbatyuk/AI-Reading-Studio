"""Cartesia Text-to-Speech API client."""

from __future__ import annotations

import logging
import time

import requests

logger = logging.getLogger(__name__)

API_BASE = "https://api.cartesia.ai"
API_VERSION = "2026-03-01"
DEFAULT_MODEL = "sonic-3.5"
DEFAULT_VOICE = "db6b0ed5-d5d3-463d-ae85-518a07d3c2b4"  # Skylar — Friendly Guide

# Public voices from Cartesia voice library (fallback without API key).
DEFAULT_VOICES: list[tuple[str, str]] = [
    (DEFAULT_VOICE, "Skylar — Friendly Guide (EN)"),
    ("f786b574-daa5-4673-aa0c-cbe3e8534c02", "Sonic default (EN)"),
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


def _api_headers(api_key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key.strip()}",
        "Cartesia-Version": API_VERSION,
        "Content-Type": "application/json",
    }


def iso_language(lang: str) -> str | None:
    code = BOOK_TO_ISO.get(lang, lang)
    return code or None


def fetch_voices(
    api_key: str, timeout: int = 15, *, force: bool = False
) -> list[tuple[str, str]]:
    """Return voices from Cartesia API (cached)."""
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

    voices: list[tuple[str, str]] = []
    starting_after: str | None = None
    while True:
        params: dict[str, str | int] = {"limit": 100}
        if starting_after:
            params["starting_after"] = starting_after
        resp = requests.get(
            f"{API_BASE}/voices",
            headers=_api_headers(api_key),
            params=params,
            timeout=timeout,
        )
        if resp.status_code != 200:
            detail = resp.text[:300]
            raise RuntimeError(f"Cartesia voices HTTP {resp.status_code}: {detail}")

        payload = resp.json()
        batch = payload.get("data") or []
        for item in batch:
            voice_id = str(item.get("id") or "").strip()
            name = str(item.get("name") or voice_id).strip()
            language = str(item.get("language") or "en").strip().upper()
            if voice_id:
                voices.append((voice_id, f"{name} ({language})"))
        if not payload.get("has_more"):
            break
        starting_after = str(payload.get("next_page") or "").strip() or None
        if not starting_after:
            break

    if not voices:
        voices = list(DEFAULT_VOICES)
    _voices_cache = (now, voices)
    return list(voices)


def list_voices_for_language(lang_code: str, api_key: str = "") -> list[tuple[str, str]]:
    from .tts_voices import filter_voices_for_book_language

    if api_key:
        try:
            voices = fetch_voices(api_key)
        except Exception as exc:
            logger.debug("Cartesia voice list fetch failed: %s", exc)
            voices = list(DEFAULT_VOICES)
    else:
        voices = list(DEFAULT_VOICES)
    filtered = filter_voices_for_book_language(voices, lang_code, BOOK_TO_ISO)
    return filtered or (voices if lang_code == "en" else [])


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
                    "Cartesia voice %s unavailable; using %s", cleaned, DEFAULT_VOICE
                )
                return DEFAULT_VOICE
            return cleaned
        except Exception as exc:
            logger.debug("Cartesia voice resolve fetch failed: %s", exc)
    if cleaned not in {voice_id for voice_id, _label in DEFAULT_VOICES}:
        return DEFAULT_VOICE
    return cleaned


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
    from .tts_speed import cartesia_generation_speed

    text = text.strip()
    if not text:
        return b""
    if not api_key:
        raise RuntimeError("Cartesia API key is missing")

    voice_id = resolve_voice_id(voice or DEFAULT_VOICE, api_key)
    payload: dict[str, object] = {
        "model_id": model_id,
        "transcript": text,
        "voice": {"mode": "id", "id": voice_id},
        "output_format": {
            "container": "mp3",
            "sample_rate": 44100,
            "bit_rate": 128000,
        },
        "generation_config": {
            "speed": cartesia_generation_speed(speed),
        },
    }
    language = iso_language(lang)
    if language:
        payload["language"] = language

    resp = requests.post(
        f"{API_BASE}/tts/bytes",
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
        raise RuntimeError(f"Cartesia TTS HTTP {resp.status_code}: {detail}")
    if not resp.content:
        raise RuntimeError("Cartesia TTS returned empty audio")
    return resp.content
