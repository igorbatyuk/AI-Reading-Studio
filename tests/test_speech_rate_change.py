"""Tests for speech-rate change behaviour in TTSEngine and ReadingView."""

from src.core.tts_engine import TTSEngine


def test_set_speed_releases_loaded_playback(qapp, tmp_path):
    tts = TTSEngine()
    tts.set_app_dir(tmp_path)
    path = tmp_path / "sample.mp3"
    path.write_bytes(b"mp3")
    tts._current_file = path

    tts.set_speed(0.25)
    assert tts.speed == 0.25
    assert tts._current_file is None


def test_set_speed_bumps_prefetch_generation(qapp):
    tts = TTSEngine()
    before = tts._prefetch_generation
    tts.set_speed(0.5)
    assert tts._prefetch_generation == before + 1


def test_kokoro_speed_combo_excludes_slow_rates():
    from src.core.tts_speed import allowed_ui_speech_rates, speech_rate_limits_for_engine

    min_rate, max_rate = speech_rate_limits_for_engine("kokoro")
    allowed = allowed_ui_speech_rates(min_rate, max_rate)
    assert 0.25 not in allowed
    assert 0.5 in allowed
    assert 2.0 in allowed


def test_auto_mode_uses_restrictive_limits():
    from src.core.tts_speed import speech_rate_limits_for_tts_context

    min_rate, max_rate = speech_rate_limits_for_tts_context(
        "auto", offline_engine="kokoro", online_engine="google"
    )
    assert min_rate == 0.5
    assert max_rate == 2.0


def test_cartesia_caps_fast_rates():
    from src.core.tts_speed import allowed_ui_speech_rates, speech_rate_limits_for_engine

    min_rate, max_rate = speech_rate_limits_for_engine("cartesia")
    allowed = allowed_ui_speech_rates(min_rate, max_rate)
    assert 1.5 in allowed
    assert 1.75 not in allowed
    assert 2.0 not in allowed


def test_clamp_ui_speech_rate_for_context():
    from src.core.tts_speed import clamp_ui_speech_rate_for_context

    assert (
        clamp_ui_speech_rate_for_context(0.25, "offline", "kokoro", "edge")
        == 0.5
    )
    assert (
        clamp_ui_speech_rate_for_context(2.0, "online", "system", "cartesia")
        == 1.5
    )


def test_regenerate_on_speech_rate_change(qapp, monkeypatch):
    from src.ui.reading_view import ReadingView
    from src.core.database import Database

    db = Database()
    tts = TTSEngine()
    view = ReadingView(db, tts, None)
    view.current_text = "Sample block text."
    view.is_playing = True
    view.is_paused = True
    view.current_block_index = 0

    calls: list[str] = []

    def fake_speak(text, *, advance=True):
        calls.append(text)

    monkeypatch.setattr(tts, "speak", fake_speak)
    monkeypatch.setattr(tts, "stop", lambda emit_finished=False: None)
    monkeypatch.setattr(tts, "should_prefetch_blocks", lambda: False)

    view.on_speech_rate_changed(0.25)
    assert tts.speed == 0.25
    assert calls == ["Sample block text."]
