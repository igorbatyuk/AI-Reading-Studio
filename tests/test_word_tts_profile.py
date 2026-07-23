"""Tests for separate word TTS profile."""

from src.core.tts_engine import TTSEngine
from src.core.tts_voices import format_stored_voice


def test_word_context_uses_custom_settings():
    tts = TTSEngine(format_stored_voice("elevenlabs", "21m00Tcm4TlvDq8ikWAM"))
    tts.set_mode("online")
    tts.set_online_engine("elevenlabs")
    tts.set_elevenlabs_api_key("sk-test")
    tts.set_word_tts_settings(
        "custom",
        format_stored_voice("edge", "en-US-AriaNeural"),
        "online",
        "edge",
        "system",
    )
    main = tts._main_context()
    word = tts._word_context()
    assert main.online_engine == "elevenlabs"
    assert word.online_engine == "edge"
    assert word.voice.startswith("edge:")


def test_word_cache_key_differs_from_main():
    tts = TTSEngine(format_stored_voice("edge", "en-US-AriaNeural"))
    tts.set_word_tts_settings(
        "custom",
        format_stored_voice("edge", "en-US-GuyNeural"),
        "online",
        "edge",
        "system",
    )
    main_key = tts._cache_key("hello")
    word_key = tts._cache_key("hello", for_word=True)
    assert main_key != word_key


def test_prefetch_allowed_for_custom_edge_words():
    tts = TTSEngine(format_stored_voice("elevenlabs", "21m00Tcm4TlvDq8ikWAM"))
    tts.set_mode("online")
    tts.set_online_engine("elevenlabs")
    tts.set_elevenlabs_api_key("sk-test")
    tts.set_word_tts_settings(
        "custom",
        format_stored_voice("edge", "en-US-AriaNeural"),
        "online",
        "edge",
        "system",
    )
    assert tts.should_prefetch_words() is True
