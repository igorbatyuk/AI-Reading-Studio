"""Tests for Apify translation usage tracking."""

from datetime import date
from pathlib import Path

import pytest

from src.core.apify_translate_usage import (
    FREE_MONTHLY_CHAR_LIMIT,
    ApifyTranslateUsage,
)
from src.core.database import Database


@pytest.fixture
def db(tmp_path: Path) -> Database:
    return Database(tmp_path / "test.db")


def test_usage_starts_at_zero(db: Database):
    tracker = ApifyTranslateUsage(db)
    stats = tracker.status()
    assert stats["used"] == 0
    assert stats["remaining"] == FREE_MONTHLY_CHAR_LIMIT
    assert stats["month"] == date.today().strftime("%Y-%m")


def test_usage_accumulates(db: Database):
    tracker = ApifyTranslateUsage(db)
    tracker.record(1200)
    tracker.record(800)
    stats = tracker.status()
    assert stats["used"] == 2000
    assert stats["remaining"] == FREE_MONTHLY_CHAR_LIMIT - 2000


def test_usage_resets_on_new_month(db: Database, monkeypatch):
    tracker = ApifyTranslateUsage(db)
    tracker.record(5000)
    monkeypatch.setattr(
        ApifyTranslateUsage,
        "current_month",
        staticmethod(lambda: "2099-01"),
    )
    stats = tracker.status()
    assert stats["used"] == 0
    assert stats["month"] == "2099-01"


def test_translate_apify_records_usage(monkeypatch):
    from src.core.translation_service import TranslationService

    recorded: list[int] = []

    class FakeUsage:
        def record(self, n: int) -> None:
            recorded.append(n)

    service = TranslationService(
        source_lang="en",
        target_lang="uk",
        apify_api_token="apify_api_test",
        apify_usage=FakeUsage(),
    )

    monkeypatch.setattr(
        "src.core.translation_service.apify_translate.translate_text",
        lambda text, **kwargs: ("привіт", ""),
    )
    monkeypatch.setattr(
        service,
        "_is_valid_translation",
        lambda source, result: True,
    )

    result = service._translate_apify("hello")
    assert result == "привіт"
    assert recorded == [5]
