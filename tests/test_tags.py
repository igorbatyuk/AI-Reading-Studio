"""Tests for book tags."""

from pathlib import Path

import pytest

from src.core.database import Database


@pytest.fixture
def db(tmp_path: Path) -> Database:
    return Database(tmp_path / "test.db")


def test_book_tags(db: Database):
    book_id = db.add_book("T", "A", "/x.txt", ".txt", [("hello", "")])
    db.set_book_tags(book_id, ["Fiction", "english", "fiction"])
    tags = db.get_book_tags(book_id)
    assert tags == ["english", "fiction"]
    assert "english" in db.get_all_tags()
