"""Read audio file duration without playing it."""

from __future__ import annotations

import struct
import wave
from pathlib import Path


def media_duration_ms(path: Path) -> int:
    suffix = path.suffix.lower()
    if suffix == ".wav":
        return _wav_duration_ms(path)
    if suffix == ".mp3":
        return _mp3_duration_ms(path)
    return 0


def _wav_duration_ms(path: Path) -> int:
    try:
        with wave.open(str(path), "rb") as handle:
            rate = handle.getframerate()
            if rate <= 0:
                return 0
            return int(1000 * handle.getnframes() / rate)
    except (OSError, EOFError, wave.Error):
        return 0


def _mp3_duration_ms(path: Path) -> int:
    try:
        from mutagen.mp3 import MP3

        return int(MP3(path).info.length * 1000)
    except ImportError:
        return _mp3_duration_ms_fallback(path)
    except Exception:
        return _mp3_duration_ms_fallback(path)


def _mp3_duration_ms_fallback(path: Path) -> int:
    """Estimate MP3 length from frame headers when mutagen is unavailable."""
    try:
        data = path.read_bytes()
    except OSError:
        return 0
    offset = 0
    total_samples = 0
    sample_rate = 0
    while offset + 4 < len(data):
        if data[offset] != 0xFF or (data[offset + 1] & 0xE0) != 0xE0:
            offset += 1
            continue
        header = struct.unpack(">I", b"\x00" + data[offset : offset + 3])[0]
        version = (header >> 19) & 3
        layer = (header >> 17) & 3
        bitrate_index = (header >> 12) & 0xF
        sample_index = (header >> 10) & 3
        if layer != 1 or bitrate_index == 0 or bitrate_index == 15 or sample_index == 3:
            offset += 1
            continue
        bitrates = {
            3: [0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, 0],
            2: [0, 32, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, 384, 0],
            0: [0, 32, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, 384, 0],
        }
        sample_rates = {
            3: [44100, 48000, 32000, 0],
            2: [22050, 24000, 16000, 0],
            0: [11025, 12000, 8000, 0],
        }
        bitrate = bitrates.get(version, bitrates[3])[bitrate_index] * 1000
        sample_rate = sample_rates.get(version, sample_rates[3])[sample_index]
        padding = 1 if (header >> 9) & 1 else 0
        if version == 3:
            frame_len = int(144000 * bitrate / sample_rate) + padding
            samples = 1152
        else:
            frame_len = int(72000 * bitrate / sample_rate) + padding
            samples = 576
        if frame_len <= 0:
            offset += 1
            continue
        total_samples += samples
        offset += frame_len
    if sample_rate <= 0:
        return 0
    return int(1000 * total_samples / sample_rate)
