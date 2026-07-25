"""Tests for Murf TTS client and usage."""

from pathlib import Path

import pytest

from src.core import murf_tts
from src.core.database import Database
from src.core.murf_tts_usage import FREE_MONTHLY_CHAR_LIMIT, MurfTTSUsage


@pytest.fixture
def db(tmp_path: Path) -> Database:
    return Database(tmp_path / "test.db")


def test_list_voices_fallback():
    voices = murf_tts.list_voices_for_language("en")
    assert voices
    assert voices[0][0] == murf_tts.DEFAULT_VOICE


def test_synthesize_mp3(monkeypatch):

    captured: dict = {}

    class FakeResp:
        status_code = 200

        @staticmethod
        def json():
            return {
                "encodedAudio": "bXAz",
                "consumedCharacterCount": 28,
                "remainingCharacterCount": 99972,
                "wordDurations": [
                    {"word": "Hello", "startMs": 0, "endMs": 400},
                ],
            }

    def fake_post(url, headers, json, timeout):
        captured["json"] = json
        return FakeResp()

    monkeypatch.setattr(murf_tts.requests, "post", fake_post)
    monkeypatch.setattr(murf_tts, "resolve_voice_id", lambda voice, api_key: voice)

    audio, usage, timings = murf_tts.synthesize_mp3(
        "Hello",
        voice="Natalie",
        lang="en",
        api_key="test-key",
        speed=0.25,
    )
    assert audio == b"mp3"
    assert usage["remaining"] == 99972
    assert timings == [(0, 400)]
    assert captured["json"]["rate"] == -50


def test_parse_word_durations():
    data = {
        "wordDurations": [
            {"word": "Hi", "startMs": 10, "endMs": 200},
            {"word": "there", "startMs": 201, "endMs": 500},
        ]
    }
    assert murf_tts.parse_word_durations(data) == [(10, 200), (201, 500)]


def test_usage_starts_at_zero(db: Database):
    tracker = MurfTTSUsage(db)
    stats = tracker.status()
    assert stats["used"] == 0
    assert stats["remaining"] == FREE_MONTHLY_CHAR_LIMIT


def test_sync_from_response(db: Database):
    tracker = MurfTTSUsage(db)
    tracker.sync_from_response(consumed=500, remaining=99500)
    stats = tracker.status()
    assert stats["source"] == "api"
    assert stats["remaining"] == 99500


def test_murf_speech_rate_mapping():
    from src.core.tts_speed import murf_speech_rate

    assert murf_speech_rate(1.0) == 0
    assert murf_speech_rate(0.25) == -50
    assert murf_speech_rate(0.5) == -33
    assert murf_speech_rate(2.0) == 50
