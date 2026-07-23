"""Tests for voice preview samples."""

from src.core.tts_voices import voice_preview_sample


def test_voice_preview_sample_uk():
    text = voice_preview_sample("uk")
    assert "Привіт" in text
    assert len(text) < 120


def test_voice_preview_sample_fallback():
    text = voice_preview_sample("unknown")
    assert "Hello" in text
