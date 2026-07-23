"""Smoke tests for Qt widgets and i18n fallbacks."""

import pytest
from PySide6.QtWidgets import QApplication

from src.core.i18n import set_language, tr


class _NoSignal:
    def connect(self, _cb):
        pass


class _FakeTTS:
    generating_changed = _NoSignal()
    activity_changed = _NoSignal()
    playback_error = _NoSignal()
    playback_started = _NoSignal()
    playback_finished = _NoSignal()
    sample_finished = _NoSignal()
    _last_error = ""

    def is_generating(self):
        return False

    def active_tasks(self):
        return 0

    def is_cached(self, _text):
        return False

    def cache_stats(self):
        return {"memory": 0, "disk": 0}

    def last_error(self):
        return self._last_error

    def audio_status(self, text):
        if not text.strip():
            return "none", ""
        return "waiting", ""

    def describe_main_engine(self):
        from src.core.tts_engine import TTSEngineInfo

        return TTSEngineInfo(
            mode_label="Auto",
            engine_label="Edge TTS",
            is_slow=False,
            loading_hint="Preparing audio…",
        )


class _FakeTranslator:
    last_error = ""
    block_provider = "free"
    word_provider = "free"
    selection_provider = "free"

    def can_use_ollama(self, **kwargs):
        return False

    def pending_tasks(self):
        return 0

    def cache_stats(self):
        return 0, 0

    def last_activity(self):
        return ""

    def provider_label(self, scope="block"):
        return f"provider:{scope}"

    def is_sentence_cached(self, _text):
        return False

    @property
    def activity_changed(self):
        return _NoSignal()


class _FakeReadingView:
    current_book = None
    current_text = ""
    current_block_index = 0
    is_playing = False
    is_paused = False
    progress_updated = _NoSignal()

    def block_position_label(self):
        return ""


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_partial_locale_falls_back_to_english():
    set_language("de")
    assert tr("settings.sync_now") == "Sync now"
    assert tr("settings.export") == "Backup exportieren"


def test_processing_status_panel_smoke(qapp):
    from src.core.processing_status import ProcessingStatusTracker
    from src.ui.processing_status_panel import ProcessingStatusPanel

    tracker = ProcessingStatusTracker(
        _FakeTTS(),
        _FakeTranslator(),
        _FakeReadingView(),
    )
    panel = ProcessingStatusPanel(tracker)
    panel.refresh()
    assert panel.windowTitle()
    panel.close()
