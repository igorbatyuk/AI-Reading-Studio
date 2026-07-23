"""Tests for cloud TTS usage tracking."""

from datetime import date
from pathlib import Path

import pytest

from src.core.azure_tts_usage import AzureTTSUsage, FREE_MONTHLY_CHAR_LIMIT
from src.core.google_tts_usage import GoogleTTSUsage
from src.core.database import Database
from src.core.tts_engine import TTSEngine


@pytest.fixture
def db(tmp_path: Path) -> Database:
    return Database(tmp_path / "test.db")


def test_azure_usage_starts_at_zero(db: Database):
    tracker = AzureTTSUsage(db)
    stats = tracker.status()
    assert stats["used"] == 0
    assert stats["remaining"] == FREE_MONTHLY_CHAR_LIMIT
    assert stats["month"] == date.today().strftime("%Y-%m")


def test_google_tts_usage_accumulates(db: Database):
    tracker = GoogleTTSUsage(db)
    tracker.record(1000)
    tracker.record(500)
    stats = tracker.status()
    assert stats["used"] == 1500


def test_azure_can_spend_respects_limit(db: Database):
    tracker = AzureTTSUsage(db)
    tracker.record(FREE_MONTHLY_CHAR_LIMIT)
    assert tracker.can_spend(1) is False
    assert tracker.can_spend(0) is True


def test_google_can_spend_respects_limit(db: Database):
    tracker = GoogleTTSUsage(db)
    tracker.record(FREE_MONTHLY_CHAR_LIMIT)
    assert tracker.can_spend(1) is False


def test_azure_blocks_tts_generation(db: Database, tmp_path: Path, monkeypatch):
    tts = TTSEngine("azure:en-US-JennyNeural")
    tts.set_app_dir(tmp_path)
    tts.set_mode("online")
    tts.set_online_engine("azure")
    tts.set_azure_credentials("key", "eastus")
    tts.set_azure_tts_usage(AzureTTSUsage(db))
    tts._azure_tts_usage.record(FREE_MONTHLY_CHAR_LIMIT)

    with pytest.raises(RuntimeError, match="monthly limit reached"):
        tts._generate_audio("hello", tts._cache_key("hello"), tts._main_context())
