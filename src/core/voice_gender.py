"""Detect voice gender and ensure localized gender tags in voice labels."""

from __future__ import annotations

import re

from .tts_voices import parse_stored_voice

_GENDER_SUFFIX_RE = re.compile(
    r"\s*\(\s*(Female|Male|Neutral|Жіноч(?:ий|а)?|Чоловіч(?:ий|а)?|"
    r"Neutra[l]?|Нейтральн(?:ий|а)?)\s*\)\s*$",
    re.IGNORECASE,
)

_PIPER_FEMALE_HINTS = (
    "amy",
    "kathleen",
    "kristin",
    "hannah",
    "irina",
    "lada",
    "gosia",
    "zofia",
    "katja",
    "denise",
    "elvira",
    "elsa",
    "francisca",
    "polina",
    "svetlana",
    "pernille",
    "ukrainian",
)
_PIPER_MALE_HINTS = (
    "lessac",
    "ryan",
    "alan",
    "thorsten",
    "ruslan",
    "sharvard",
    "conrad",
    "marek",
    "duarte",
    "diego",
    "ostap",
    "dmitry",
    "finn",
)

_MURF_GENDER: dict[str, str] = {
    "natalie": "female",
    "ken": "male",
    "ariana": "female",
}

_CARTESIA_GENDER: dict[str, str] = {
    "skylar": "female",
}


def strip_gender_suffix(label: str) -> str:
    previous = None
    cleaned = label.strip()
    while cleaned != previous:
        previous = cleaned
        cleaned = _GENDER_SUFFIX_RE.sub("", cleaned).strip()
    return cleaned


def _gender_from_label_text(label: str) -> str | None:
    blob = label.lower()
    if "female" in blob or "жіноч" in blob:
        return "female"
    if "male" in blob or "чолов" in blob:
        return "male"
    if "neutral" in blob or "нейтраль" in blob:
        return "neutral"
    return None


def _gender_from_edge_raw(raw: str) -> str | None:
    from .tts_voices import _VOICES_BY_ID

    voice = _VOICES_BY_ID.get(raw)
    if voice:
        return "female" if voice.gender == "Female" else "male"
    return None


def _gender_from_kokoro_raw(raw: str) -> str | None:
    if raw.startswith(("af_", "bf_", "ff_", "jf_", "zf_", "if_")):
        return "female"
    if raw.startswith(("am_", "bm_", "jm_", "zm_", "im_")):
        return "male"
    return None


def _gender_from_piper_stem(stem: str) -> str | None:
    lower = stem.lower()
    for hint in _PIPER_FEMALE_HINTS:
        if hint in lower:
            return "female"
    for hint in _PIPER_MALE_HINTS:
        if hint in lower:
            return "male"
    return None


def _gender_from_neural_id(raw: str) -> str | None:
    if "Neural2-F" in raw or raw.endswith("-F"):
        return "female"
    if "Neural2-D" in raw or raw.endswith("-D") or raw.endswith("-B"):
        return "male"
    if "Wavenet-A" in raw or raw.endswith("-A"):
        return "female"
    if "Wavenet-B" in raw or raw.endswith("-B"):
        return "male"
    if "Standard-A" in raw:
        return "female"
    return None


def detect_voice_gender(stored_voice_id: str, label: str) -> str | None:
    """Return ``female``, ``male``, ``neutral``, or ``None`` if unknown."""
    from_label = _gender_from_label_text(label)
    if from_label:
        return from_label

    engine, raw = parse_stored_voice(stored_voice_id)

    if engine == "edge":
        return _gender_from_edge_raw(raw)
    if engine in ("azure", "google"):
        gender = _gender_from_neural_id(raw)
        if gender:
            return gender
        return _gender_from_edge_raw(raw)
    if engine == "kokoro":
        return _gender_from_kokoro_raw(raw)
    if engine == "piper":
        return _gender_from_piper_stem(raw)
    if engine == "murf":
        key = raw.lower()
        if key in _MURF_GENDER:
            return _MURF_GENDER[key]
        return _gender_from_label_text(raw)
    if engine == "cartesia":
        name = label.split("—")[0].split("(")[0].strip().lower()
        for key, gender in _CARTESIA_GENDER.items():
            if key in name or key in raw.lower():
                return gender
    if engine == "elevenlabs":
        return _gender_from_label_text(label)
    return None


def gender_label(gender: str) -> str:
    from .i18n import tr

    if gender == "female":
        return tr("voice.gender.female")
    if gender == "male":
        return tr("voice.gender.male")
    if gender == "neutral":
        return tr("voice.gender.neutral")
    return ""


def ensure_gender_in_label(stored_voice_id: str, label: str) -> str:
    """Append localized gender tag when it can be inferred."""
    engine, _raw = parse_stored_voice(stored_voice_id)
    if engine == "system":
        return label

    gender = detect_voice_gender(stored_voice_id, label)
    if not gender:
        return label

    clean = strip_gender_suffix(label)
    tag = gender_label(gender)
    if not tag:
        return label
    if clean.endswith(f"({tag})"):
        return clean
    return f"{clean} ({tag})"


def apply_gender_labels(voices: list[tuple[str, str]]) -> list[tuple[str, str]]:
    return [
        (stored, ensure_gender_in_label(stored, label))
        for stored, label in voices
    ]
