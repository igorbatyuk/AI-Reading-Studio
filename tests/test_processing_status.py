"""Tests for processing status aggregation."""

from src.core.processing_status import ProcessingStatusTracker
from src.core.tts_engine import TTSEngineInfo


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
        return {"memory": 2, "disk": 5}

    def last_error(self):
        return self._last_error

    def audio_status(self, text):
        if not text.strip():
            return "none", ""
        return "waiting", ""

    def describe_main_engine(self):
        return TTSEngineInfo(
            mode_label="Auto",
            engine_label="Edge TTS (free) → Neural (Kokoro CLI) fallback",
            is_slow=False,
            loading_hint="Preparing audio…",
        )


class _FakeTranslator:
    last_error = ""
    block_provider = "free"
    word_provider = "free"
    selection_provider = "apify"

    def can_use_ollama(self, **kwargs):
        return False

    def pending_tasks(self):
        return 0

    def cache_stats(self):
        return 3, 1

    def last_activity(self):
        return ""

    def provider_label(self, scope="block"):
        return f"provider:{scope}"

    def is_sentence_cached(self, _text):
        return False

    @property
    def activity_changed(self):
        return _NoSignal()


class _FakeBook:
    title = "Test Book"
    total_blocks = 10
    id = 1


class _FakeDB:
    def get_block(self, book_id, index):
        return (f"Block {index + 1}", "Chapter 1")


class _FakeReadingView:
    current_book = None
    current_text = ""
    current_block_index = 0
    db = None
    is_playing = False
    is_paused = False
    progress_updated = _NoSignal()
    highlight_sync_mode = "idle"


def test_snapshot_without_book():
    tracker = ProcessingStatusTracker(
        _FakeTTS(), _FakeTranslator(), _FakeReadingView()
    )
    snap = tracker.snapshot()
    assert snap.audio_current == "none"
    assert snap.audio_next == "na"
    assert snap.summary_level == "ok"
    assert snap.book_title == ""
    assert snap.translation_provider_label == "provider:block"


def test_snapshot_with_book_position():
    view = _FakeReadingView()
    view.current_book = _FakeBook()
    view.current_text = "Hello world"
    view.current_block_index = 2
    view.db = _FakeDB()
    tracker = ProcessingStatusTracker(_FakeTTS(), _FakeTranslator(), view)
    snap = tracker.snapshot()
    assert snap.book_title == "Test Book"
    assert snap.block_position
    assert snap.tts_engine_label


def test_snapshot_audio_failed():
    tts = _FakeTTS()

    def audio_status(text):
        return "failed", "Edge TTS timeout"

    tts.audio_status = audio_status
    view = _FakeReadingView()
    view.current_text = "Hello world"
    tracker = ProcessingStatusTracker(tts, _FakeTranslator(), view)
    snap = tracker.snapshot()
    assert snap.summary_level == "error"
    assert "Edge TTS" in snap.audio_current_error


def test_snapshot_slow_engine_generating():
    tts = _FakeTTS()

    def describe_main_engine():
        return TTSEngineInfo(
            mode_label="Offline",
            engine_label="Neural (Kokoro CLI)",
            is_slow=True,
            loading_hint="Generating…",
        )

    def audio_status(text):
        return "generating", ""

    tts.describe_main_engine = describe_main_engine
    tts.audio_status = audio_status
    view = _FakeReadingView()
    view.current_text = "Long block text"
    tracker = ProcessingStatusTracker(tts, _FakeTranslator(), view)
    snap = tracker.snapshot()
    assert snap.summary_level == "working"
    assert "Kokoro" in snap.summary_text
    assert snap.tts_slow_hint
