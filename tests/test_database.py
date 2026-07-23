"""Tests for Database block read deduplication."""

from pathlib import Path

import pytest

from src.core.database import Database


@pytest.fixture
def db(tmp_path: Path) -> Database:
    return Database(tmp_path / "test.db")


def test_record_block_read_deduplicates(db: Database):
    db.add_book("Test", "Author", "/fake/book.txt", ".txt", [("Hello world", ""), ("Second block here", "")])

    assert db.record_block_read(1, 0, 2) is True
    assert db.record_block_read(1, 0, 2) is False
    assert db.get_today_blocks_read() == 1

    assert db.record_block_read(1, 1, 3) is True
    assert db.get_today_blocks_read() == 2


def test_replace_book_blocks_keeps_progress(db: Database):
    book_id = db.add_book(
        "Test",
        "Author",
        "/fake/book.txt",
        ".txt",
        [("Block zero", ""), ("Block one", ""), ("Block two", "")],
    )
    db.update_book_progress(book_id, 2, 66.0)
    new_blocks = [("A" * 20, ""), ("B" * 20, "")]
    db.replace_book_blocks(book_id, new_blocks)
    book = db.get_book(book_id)
    assert book.total_blocks == 2
    assert book.current_block == 1
