"""Tests for Google Cloud Translation API usage tracking."""

from datetime import date
from pathlib import Path

import pytest

from src.core.google_translate_usage import (
    FREE_MONTHLY_CHAR_LIMIT,
    GoogleTranslateUsage,
)
from src.core.database import Database


@pytest.fixture
def db(tmp_path: Path) -> Database:
    return Database(tmp_path / "test.db")


def test_usage_starts_at_zero(db: Database):
    tracker = GoogleTranslateUsage(db)
    stats = tracker.status()
    assert stats["used"] == 0
    assert stats["remaining"] == FREE_MONTHLY_CHAR_LIMIT
    assert stats["month"] == date.today().strftime("%Y-%m")


def test_usage_accumulates(db: Database):
    tracker = GoogleTranslateUsage(db)
    tracker.record(1200)
    tracker.record(800)
    stats = tracker.status()
    assert stats["used"] == 2000
    assert stats["remaining"] == FREE_MONTHLY_CHAR_LIMIT - 2000


def test_usage_resets_on_new_month(db: Database, monkeypatch):
    tracker = GoogleTranslateUsage(db)
    tracker.record(5000)
    monkeypatch.setattr(
        GoogleTranslateUsage,
        "current_month",
        staticmethod(lambda: "2099-01"),
    )
    stats = tracker.status()
    assert stats["used"] == 0
    assert stats["month"] == "2099-01"


def test_translate_google_api_records_usage(monkeypatch):
    from src.core.translation_service import TranslationService

    recorded: list[int] = []

    class FakeUsage:
        def record(self, n: int) -> None:
            recorded.append(n)

    service = TranslationService(
        source_lang="en",
        target_lang="uk",
        google_api_key="AIza-test",
        google_usage=FakeUsage(),
    )

    class FakeResp:
        status_code = 200

        @staticmethod
        def json():
            return {"data": {"translations": [{"translatedText": "привіт"}]}}

    monkeypatch.setattr(
        "src.core.translation_service.requests.post",
        lambda *args, **kwargs: FakeResp(),
    )
    monkeypatch.setattr(
        service,
        "_is_valid_translation",
        lambda source, result: True,
    )

    result = service._translate_google_api("hello")
    assert result == "привіт"
    assert recorded == [5]
