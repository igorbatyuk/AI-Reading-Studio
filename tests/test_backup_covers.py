"""Tests for backup covers and import merge logic."""

import base64

import pytest

from src.core.cover_service import CoverService
from src.core.database import Database


@pytest.fixture
def db(tmp_path):
    return Database(tmp_path / "test.db")


def test_export_import_cover_b64(db: Database, tmp_path):
    book_id = db.add_book(
        "Cover Book",
        "Author",
        "/fake/book.epub",
        ".epub",
        [("Hello world block", "")],
    )
    covers = CoverService(db.app_dir)
    png = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
        b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde"
        b"\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x01\x01\x01\x00\x18\xdd\x8d\xb4"
        b"\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    covers.save_cover(book_id, png)

    exported = db.export_data()
    book = exported["books"][0]
    assert book["cover_b64"]
    assert base64.b64decode(book["cover_b64"]) == png

    db2 = Database(tmp_path / "restored.db")
    db2.import_data(exported, merge=False)
    restored = db2.get_all_books()[0]
    restored_cover = CoverService(db2.app_dir).get_cover_path(restored.id, restored.cover_path)
    assert restored_cover is not None
    assert restored_cover.read_bytes() == png


def test_import_merge_uses_title_and_author(db: Database):
    id_a = db.add_book("Same Title", "Author A", "/a.txt", ".txt", [("A", "")])
    id_b = db.add_book("Same Title", "Author B", "/b.txt", ".txt", [("B", "")])

    payload = {
        "version": 4,
        "books": [
            {
                "title": "Same Title",
                "author": "Author A",
                "file_path": "/backup/a.txt",
                "format": ".txt",
                "total_blocks": 1,
                "current_block": 0,
                "progress_percent": 99.0,
                "last_read_at": None,
                "added_at": "2026-01-01",
                "cover_path": "",
                "cover_b64": "",
                "tags": [],
                "blocks": [{"block_index": 0, "text": "A updated", "chapter": ""}],
            }
        ],
        "daily_stats": [],
        "settings": {},
    }
    db.import_data(payload, merge=True)
    book_a = db.get_book(id_a)
    book_b = db.get_book(id_b)
    assert book_a.progress_percent == 99.0
    assert book_b.progress_percent != 99.0


def test_add_reading_seconds(db: Database):
    db.add_reading_seconds(45)
    db.add_reading_seconds(30)
    stats = db.get_day_stats(__import__("datetime").date.today().isoformat())
    assert stats is not None
    assert stats["seconds"] == 75
