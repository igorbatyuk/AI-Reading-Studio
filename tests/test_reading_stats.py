"""Tests for reading_stats helpers."""

from src.core.reading_stats import (
    day_reading_status,
    estimate_reading_minutes,
    format_reading_duration,
    is_daily_goal_met,
    parse_daily_goal_settings,
)


def test_day_reading_status_blocks():
    assert day_reading_status(10, 10) == "completed"
    assert day_reading_status(5, 10) == "partial"
    assert day_reading_status(0, 10) == "missed"


def test_day_reading_status_time():
    settings = {
        "daily_goal_type": "time",
        "daily_goal_blocks": "10",
        "daily_goal_minutes": "15",
    }
    assert day_reading_status(0, 0, seconds=900, settings=settings) == "completed"
    assert day_reading_status(2, 0, seconds=300, settings=settings) == "partial"
    assert day_reading_status(0, 0, seconds=0, settings=settings) == "missed"


def test_is_daily_goal_met():
    block_settings = {
        "daily_goal_type": "blocks",
        "daily_goal_blocks": "10",
        "daily_goal_minutes": "15",
    }
    time_settings = {
        "daily_goal_type": "time",
        "daily_goal_blocks": "10",
        "daily_goal_minutes": "15",
    }
    assert is_daily_goal_met(10, 0, block_settings)
    assert not is_daily_goal_met(5, 0, block_settings)
    assert is_daily_goal_met(0, 900, time_settings)
    assert not is_daily_goal_met(0, 100, time_settings)


def test_parse_daily_goal_settings_defaults():
    goal = parse_daily_goal_settings({})
    assert goal["type"] == "blocks"
    assert goal["blocks"] == 10
    assert goal["minutes"] == 15


def test_estimate_reading_minutes():
    assert estimate_reading_minutes(0, 0) == 0
    assert estimate_reading_minutes(3, 0) >= 1
    assert estimate_reading_minutes(0, 360) >= 1


def test_format_reading_duration():
    assert format_reading_duration(0) == "0:00"
    assert format_reading_duration(65) == "1:05"
    assert format_reading_duration(3665) == "1:01:05"
