"""Tests for media_duration helpers."""

import wave
from pathlib import Path

from src.core.media_duration import media_duration_ms


def _write_silent_wav(path: Path, *, rate: int = 22050, seconds: float = 2.0) -> None:
    frames = int(rate * seconds)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(b"\x00\x00" * frames)


def test_wav_duration_ms(tmp_path: Path) -> None:
    wav_path = tmp_path / "sample.wav"
    _write_silent_wav(wav_path, rate=1000, seconds=1.5)
    assert media_duration_ms(wav_path) == 1500


def test_unknown_extension_returns_zero(tmp_path: Path) -> None:
    path = tmp_path / "note.txt"
    path.write_text("hello", encoding="utf-8")
    assert media_duration_ms(path) == 0


def test_invalid_wav_returns_zero(tmp_path: Path) -> None:
    path = tmp_path / "bad.wav"
    path.write_bytes(b"not-a-wav")
    assert media_duration_ms(path) == 0
