"""Playback intent prevents audio starting while UI is paused."""

import wave
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _write_silent_wav(path: Path, *, ms: int = 500) -> None:
    rate = 22050
    frames = int(rate * ms / 1000)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(b"\x00\x00" * frames)


def test_held_playback_when_paused_intent(qapp, tmp_path: Path) -> None:
    from src.core.tts_engine import TTSEngine

    tts = TTSEngine()
    tts.set_app_dir(tmp_path)
    text = "Hello paused playback"
    key = tts._cache_key(text)
    wav_path = tts._cache_file_path(key, ".wav")
    _write_silent_wav(wav_path, ms=800)
    tts._audio_cache[key] = wav_path

    tts.set_playback_intent(active=True, paused=True)
    tts.speak(text)
    qapp.processEvents()

    assert tts._held_playback is True
    assert tts._current_file == wav_path
    assert tts.can_resume() is True


def test_preview_enables_playback_intent(qapp, monkeypatch):
    from src.core.tts_engine import TTSEngine

    tts = TTSEngine()
    tts.set_playback_intent(active=False, paused=False)
    monkeypatch.setattr(tts, "speak", lambda *_a, **_k: None)
    tts.preview("hello")
    assert tts._playback_active is True
    assert tts._playback_paused is False
    assert tts._held_playback is False


def test_resume_after_held_playback(qapp, tmp_path: Path) -> None:
    from src.core.tts_engine import TTSEngine

    tts = TTSEngine()
    tts.set_app_dir(tmp_path)
    text = "Resume after hold"
    key = tts._cache_key(text)
    wav_path = tts._cache_file_path(key, ".wav")
    _write_silent_wav(wav_path, ms=800)
    tts._audio_cache[key] = wav_path

    tts.set_playback_intent(active=True, paused=True)
    tts.speak(text)
    qapp.processEvents()
    assert tts._held_playback is True

    tts.set_playback_intent(active=True, paused=False)
    assert tts.resume() is True
    assert tts._held_playback is False
