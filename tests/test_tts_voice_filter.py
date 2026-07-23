"""Tests for cloud voice list language filtering."""

from src.core import cartesia_tts, elevenlabs_tts
from src.core.tts_voices import filter_voices_for_book_language


def test_filter_voices_for_book_language():
    voices = [
        ("a", "Sarah (EN)"),
        ("b", "Polina (UK)"),
        ("c", "Skylar (EN)"),
    ]
    en = filter_voices_for_book_language(voices, "en", elevenlabs_tts.BOOK_TO_ISO)
    uk = filter_voices_for_book_language(voices, "uk", elevenlabs_tts.BOOK_TO_ISO)
    assert [v[0] for v in en] == ["a", "c"]
    assert [v[0] for v in uk] == ["b"]


def test_cartesia_list_voices_filters_non_english():
    voices = cartesia_tts.list_voices_for_language(
        "uk",
        api_key="",
    )
    assert voices == []


def test_elevenlabs_list_defaults_english_only():
    voices = elevenlabs_tts.list_voices_for_language("de")
    assert voices == []
