"""Tests for speech-rate mapping and playback clamp."""

import pytest

from src.core.tts_speed import (
    PLAYBACK_RATES,
    clamp_playback_rate,
    edge_rate_string,
    engine_speech_rate,
    kokoro_speech_rate,
    piper_length_scale,
)


def test_playback_rates_accelerate_only():
    assert PLAYBACK_RATES == (1.0, 1.25, 1.5, 1.75, 2.0)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (0.5, 1.0),
        (0.75, 1.0),
        (1.0, 1.0),
        (1.5, 1.5),
        (3.0, 2.0),
    ],
)
def test_clamp_playback_rate(raw: float, expected: float):
    assert clamp_playback_rate(raw) == expected


def test_engine_speech_rate_stronger_slow_down():
    assert engine_speech_rate(1.0) == 1.0
    assert engine_speech_rate(2.0) == 2.0
    assert engine_speech_rate(0.25) < 0.35
    assert engine_speech_rate(0.5) < 0.5


def test_kokoro_speech_rate_floor():
    assert kokoro_speech_rate(0.25) == 0.5
    assert kokoro_speech_rate(1.0) == 1.0
    assert kokoro_speech_rate(0.8) < 0.8


def test_piper_length_scale_increases_when_slower():
    normal = piper_length_scale(1.0)
    slow = piper_length_scale(0.25)
    assert slow > normal
    assert slow <= 4.5


def test_edge_rate_string_includes_new_slow_values():
    assert edge_rate_string(0.25) == "-50%"
    assert edge_rate_string(0.6) == "-40%"


def test_edge_rate_string_clamps_slow_to_fifty_percent():
    assert edge_rate_string(0.25) == "-50%"
    assert edge_rate_string(0.5) == "-50%"
    assert edge_rate_string(0.6) == "-40%"


def test_google_speaking_rate_uses_ui_value():
    from src.core.tts_speed import google_speaking_rate

    assert google_speaking_rate(0.25) == 0.25
    assert google_speaking_rate(1.0) == 1.0


def test_elevenlabs_voice_speed_mapping():
    from src.core.tts_speed import elevenlabs_voice_speed

    assert elevenlabs_voice_speed(1.0) == 1.0
    assert elevenlabs_voice_speed(0.25) == 0.25
    assert elevenlabs_voice_speed(2.0) == 2.0


def test_cartesia_generation_speed_mapping():
    from src.core.tts_speed import cartesia_generation_speed

    assert cartesia_generation_speed(0.25) == 0.6
    assert cartesia_generation_speed(1.0) == 1.0
    assert cartesia_generation_speed(2.0) == 1.5
