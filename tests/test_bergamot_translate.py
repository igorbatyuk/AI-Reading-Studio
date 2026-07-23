"""Tests for Bergamot bundled worker discovery."""

from src.core import bergamot_translate


def test_bergamot_worker_script_exists():
    worker = bergamot_translate.find_worker()
    assert worker is not None
    assert worker.name == bergamot_translate.WORKER_SCRIPT
    assert worker.is_file()


def test_bundled_bergamot_dir_layout():
    base = bergamot_translate.bundled_bergamot_dir()
    assert base.is_dir()
    assert (base / "setup.bat").is_file()
    assert (base / "bergamot_worker.py").is_file()


def test_model_code():
    assert bergamot_translate.model_code("en", "uk") == "enuk"
    assert bergamot_translate.model_code("uk", "en") == "uken"


def test_is_available_same_language():
    assert bergamot_translate.is_available("en", "en") is False


def test_translate_same_language():
    assert bergamot_translate.translate("hello", "en", "en") == "hello"


def test_worker_is_ready_without_venv(monkeypatch):
    monkeypatch.setattr(bergamot_translate, "find_python", lambda: None)
    assert bergamot_translate.worker_is_ready() is False
