"""Tests for DeepL API usage tracking."""

from datetime import date
from pathlib import Path

import pytest

from src.core.deepl_translate_usage import (
    FREE_MONTHLY_CHAR_LIMIT,
    DeepLTranslateUsage,
)
from src.core.database import Database


@pytest.fixture
def db(tmp_path: Path) -> Database:
    return Database(tmp_path / "test.db")


def test_usage_starts_at_zero(db: Database):
    tracker = DeepLTranslateUsage(db)
    stats = tracker.status()
    assert stats["used"] == 0
    assert stats["remaining"] == FREE_MONTHLY_CHAR_LIMIT
    assert stats["limit"] == 1_000_000
    assert stats["month"] == date.today().strftime("%Y-%m")


def test_usage_accumulates(db: Database):
    tracker = DeepLTranslateUsage(db)
    tracker.record(5000)
    tracker.record(3000)
    stats = tracker.status()
    assert stats["used"] == 8000
    assert stats["remaining"] == FREE_MONTHLY_CHAR_LIMIT - 8000


def test_translate_deepl_records_usage(monkeypatch):
    from src.core.translation_service import TranslationService

    recorded: list[int] = []

    class FakeUsage:
        def record(self, n: int) -> None:
            recorded.append(n)

    service = TranslationService(
        source_lang="en",
        target_lang="uk",
        deepl_api_key="deepl-test:fx",
        deepl_usage=FakeUsage(),
    )

    monkeypatch.setattr(
        "src.core.translation_service.deepl_translate.translate_text",
        lambda text, **kwargs: ("привіт", ""),
    )
    monkeypatch.setattr(
        service,
        "_is_valid_translation",
        lambda source, result: True,
    )

    result = service._translate_deepl("hello")
    assert result == "привіт"
    assert recorded == [5]
