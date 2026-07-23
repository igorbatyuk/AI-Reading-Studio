"""Tests for Piper TTS helpers."""

import time
from pathlib import Path

from src.core import piper_tts


def test_list_models_includes_bundled(tmp_path: Path, monkeypatch):
    bundled = tmp_path / "bundled"
    bundled.mkdir()
    (bundled / "en_US-lessac-medium.onnx").write_bytes(b"x")
    (bundled / "en_GB-alan-medium.onnx").write_bytes(b"x")
    monkeypatch.setattr(piper_tts, "bundled_piper_dir", lambda: bundled)
    models = piper_tts.list_models(tmp_path)
    assert len(models) == 2
    stems = [stem for stem, _path in models]
    assert "en_US-lessac-medium" in stems
    assert "en_GB-alan-medium" in stems


def test_list_models_sorted_by_addition_time(tmp_path: Path, monkeypatch):
    bundled = tmp_path / "bundled"
    bundled.mkdir()
    old = bundled / "en_US-lessac-medium.onnx"
    new = bundled / "en_GB-alan-medium.onnx"
    old.write_bytes(b"x")
    time.sleep(0.05)
    new.write_bytes(b"x")
    monkeypatch.setattr(piper_tts, "bundled_piper_dir", lambda: bundled)
    models = piper_tts.list_models(tmp_path)
    assert [stem for stem, _path in models] == [
        "en_US-lessac-medium",
        "en_GB-alan-medium",
    ]


def test_resolve_model_by_voice_stem(tmp_path: Path, monkeypatch):
    bundled = tmp_path / "bundled"
    bundled.mkdir()
    model = bundled / "en_US-ryan-medium.onnx"
    model.write_bytes(b"x")
    monkeypatch.setattr(piper_tts, "bundled_piper_dir", lambda: bundled)
    resolved = piper_tts.resolve_model("en", "", tmp_path, voice="en_US-ryan-medium")
    assert resolved == model


def test_list_voices_for_language(tmp_path: Path, monkeypatch):
    bundled = tmp_path / "bundled"
    bundled.mkdir()
    (bundled / "en_US-lessac-medium.onnx").write_bytes(b"x")
    monkeypatch.setattr(piper_tts, "bundled_piper_dir", lambda: bundled)
    voices = piper_tts.list_voices_for_language("en", tmp_path)
    assert ("en_US-lessac-medium", "Piper — en_US-lessac-medium") in voices


def test_resolve_model_custom_path(tmp_path: Path):
    model = tmp_path / "voice.onnx"
    model.write_bytes(b"x")
    resolved = piper_tts.resolve_model("en", str(model), tmp_path)
    assert resolved == model


def test_resolve_model_from_models_dir(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(
        piper_tts,
        "bundled_piper_dir",
        lambda: tmp_path / "missing_bundled",
    )
    models_dir = tmp_path / "piper_models"
    models_dir.mkdir()
    model = models_dir / "en_US-lessac-medium.onnx"
    model.write_bytes(b"x")
    resolved = piper_tts.resolve_model("en", "", tmp_path)
    assert resolved == model


def test_is_available_without_binary(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(piper_tts, "find_piper_binary", lambda: None)
    assert piper_tts.is_available("en", "", tmp_path) is False
