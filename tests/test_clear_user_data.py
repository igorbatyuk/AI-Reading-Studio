"""Tests for clearing library data while keeping settings."""

from __future__ import annotations

import pytest

from src.core.backup_service import BackupService
from src.core.cover_service import CoverService
from src.core.database import Database


@pytest.fixture
def db(tmp_path):
    return Database(tmp_path / "test.db")


def test_clear_user_data_removes_books_and_keeps_settings(db: Database, tmp_path):
    db.set_setting("tts_voice", "en-US-AriaNeural")
    db.set_setting("ui_language", "uk")
    db.add_book("Book A", "Author", "/a.epub", ".epub", [("Block one", "")])
    db.add_reading_seconds(120)

    audio_dir = db.app_dir / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    (audio_dir / "cache.mp3").write_bytes(b"mp3")

    covers = CoverService(db.app_dir)
    covers.save_cover(1, b"\xff\xd8\xff" + b"x" * 20)

    service = BackupService(db)
    counts = service.clear_user_data()

    assert counts["books"] == 1
    assert counts["stats_days"] >= 1
    assert counts["audio_files"] == 1
    assert counts["cover_files"] == 1
    assert db.get_all_books() == []
    assert db.get_setting("tts_voice") == "en-US-AriaNeural"
    assert db.get_setting("ui_language") == "uk"
    assert db.get_statistics()["total_blocks"] == 0
    assert not list(audio_dir.iterdir())
    assert not list((db.app_dir / "covers").iterdir())
