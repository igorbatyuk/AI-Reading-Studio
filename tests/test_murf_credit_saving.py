"""Murf word prefetch should be disabled to save characters."""

from src.core.tts_engine import TTSEngine


def test_murf_skips_word_prefetch(qapp):
    tts = TTSEngine()
    tts.set_mode("online")
    tts.set_online_engine("murf")
    tts.set_murf_api_key("test-key")
    assert tts.should_prefetch_words() is False
