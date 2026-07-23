"""Tests for network status helper."""

from src.core.network_status import is_online


def test_is_online_returns_bool():
    assert isinstance(is_online(timeout=0.5), bool)
