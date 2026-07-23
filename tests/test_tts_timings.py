"""Tests for offline TTS word timing estimation."""

import json
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


def _write_silent_wav(path: Path, *, ms: int = 2000) -> None:
    rate = 22050
    frames = int(rate * ms / 1000)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(b"\x00\x00" * frames)


def test_finalize_generates_timings_sidecar(qapp, tmp_path: Path) -> None:
    from src.core.tts_engine import TTSEngine

    tts = TTSEngine()
    tts.set_app_dir(tmp_path)
    text = "Hello world again"
    key = tts._cache_key(text)
    wav_path = tts._cache_file_path(key, ".wav")
    _write_silent_wav(wav_path, ms=3000)

    tts._finalize_generated_audio(text, key, wav_path)

    timings_path = tts._timings_path(key)
    assert timings_path.exists()
    raw = json.loads(timings_path.read_text(encoding="utf-8"))
    assert raw["estimated"] is True
    words = raw["words"]
    assert len(words) >= 3
    assert words[0][0] == 0


def test_word_timings_info_marks_estimated(qapp, tmp_path: Path) -> None:
    from src.core.tts_engine import TTSEngine

    tts = TTSEngine()
    tts.set_app_dir(tmp_path)
    text = "Hello world again"
    key = tts._cache_key(text)
    wav_path = tts._cache_file_path(key, ".wav")
    _write_silent_wav(wav_path, ms=3000)
    tts._finalize_generated_audio(text, key, wav_path)

    info = tts.word_timings_info_for(text)
    assert info is not None
    assert info.estimated is True
    assert len(info.timings) >= 3
    from src.core.tts_engine import TTSEngine

    tts = TTSEngine()
    tts.set_app_dir(tmp_path)
    text = "One two three"
    key = tts._cache_key(text)
    wav_path = tts._cache_file_path(key, ".wav")
    _write_silent_wav(wav_path, ms=2500)

    timings = tts.word_timings_for(text)
    assert timings is not None
    assert len(timings) == 3
    assert timings[-1][1] > timings[0][0]
