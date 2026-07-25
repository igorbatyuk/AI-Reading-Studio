"""Curated voice ordering for book reading."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from .tts_voices import parse_stored_voice

if TYPE_CHECKING:
    from .voice_sort_prefs import VoiceSortPrefs

# Raw voice ids / substrings per engine and book language (first = best for reading).
RECOMMENDED_RAW: dict[str, dict[str, list[str]]] = {
    "edge": {
        "en": [
            "en-US-JennyNeural",
            "en-US-AriaNeural",
            "en-US-GuyNeural",
            "en-GB-SoniaNeural",
            "en-US-EmmaNeural",
            "en-GB-LibbyNeural",
            "en-GB-RyanNeural",
            "en-US-AndrewNeural",
        ],
        "uk": ["uk-UA-PolinaNeural", "uk-UA-OstapNeural"],
        "ru": ["ru-RU-SvetlanaNeural", "ru-RU-DmitryNeural"],
        "de": ["de-DE-KatjaNeural", "de-DE-ConradNeural"],
        "fr": ["fr-FR-DeniseNeural", "fr-FR-HenriNeural"],
        "es": ["es-ES-ElviraNeural", "es-ES-AlvaroNeural"],
        "it": ["it-IT-ElsaNeural", "it-IT-DiegoNeural"],
        "pl": ["pl-PL-ZofiaNeural", "pl-PL-MarekNeural"],
        "pt": ["pt-BR-FranciscaNeural", "pt-BR-AntonioNeural"],
        "nl": ["nl-NL-ColetteNeural", "nl-NL-MaartenNeural"],
        "nb": ["nb-NO-PernilleNeural", "nb-NO-FinnNeural"],
    },
    "azure": {
        "en": [
            "en-US-JennyNeural",
            "en-US-AriaNeural",
            "en-US-GuyNeural",
            "en-GB-SoniaNeural",
        ],
        "uk": ["uk-UA-PolinaNeural"],
        "de": ["de-DE-KatjaNeural"],
        "fr": ["fr-FR-DeniseNeural"],
        "es": ["es-ES-ElviraNeural"],
        "pl": ["pl-PL-ZofiaNeural"],
    },
    "google": {
        "en": [
            "en-US-Neural2-F",
            "en-US-Neural2-D",
            "en-GB-Neural2-F",
        ],
        "uk": ["uk-UA-Wavenet-A"],
        "de": ["de-DE-Neural2-F"],
        "fr": ["fr-FR-Neural2-A"],
        "es": ["es-ES-Neural2-A"],
        "pl": ["pl-PL-Wavenet-A"],
    },
    "kokoro": {
        "en": ["af_bella", "af_sarah", "af_heart", "af_nova", "am_adam"],
        "fr": ["ff_siwis"],
        "it": ["if_sara", "im_nicola"],
        "ja": ["jf_alpha"],
        "zh": ["zf_xiaoxiao", "zm_yunxi"],
    },
    "elevenlabs": {
        "en": [
            "EXAVITQu4vr4xnSDxMaL",  # Sarah
            "FGY2WhTYpPnrIDTdsKH5",  # Laura
            "Xb7hH8MSUJpSbSDYk0k2",  # Alice
            "bIHbv24MWmeRgasZH58o",  # Will
            "onwK4e9ZLuTAKqWW03F9",  # Daniel
        ],
    },
    "cartesia": {
        "en": [
            "db6b0ed5-d5d3-463d-ae85-518a07d3c2b4",  # Skylar
        ],
    },
    "murf": {
        "en": ["Natalie", "Ken", "Ariana"],
    },
}

# Piper / StyleTTS2 / XTTS — match substrings in model stem (lower case).
RECOMMENDED_SUBSTRINGS: dict[str, dict[str, list[str]]] = {
    "piper": {
        "en": ["lessac-medium", "amy-medium", "ryan-medium", "alan-medium"],
        "uk": ["ukrainian_tts-medium", "uk_ua"],
        "de": ["-medium"],
        "fr": ["-medium"],
        "es": ["-medium"],
        "pl": ["-medium"],
    },
}

_UNSUITABLE_RAW_SUFFIXES = (
    "MultilingualNeural",
    "Multilingual",
    "ExpressiveNeural",
    "Expressive",
)

_UNSUITABLE_RAW_EXACT = frozenset(
    {
        "en-US-AnaNeural",  # child voice
    }
)

_UNSUITABLE_LABEL_RE = re.compile(
    r"multilingual|expressive|\bchild\b|\bx_low\b",
    re.IGNORECASE,
)

_UNSUITABLE_STEM_RE = re.compile(r"x_low|x-low", re.IGNORECASE)

_RECOMMENDED_BADGE = "★ "


def _engine_from_stored(stored_voice_id: str) -> str:
    engine, _raw = parse_stored_voice(stored_voice_id)
    return engine


def _raw_from_stored(stored_voice_id: str) -> str:
    _engine, raw = parse_stored_voice(stored_voice_id)
    return raw


def is_unsuitable_for_reading(
    stored_voice_id: str,
    label: str,
    *,
    engine: str | None = None,
) -> bool:
    """Voices to deprioritize/hide for long-form book reading."""
    engine = engine or _engine_from_stored(stored_voice_id)
    raw = _raw_from_stored(stored_voice_id)

    if raw in _UNSUITABLE_RAW_EXACT:
        return True
    if any(marker in raw for marker in _UNSUITABLE_RAW_SUFFIXES):
        return True
    if _UNSUITABLE_LABEL_RE.search(label):
        return True
    if engine == "piper" and _UNSUITABLE_STEM_RE.search(raw):
        return True
    return False


def _recommended_index(
    engine: str,
    lang_code: str,
    raw: str,
    label: str,
) -> int | None:
    exact = RECOMMENDED_RAW.get(engine, {}).get(lang_code, [])
    if raw in exact:
        return exact.index(raw)

    substrings = RECOMMENDED_SUBSTRINGS.get(engine, {}).get(lang_code, [])
    raw_lower = raw.lower()
    label_lower = label.lower()
    for index, needle in enumerate(substrings):
        n = needle.lower()
        if n in raw_lower or n in label_lower:
            return index

    # Azure/Google often mirror Edge ids.
    if engine in ("azure", "google"):
        edge_list = RECOMMENDED_RAW.get("edge", {}).get(lang_code, [])
        if raw in edge_list:
            return edge_list.index(raw)

    # ElevenLabs / Murf — match display name in label when id unknown.
    if engine == "elevenlabs":
        for index, voice_id in enumerate(
            RECOMMENDED_RAW.get("elevenlabs", {}).get(lang_code, [])
        ):
            if voice_id == raw:
                return index
    if engine == "murf":
        for index, name in enumerate(RECOMMENDED_RAW.get("murf", {}).get(lang_code, [])):
            if name.lower() in label.lower():
                return index

    return None


def _region_boost(lang_code: str, raw: str, label: str, region_pref: str) -> int:
    if lang_code != "en":
        return 0
    blob = f"{raw} {label}".upper()
    if region_pref == "any":
        if "EN-US" in blob or " US " in blob or blob.startswith("US "):
            return 3
        if "EN-GB" in blob or " UK " in blob or "(UK)" in label.upper():
            return 2
        if "EN-AU" in blob or " AU " in blob:
            return 1
        return 0
    if region_pref == "us":
        if "EN-US" in blob or " US " in blob or blob.startswith("US "):
            return 3
        return 0
    if region_pref == "uk":
        if "EN-GB" in blob or " UK " in blob or "(UK)" in label.upper():
            return 3
        return 0
    if region_pref == "au":
        if "EN-AU" in blob or " AU " in blob:
            return 3
        return 0
    return 0


def _gender_sort_rank(label: str, raw: str, gender_pref: str) -> int:
    from .voice_sort_prefs import GENDER_FEMALE, GENDER_MALE, GENDER_MIX

    if gender_pref == GENDER_MIX:
        return 0
    is_female = (
        "Female" in label
        or "Жіноч" in label
        or raw.startswith(("af_", "bf_", "ff_", "jf_", "zf_", "if_"))
    )
    is_male = (
        "Male" in label
        or "Чолов" in label
        or raw.startswith(("am_", "bm_", "jm_", "zm_", "im_"))
    )
    if gender_pref == GENDER_FEMALE:
        if is_female:
            return 0
        if is_male:
            return 1
        return 2
    if gender_pref == GENDER_MALE:
        if is_male:
            return 0
        if is_female:
            return 1
        return 2
    return 0


def _quality_boost(engine: str, raw: str, label: str) -> int:
    score = 0
    if engine == "piper":
        stem = raw.lower()
        if "medium" in stem:
            score += 4
        if "lessac" in stem or "amy" in stem or "ukrainian_tts" in stem:
            score += 6
        if _UNSUITABLE_STEM_RE.search(stem):
            score -= 20
    return score


def voice_reading_sort_key(
    stored_voice_id: str,
    label: str,
    lang_code: str,
    *,
    gender_pref: str = "female",
    region_pref: str = "us",
    preset: str = "book",
) -> tuple[int, int, int, int, int, str]:
    """Sort key: lower tuple = earlier in list (better for reading)."""
    from .voice_sort_prefs import PRESET_NEWS, REGION_ANY, REGION_AU, REGION_UK, REGION_US

    engine = _engine_from_stored(stored_voice_id)
    raw = _raw_from_stored(stored_voice_id)

    unsuitable = 1 if is_unsuitable_for_reading(stored_voice_id, label, engine=engine) else 0

    rec = _recommended_index(engine, lang_code, raw, label)
    rec_rank = rec if rec is not None else 999

    region = -_region_boost(lang_code, raw, label, region_pref)
    gender = _gender_sort_rank(label, raw, gender_pref)
    quality = -_quality_boost(engine, raw, label)

    use_region_first = (
        lang_code == "en"
        and region_pref in (REGION_US, REGION_UK, REGION_AU)
    )
    if preset == PRESET_NEWS:
        return (unsuitable, gender, rec_rank, region, quality, label.lower())
    if use_region_first:
        return (unsuitable, region, rec_rank, gender, quality, label.lower())
    return (unsuitable, rec_rank, region, gender, quality, label.lower())


def _apply_custom_order(
    voices: list[tuple[str, str]],
    engine: str,
    custom_order: dict[str, list[str]],
) -> list[tuple[str, str]]:
    order = custom_order.get(engine, [])
    if not order:
        return voices
    by_id = dict(voices)
    result: list[tuple[str, str]] = []
    seen: set[str] = set()
    for stored_id in order:
        if stored_id in by_id:
            result.append((stored_id, by_id[stored_id]))
            seen.add(stored_id)
    for stored_id, label in voices:
        if stored_id not in seen:
            result.append((stored_id, label))
    return result


def _strip_recommended_badge(label: str) -> str:
    if label.startswith(_RECOMMENDED_BADGE):
        return label[len(_RECOMMENDED_BADGE) :]
    return label


def _decorate_recommended_badges(
    voices: list[tuple[str, str]],
    lang_code: str,
    *,
    show_badge: bool,
) -> list[tuple[str, str]]:
    if not show_badge:
        return voices
    result: list[tuple[str, str]] = []
    for stored, label in voices:
        clean = _strip_recommended_badge(label)
        engine = _engine_from_stored(stored)
        raw = _raw_from_stored(stored)
        if _recommended_index(engine, lang_code, raw, clean) is not None:
            result.append((stored, f"{_RECOMMENDED_BADGE}{clean}"))
        else:
            result.append((stored, clean))
    return result


def sort_voices_for_reading(
    voices: list[tuple[str, str]],
    lang_code: str,
    engine: str,
    prefs: VoiceSortPrefs | None = None,
) -> list[tuple[str, str]]:
    """
    Reorder voices for book reading: recommended narrators first, unsuitable last/hidden.

    Does not remove the user's current voice — if filtering would empty the list,
    returns the original list unchanged.
    """
    if not voices:
        return []

    from .voice_sort_prefs import PRESET_CUSTOM, VoiceSortPrefs

    effective = (prefs or VoiceSortPrefs()).effective()
    engine_key = engine or "edge"

    sorted_voices = sorted(
        voices,
        key=lambda item: voice_reading_sort_key(
            item[0],
            _strip_recommended_badge(item[1]),
            lang_code,
            gender_pref=effective.gender_pref,
            region_pref=effective.region_pref,
            preset=effective.preset,
        ),
    )

    if effective.preset == PRESET_CUSTOM:
        sorted_voices = _apply_custom_order(
            sorted_voices, engine_key, effective.custom_order
        )

    if effective.hide_unsuitable:
        filtered = [
            item
            for item in sorted_voices
            if not is_unsuitable_for_reading(
                item[0],
                _strip_recommended_badge(item[1]),
                engine=_engine_from_stored(item[0]),
            )
        ]
        if filtered:
            sorted_voices = filtered

    return _decorate_recommended_badges(
        sorted_voices,
        lang_code,
        show_badge=effective.show_recommended_badge,
    )
