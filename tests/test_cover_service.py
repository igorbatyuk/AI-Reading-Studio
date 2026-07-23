"""Tests for cover service."""

from src.core.cover_service import CoverService, _detect_ext


def test_detect_ext():
    assert _detect_ext(b"\xff\xd8\xff\x00") == ".jpg"
    assert _detect_ext(b"\x89PNG\r\n\x1a\n") == ".png"


def test_save_cover(tmp_path):
    svc = CoverService(tmp_path)
    path = svc.save_cover(1, b"\xff\xd8\xff\x00abc")
    assert path.endswith(".jpg")
    assert svc.get_cover_path(1) is not None
