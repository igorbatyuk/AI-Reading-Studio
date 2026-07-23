"""Tests for period-based statistics."""

from datetime import date, timedelta

import pytest

from src.core.database import Database
from src.core.reading_stats import chart_bar_label


@pytest.fixture
def db(tmp_path):
    return Database(tmp_path / "test.db")


def test_get_monthly_stats_aggregates(db: Database):
    book_id = db.add_book("M", "A", "/m.txt", ".txt", [("one", ""), ("two", "")])
    today = date.today()
    for offset in range(3):
        day = (today - timedelta(days=offset * 10)).isoformat()
        with db._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO daily_stats
                (date, seconds, goal_met, words_read, blocks_read)
                VALUES (?, ?, 0, ?, ?)
                """,
                (day, 120 * (offset + 1), 20, 2),
            )
            conn.execute(
                """
                INSERT OR IGNORE INTO read_blocks (date, book_id, block_index, words)
                VALUES (?, ?, ?, ?)
                """,
                (day, book_id, offset, 10),
            )

    rows = db.get_monthly_stats(3)
    assert len(rows) == 3
    assert sum(row["blocks"] for row in rows) >= 2
    assert sum(row["seconds"] for row in rows) >= 120


def test_get_recent_daily_stats_includes_seconds(db: Database):
    db.add_reading_seconds(90)
    rows = db.get_recent_daily_stats(7)
    today_row = rows[-1]
    assert today_row["seconds"] == 90


def test_get_today_reading_seconds(db: Database):
    assert db.get_today_reading_seconds() == 0
    db.add_reading_seconds(42)
    assert db.get_today_reading_seconds() == 42


def test_get_yearly_stats(db: Database):
    book_id = db.add_book("Y", "A", "/y.txt", ".txt", [("block", "")])
    db.record_block_read(book_id, 0, 5)
    rows = db.get_yearly_stats(3)
    assert len(rows) == 3
    assert rows[-1]["blocks"] >= 1


def test_chart_bar_label_formats():
    assert chart_bar_label("2026-07-15", "week") == "07/15"
    assert chart_bar_label("2026-07", "month", lambda m: "July") == "Jul"
    assert chart_bar_label("2026", "year") == "2026"
