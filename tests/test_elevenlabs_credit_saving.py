"""Tests for ElevenLabs credit-saving behavior."""

from src.core.tts_engine import TTSEngine


def test_skips_word_prefetch_for_elevenlabs_online():
    tts = TTSEngine("elevenlabs:21m00Tcm4TlvDq8ikWAM")
    tts.set_mode("online")
    tts.set_online_engine("elevenlabs")
    tts.set_elevenlabs_api_key("sk-test")
    assert tts.should_prefetch_words() is False


def test_allows_word_prefetch_for_edge_online():
    tts = TTSEngine("edge:en-US-AriaNeural")
    tts.set_mode("online")
    tts.set_online_engine("edge")
    assert tts.should_prefetch_words() is True
