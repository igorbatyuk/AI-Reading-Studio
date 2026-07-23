"""Cartesia word prefetch should be disabled to save credits."""

from src.core.tts_engine import TTSEngine


def test_cartesia_skips_word_prefetch(qapp):
    tts = TTSEngine()
    tts.set_mode("online")
    tts.set_online_engine("cartesia")
    tts.set_cartesia_api_key("sk_car_test")
    assert tts.should_prefetch_words() is False
    assert tts.should_prefetch_blocks() is False


def test_cartesia_auto_allows_block_prefetch(qapp):
    tts = TTSEngine()
    tts.set_mode("auto")
    tts.set_cartesia_api_key("sk_car_test")
    assert tts.should_prefetch_blocks() is True
    assert tts.should_prefetch_words() is True


def test_edge_allows_word_prefetch(qapp):
    tts = TTSEngine()
    tts.set_mode("online")
    tts.set_online_engine("edge")
    assert tts.should_prefetch_words() is True
