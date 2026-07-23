"""Startup behavior tests."""

import pytest

from PySide6.QtWidgets import QApplication


@pytest.fixture
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


def test_continue_reading_is_deferred_until_after_show(qapp, monkeypatch):
    """Continue dialog must not block MainWindow init before window.show()."""
    calls: list[str] = []

    def fake_check(self) -> None:
        calls.append("continue")

    monkeypatch.setattr(
        "src.ui.main_window.MainWindow._check_continue_reading",
        fake_check,
    )

    from src.ui.main_window import MainWindow

    window = MainWindow()
    assert calls == [], "continue check should be deferred, not run during __init__"

    window.show()
    qapp.processEvents()
    import time

    end = time.monotonic() + 1.0
    while time.monotonic() < end and not calls:
        qapp.processEvents()
        time.sleep(0.01)

    assert calls == ["continue"]
    window.close()
