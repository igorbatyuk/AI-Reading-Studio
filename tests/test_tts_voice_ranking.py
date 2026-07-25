"""Tests for book-reading voice ranking (Phase 1)."""

from src.core.tts_voice_ranking import (
    is_unsuitable_for_reading,
    sort_voices_for_reading,
)
from src.core.tts_voices import format_stored_voice, get_voices_for_tts_context


def test_edge_english_jenny_before_aria():
    voices = get_voices_for_tts_context("en", "online", "system", online_engine="edge")
    ids = [v[0] for v in voices]
    jenny = format_stored_voice("edge", "en-US-JennyNeural")
    aria = format_stored_voice("edge", "en-US-AriaNeural")
    assert jenny in ids
    assert aria in ids
    assert ids.index(jenny) < ids.index(aria)


def test_edge_hides_multilingual_and_child():
    voices = get_voices_for_tts_context("en", "online", "system", online_engine="edge")
    ids = {v[0] for v in voices}
    assert format_stored_voice("edge", "en-US-AnaNeural") not in ids
    assert format_stored_voice("edge", "en-US-AvaMultilingualNeural") not in ids
    assert format_stored_voice("edge", "en-US-EmmaMultilingualNeural") not in ids


def test_ukrainian_polina_first():
    voices = get_voices_for_tts_context("uk", "online", "system", online_engine="edge")
    assert voices[0][0] == format_stored_voice("edge", "uk-UA-PolinaNeural")


def test_kokoro_recommended_order():
    voices = get_voices_for_tts_context("en", "offline", "kokoro")
    ids = [v[0] for v in voices]
    bella = format_stored_voice("kokoro", "af_bella")
    sarah = format_stored_voice("kokoro", "af_sarah")
    heart = format_stored_voice("kokoro", "af_heart")
    alloy = format_stored_voice("kokoro", "af_alloy")
    assert ids.index(bella) < ids.index(alloy)
    assert ids.index(sarah) < ids.index(alloy)
    assert ids.index(heart) < ids.index(alloy)


def test_piper_prefers_medium_over_x_low(tmp_path, monkeypatch):
    from src.core import piper_tts

    bundled = tmp_path / "piper_bundled"
    bundled.mkdir()
    (bundled / "uk_UA-lada-x_low.onnx").write_bytes(b"x")
    (bundled / "uk_UA-ukrainian_tts-medium.onnx").write_bytes(b"x")
    monkeypatch.setattr(piper_tts, "bundled_piper_dir", lambda: bundled)

    voices = get_voices_for_tts_context("uk", "offline", "piper", app_dir=tmp_path)
    assert len(voices) == 1
    assert "ukrainian_tts-medium" in voices[0][0]


def test_sort_keeps_voice_if_all_unsuitable():
    only_bad = [
        (format_stored_voice("edge", "en-US-AnaNeural"), "Edge — Ana"),
    ]
    result = sort_voices_for_reading(only_bad, "en", "edge")
    assert result == only_bad


def test_is_unsuitable_piper_x_low():
    assert is_unsuitable_for_reading(
        format_stored_voice("piper", "uk_UA-lada-x_low"),
        "Piper — uk_UA-lada-x_low",
    )
    assert not is_unsuitable_for_reading(
        format_stored_voice("piper", "en_US-lessac-medium"),
        "Piper — en_US-lessac-medium",
    )


def test_stored_voice_still_valid_after_reorder():
    aria = format_stored_voice("edge", "en-US-AriaNeural")
    voices = get_voices_for_tts_context("en", "online", "system", online_engine="edge")
    assert aria in {v[0] for v in voices}
