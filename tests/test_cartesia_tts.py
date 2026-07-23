"""Tests for Cartesia TTS client and usage."""

from pathlib import Path

import pytest

from src.core import cartesia_tts
from src.core.cartesia_tts_usage import FREE_MONTHLY_CREDIT_LIMIT, CartesiaTTSUsage
from src.core.database import Database


@pytest.fixture
def db(tmp_path: Path) -> Database:
    return Database(tmp_path / "test.db")


def test_list_voices_fallback():
    voices = cartesia_tts.list_voices_for_language("en")
    assert voices
    assert voices[0][0] == cartesia_tts.DEFAULT_VOICE


def test_synthesize_mp3(monkeypatch):
    captured: dict = {}

    class FakeResp:
        status_code = 200
        content = b"mp3-data"

    def fake_post(url, headers, json, timeout):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        return FakeResp()

    monkeypatch.setattr(cartesia_tts.requests, "post", fake_post)

    audio = cartesia_tts.synthesize_mp3(
        "Hello",
        voice=cartesia_tts.DEFAULT_VOICE,
        lang="en",
        api_key="sk_car_test",
        speed=0.25,
    )
    assert audio == b"mp3-data"
    assert captured["url"].endswith("/tts/bytes")
    assert captured["headers"]["Authorization"] == "Bearer sk_car_test"
    assert captured["headers"]["Cartesia-Version"] == cartesia_tts.API_VERSION
    assert captured["json"]["transcript"] == "Hello"
    assert captured["json"]["model_id"] == "sonic-3.5"
    assert captured["json"]["voice"] == {
        "mode": "id",
        "id": cartesia_tts.DEFAULT_VOICE,
    }
    assert captured["json"]["generation_config"]["speed"] == 0.6


def test_usage_starts_at_zero(db: Database):
    tracker = CartesiaTTSUsage(db)
    stats = tracker.status()
    assert stats["used"] == 0
    assert stats["remaining"] == FREE_MONTHLY_CREDIT_LIMIT


def test_usage_records_credits(db: Database):
    tracker = CartesiaTTSUsage(db)
    tracker.record(120)
    stats = tracker.status()
    assert stats["used"] == 120


def test_can_spend_respects_limit(db: Database):
    tracker = CartesiaTTSUsage(db)
    tracker.record(FREE_MONTHLY_CREDIT_LIMIT)
    assert tracker.can_spend(1) is False
