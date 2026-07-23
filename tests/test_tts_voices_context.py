"""Tests for context-aware TTS voice selection."""

from pathlib import Path

from src.core.tts_voices import (
    default_voice_for_tts_context,
    format_stored_voice,
    get_voices_for_tts_context,
    is_voice_valid_for_tts_context,
    parse_stored_voice,
)


def test_parse_legacy_edge_voice():
    assert parse_stored_voice("en-US-AriaNeural") == ("edge", "en-US-AriaNeural")


def test_parse_prefixed_voice():
    assert parse_stored_voice("kokoro:af_heart") == ("kokoro", "af_heart")


def test_edge_voices_for_online_mode():
    voices = get_voices_for_tts_context("en", "online", "system")
    assert voices
    assert voices[0][0].startswith("edge:")


def test_kokoro_voices_for_offline_kokoro():
    voices = get_voices_for_tts_context("en", "offline", "kokoro")
    assert any(v[0] == format_stored_voice("kokoro", "af_heart") for v in voices)


def test_switching_engine_invalidates_voice():
    edge_voice = default_voice_for_tts_context("en", "online", "system")
    assert is_voice_valid_for_tts_context(edge_voice, "en", "online", "system")
    assert not is_voice_valid_for_tts_context(
        edge_voice, "en", "offline", "kokoro"
    )


def test_default_voice_changes_with_engine(tmp_path: Path):
    edge_default = default_voice_for_tts_context(
        "en", "online", "system", online_engine="edge", app_dir=tmp_path
    )
    kokoro_default = default_voice_for_tts_context(
        "en", "offline", "kokoro", app_dir=tmp_path
    )
    assert edge_default.startswith("edge:")
    assert kokoro_default.startswith("kokoro:")


def test_azure_voices_for_online_azure():
    voices = get_voices_for_tts_context(
        "en", "online", "system", online_engine="azure"
    )
    assert voices
    assert voices[0][0].startswith("azure:")


def test_google_voices_for_online_google():
    voices = get_voices_for_tts_context(
        "en", "online", "system", online_engine="google"
    )
    assert voices
    assert voices[0][0].startswith("google:")


def test_elevenlabs_voices_for_online():
    voices = get_voices_for_tts_context(
        "en", "online", "system", online_engine="elevenlabs"
    )
    assert voices
    assert voices[0][0].startswith("elevenlabs:")


def test_cartesia_voices_for_online():
    voices = get_voices_for_tts_context(
        "en", "online", "system", online_engine="cartesia"
    )
    assert voices
    assert voices[0][0].startswith("cartesia:")


def test_murf_voices_for_online():
    voices = get_voices_for_tts_context(
        "en", "online", "system", online_engine="murf"
    )
    assert voices
    assert voices[0][0].startswith("murf:")


def test_xtts_voices_for_offline_xtts(tmp_path: Path):
    speakers = tmp_path / "xtts_speakers"
    speakers.mkdir()
    (speakers / "demo.wav").write_bytes(b"wav")
    voices = get_voices_for_tts_context(
        "en", "offline", "xtts", app_dir=tmp_path
    )
    assert any(v[0] == format_stored_voice("xtts", "demo") for v in voices)


def test_styletts2_voices_for_offline(tmp_path: Path):
    models = tmp_path / "styletts2_models"
    models.mkdir()
    (models / "voice.pth").write_bytes(b"pth")
    voices = get_voices_for_tts_context(
        "en", "offline", "styletts2", app_dir=tmp_path
    )
    assert any(v[0] == format_stored_voice("styletts2", "voice") for v in voices)


def test_piper_voices_list_all_onnx_in_folder(tmp_path: Path, monkeypatch):
    from src.core import piper_tts

    bundled = tmp_path / "piper_bundled"
    bundled.mkdir()
    (bundled / "en_US-lessac-medium.onnx").write_bytes(b"x")
    (bundled / "en_GB-alan-medium.onnx").write_bytes(b"x")
    (bundled / "en_US-ryan-medium.onnx").write_bytes(b"x")
    monkeypatch.setattr(piper_tts, "bundled_piper_dir", lambda: bundled)

    voices = get_voices_for_tts_context(
        "en", "offline", "piper", app_dir=tmp_path
    )
    ids = [v[0] for v in voices]
    assert format_stored_voice("piper", "en_US-lessac-medium") in ids
    assert format_stored_voice("piper", "en_GB-alan-medium") in ids
    assert format_stored_voice("piper", "en_US-ryan-medium") in ids
    assert len(voices) == 3
