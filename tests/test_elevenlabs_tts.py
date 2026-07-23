"""Tests for ElevenLabs TTS client and usage."""

from pathlib import Path

import pytest

from src.core import elevenlabs_tts
from src.core.database import Database
from src.core.elevenlabs_tts_usage import (
    FREE_MONTHLY_CREDIT_LIMIT,
    ElevenLabsTTSUsage,
)


@pytest.fixture
def db(tmp_path: Path) -> Database:
    return Database(tmp_path / "test.db")


def test_resolve_legacy_rachel_voice():
    assert (
        elevenlabs_tts.resolve_voice_id("21m00Tcm4TlvDq8ikWAM")
        == elevenlabs_tts.DEFAULT_VOICE
    )


def test_list_voices():
    voices = elevenlabs_tts.list_voices_for_language("en")
    assert voices
    assert voices[0][0] == elevenlabs_tts.DEFAULT_VOICE


def test_synthesize_mp3(monkeypatch):
    captured: dict = {}

    class FakeResp:
        status_code = 200
        content = b"mp3-data"

    def fake_post(url, headers, json, params, timeout):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        return FakeResp()

    monkeypatch.setattr(elevenlabs_tts.requests, "post", fake_post)

    audio = elevenlabs_tts.synthesize_mp3(
        "Hello",
        voice=elevenlabs_tts.DEFAULT_VOICE,
        lang="en",
        api_key="sk-test",
        speed=0.25,
    )
    assert audio == b"mp3-data"
    assert "text-to-speech" in captured["url"]
    assert captured["headers"]["xi-api-key"] == "sk-test"
    assert captured["json"]["text"] == "Hello"
    assert captured["json"]["voice_settings"]["speed"] == 0.25


def test_synthesize_mp3_default_speed(monkeypatch):
    captured: dict = {}

    class FakeResp:
        status_code = 200
        content = b"mp3-data"

    def fake_post(url, headers, json, params, timeout):
        captured["json"] = json
        return FakeResp()

    monkeypatch.setattr(elevenlabs_tts.requests, "post", fake_post)

    elevenlabs_tts.synthesize_mp3(
        "Hello",
        voice=elevenlabs_tts.DEFAULT_VOICE,
        lang="en",
        api_key="sk-test",
    )
    assert captured["json"]["voice_settings"]["speed"] == 1.0


def test_fetch_subscription(monkeypatch):
    class FakeResp:
        status_code = 200

        @staticmethod
        def json():
            return {
                "character_count": 2500,
                "character_limit": 10000,
                "tier": "free",
            }

    monkeypatch.setattr(elevenlabs_tts.requests, "get", lambda *a, **k: FakeResp())
    stats = elevenlabs_tts.fetch_subscription("sk-test")
    assert stats["used"] == 2500
    assert stats["limit"] == 10000
    assert stats["remaining"] == 7500


def test_usage_starts_at_zero(db: Database):
    tracker = ElevenLabsTTSUsage(db)
    stats = tracker.status()
    assert stats["used"] == 0
    assert stats["remaining"] == FREE_MONTHLY_CREDIT_LIMIT
    assert stats["source"] == "local"


def test_usage_records_credits(db: Database):
    tracker = ElevenLabsTTSUsage(db)
    tracker.record(120)
    stats = tracker.status()
    assert stats["local_used"] == 60
    assert stats["used"] == 60


def test_sync_skips_when_recent(db: Database, monkeypatch):
    tracker = ElevenLabsTTSUsage(db)
    calls = {"n": 0}

    def fake_fetch(_key):
        calls["n"] += 1
        return {"used": 1, "limit": 10000, "remaining": 9999, "tier": "free"}

    monkeypatch.setattr(
        "src.core.elevenlabs_tts.fetch_subscription",
        fake_fetch,
    )
    assert tracker.sync_from_api("sk-test", force=True) is True
    assert calls["n"] == 1
    assert tracker.sync_from_api("sk-test") is True
    assert calls["n"] == 1
    assert tracker.sync_from_api("sk-test", force=True) is True
    assert calls["n"] == 2


def test_sync_from_api(db: Database, monkeypatch):
    tracker = ElevenLabsTTSUsage(db)

    class FakeResp:
        status_code = 200

        @staticmethod
        def json():
            return {
                "character_count": 4000,
                "character_limit": 10000,
                "tier": "free",
            }

    monkeypatch.setattr(
        "src.core.elevenlabs_tts.requests.get",
        lambda *a, **k: FakeResp(),
    )
    assert tracker.sync_from_api("sk-test") is True
    stats = tracker.status()
    assert stats["source"] == "api"
    assert stats["used"] == 4000
    assert stats["limit"] == 10000


def test_can_spend_respects_limit(db: Database):
    tracker = ElevenLabsTTSUsage(db)
    tracker.record(FREE_MONTHLY_CREDIT_LIMIT * 2)
    assert tracker.can_spend(1) is False
