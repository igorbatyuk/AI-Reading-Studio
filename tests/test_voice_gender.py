"""Tests for localized voice gender labels."""

from src.core.i18n import set_language
from src.core.tts_voices import format_stored_voice, get_voices_for_tts_context
from src.core.voice_gender import (
    apply_gender_labels,
    detect_voice_gender,
    ensure_gender_in_label,
)


def test_edge_voice_has_gender_label_en():
    set_language("en")
    voices = get_voices_for_tts_context("en", "online", "system", online_engine="edge")
    jenny = format_stored_voice("edge", "en-US-JennyNeural")
    labels = {v[0]: v[1] for v in voices}
    assert "Female" in labels[jenny]
    guy = format_stored_voice("edge", "en-US-GuyNeural")
    assert "Male" in labels[guy]


def test_edge_voice_has_gender_label_uk():
    set_language("uk")
    voices = get_voices_for_tts_context("en", "online", "system", online_engine="edge")
    jenny = format_stored_voice("edge", "en-US-JennyNeural")
    labels = {v[0]: v[1] for v in voices}
    assert "Жіночий" in labels[jenny]
    guy = format_stored_voice("edge", "en-US-GuyNeural")
    assert "Чоловічий" in labels[guy]


def test_kokoro_gender_detection():
    bella = format_stored_voice("kokoro", "af_bella")
    adam = format_stored_voice("kokoro", "am_adam")
    assert detect_voice_gender(bella, "Kokoro — US — Bella") == "female"
    assert detect_voice_gender(adam, "Kokoro — US — Adam") == "male"


def test_piper_gender_from_model_stem():
    amy = format_stored_voice("piper", "en_US-amy-medium")
    lessac = format_stored_voice("piper", "en_US-lessac-medium")
    assert detect_voice_gender(amy, "Piper — en_US-amy-medium") == "female"
    assert detect_voice_gender(lessac, "Piper — en_US-lessac-medium") == "male"


def test_ensure_gender_replaces_english_with_localized():
    set_language("uk")
    stored = format_stored_voice("edge", "en-US-JennyNeural")
    label = ensure_gender_in_label(stored, "Edge — US — Jenny (Female)")
    assert "Жіночий" in label
    assert "Female" not in label


def test_apply_gender_labels_idempotent():
    set_language("en")
    stored = format_stored_voice("edge", "en-US-AriaNeural")
    once = apply_gender_labels([(stored, "Edge — US — Aria")])
    twice = apply_gender_labels(once)
    assert once == twice
