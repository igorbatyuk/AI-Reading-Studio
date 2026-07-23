"""Tests for time-based daily goals."""

import pytest

from src.core.database import Database


@pytest.fixture
def db(tmp_path):
    return Database(tmp_path / "test.db")


def test_time_goal_met_via_reading_seconds(db: Database):
    db.set_setting("daily_goal_type", "time")
    db.set_setting("daily_goal_minutes", "15")
    assert not db.is_goal_met_today()
    db.add_reading_seconds(900)
    assert db.is_goal_met_today()


def test_block_goal_still_works(db: Database):
    book_id = db.add_book("B", "A", "/b.txt", ".txt", [("one", "")])
    db.record_block_read( book_id, 0, 10)
    for _ in range(9):
        db.record_block_read(book_id, _ + 1, 10)
    assert db.is_goal_met_today()


def test_calendar_uses_time_goal(db: Database):
    db.set_setting("daily_goal_type", "time")
    db.set_setting("daily_goal_minutes", "10")
    db.add_reading_seconds(600)
    today = __import__("datetime").date.today()
    month = db.get_calendar_month(today.year, today.month)
    day_key = str(today.day)
    assert month[day_key]["status"] == "completed"
