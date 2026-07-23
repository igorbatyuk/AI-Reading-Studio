"""Tests for StyleTTS2 bundled worker discovery."""

from src.core import styletts2_tts


def test_styletts2_worker_script_exists():
    worker = styletts2_tts.find_styletts2_worker()
    assert worker is not None
    assert worker.name == styletts2_tts.WORKER_SCRIPT
    assert worker.is_file()


def test_bundled_styletts2_dir_layout():
    base = styletts2_tts.bundled_styletts2_dir()
    assert base.is_dir()
    assert (base / "setup.bat").is_file()
