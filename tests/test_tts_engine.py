"""Tests for TTS cache and generating state."""

from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_is_cached_false_for_new_text(qapp, tmp_path):
    from src.core.tts_engine import TTSEngine

    tts = TTSEngine()
    tts.set_app_dir(tmp_path)
    assert tts.is_cached("Hello world test phrase") is False


def test_pause_resume_without_playback(qapp):
    from src.core.tts_engine import TTSEngine

    tts = TTSEngine()
    assert tts.pause() is False
    assert tts.resume() is False
    assert tts.can_resume() is False


def test_generating_counter(qapp, tmp_path):
    from src.core.tts_engine import TTSEngine

    tts = TTSEngine()
    tts.set_app_dir(tmp_path)
    assert tts.is_generating() is False
    tts._generating_begin()
    assert tts.is_generating() is True
    tts._generating_begin()
    assert tts.is_generating() is True
    tts._generating_end()
    assert tts.is_generating() is True
    tts._generating_end()
    assert tts.is_generating() is False


def test_playback_rate_cycle(qapp):
    from src.core.tts_engine import TTSEngine

    tts = TTSEngine()
    assert tts.playback_rate() == 1.0
    assert tts.cycle_playback_rate() == 1.25
    assert tts.cycle_playback_rate() == 1.5
    tts.set_playback_rate(2.0)
    assert tts.cycle_playback_rate() == 1.0
    assert tts.cycle_playback_rate() == 1.25
    assert tts.cycle_playback_rate() == 1.5


def test_playback_rate_clamps_slow_values(qapp):
    from src.core.tts_engine import TTSEngine

    tts = TTSEngine()
    tts.set_playback_rate(0.5)
    assert tts.playback_rate() == 1.0


def test_generation_speed_in_cache_prefix(qapp, tmp_path):
    from src.core.tts_engine import TTSEngine

    tts = TTSEngine()
    tts.set_app_dir(tmp_path)
    tts.set_speed(0.25)
    key_slow = tts._cache_key("hello")
    tts.set_speed(1.0)
    key_normal = tts._cache_key("hello")
    tts.set_speed(1.5)
    key_fast = tts._cache_key("hello")
    assert key_slow != key_normal != key_fast


def test_restart_and_rewind_without_playback(qapp):
    from src.core.tts_engine import TTSEngine

    tts = TTSEngine()
    assert tts.can_control_playback() is False
    assert tts.restart_playback() is False
    assert tts.rewind_playback() is False


def test_prefetch_words_queues_uncached(qapp, tmp_path, monkeypatch):
    from src.core.tts_engine import TTSEngine

    tts = TTSEngine()
    tts.set_app_dir(tmp_path)
    prefetched: list[str] = []

    def fake_prefetch(text: str, for_word: bool = False) -> None:
        prefetched.append(text)

    monkeypatch.setattr(tts, "prefetch", fake_prefetch)
    monkeypatch.setattr(tts, "is_cached", lambda _text, for_word=False: False)

    tts.prefetch_words("Hello brave world")
    import time

    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline and not prefetched:
        qapp.processEvents()
        time.sleep(0.02)

    assert "hello" in prefetched
    assert "brave" in prefetched
    assert "world" in prefetched


def test_speak_word_uses_existing_cache(qapp, tmp_path):
    from src.core.tts_engine import TTSEngine

    tts = TTSEngine()
    tts.set_app_dir(tmp_path)
    key = tts._cache_key("hello")
    path = tts._cache_file_path(key, ".mp3")
    path.write_bytes(b"fake")
    tts._audio_cache[key] = path

    played: list[str] = []
    tts._word_play_request.connect(lambda p: played.append(p))

    tts.speak_word("hello")
    qapp.processEvents()

    assert played == [str(path)]


def test_stale_speak_worker_does_not_play(qapp, tmp_path, monkeypatch):
    import threading
    import time

    from src.core.tts_engine import TTSEngine

    tts = TTSEngine()
    tts.set_app_dir(tmp_path)
    played: list[str] = []
    tts._play_request.connect(lambda path, _advance: played.append(path))
    gate = threading.Event()

    def slow_generate(text: str, key: str, ctx) -> Path:
        gate.wait(timeout=2.0)
        path = tts._cache_file_path(key, ".wav")
        path.write_bytes(b"RIFF")
        return path

    monkeypatch.setattr(tts, "_generate_audio", slow_generate)

    tts.speak("first block text")
    second_key = tts._cache_key("second block text")
    second_path = tts._cache_file_path(second_key, ".wav")
    second_path.write_bytes(b"RIFF2")
    tts._audio_cache[second_key] = second_path

    tts.speak("second block text")
    gate.set()

    deadline = time.monotonic() + 3.0
    while time.monotonic() < deadline and len(played) < 1:
        qapp.processEvents()
        time.sleep(0.02)

    assert played == [str(second_path)]
