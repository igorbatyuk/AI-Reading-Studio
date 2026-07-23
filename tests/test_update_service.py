"""Tests for GitHub update checker."""

from src.core.update_service import is_newer, parse_version, check_github_release


def test_parse_version():
    assert parse_version("1.2.0") == (1, 2, 0)
    assert parse_version("v2.10.3") == (2, 10, 3)
    assert parse_version("") == (0,)


def test_is_newer():
    assert is_newer("1.0.0", "1.1.0") is True
    assert is_newer("1.2.0", "1.2.0") is False
    assert is_newer("2.0.0", "1.9.9") is False
    assert is_newer("1.9.0", "1.10.0") is True


def test_check_github_release_invalid_repo():
    assert check_github_release("", "1.0.0") is None
    assert check_github_release("invalid", "1.0.0") is None
