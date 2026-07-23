"""Tests for API usage meter status levels."""

from src.ui.api_usage_meter import usage_status_level


def test_usage_status_level_ok():
    assert usage_status_level(percent=10, remaining=1000) == "ok"


def test_usage_status_level_warn():
    assert usage_status_level(percent=70, remaining=100) == "warn"


def test_usage_status_level_critical():
    assert usage_status_level(percent=90, remaining=10) == "critical"
    assert usage_status_level(percent=50, remaining=0) == "critical"
