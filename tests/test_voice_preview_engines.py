"""Verify voice preview sample generation for every TTS engine."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from src.core.tts_engine import TTSEngine
from src.core.tts_voices import (
    BOOK_LANGUAGES,
    default_voice_for_tts_context,
    format_stored_voice,
    voice_preview_sample,
)


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _make_engine(tmp_path: Path):
    from src.core.tts_engine import TTSEngine

    tts = TTSEngine()
    tts.set_app_dir(tmp_path)
    tts.set_offline_language("en")
    return tts


def _write_fake(path: Path, suffix: str, engine: TTSEngine, text: str) -> Path:
    key = engine._cache_key(text)
    out = engine._cache_file_path(key, suffix)
    out.write_bytes(b"audio")
    return out


@pytest.mark.parametrize(
    "tts_mode,online_engine,offline_engine,voice_engine,suffix,generator",
    [
        ("online", "edge", "system", "edge", ".mp3", "_generate_edge"),
        ("online", "azure", "system", "azure", ".mp3", "_generate_azure"),
        ("online", "google", "system", "google", ".mp3", "_generate_google"),
        ("online", "elevenlabs", "system", "elevenlabs", ".mp3", "_generate_elevenlabs"),
        ("online", "cartesia", "system", "cartesia", ".mp3", "_generate_cartesia"),
        ("online", "murf", "system", "murf", ".mp3", "_generate_murf"),
        ("offline", "edge", "system", "system", ".wav", "_generate_offline"),
        ("offline", "edge", "piper", "piper", ".wav", "_generate_offline"),
        ("offline", "edge", "kokoro", "kokoro", ".wav", "_generate_offline"),
        ("offline", "edge", "xtts", "xtts", ".wav", "_generate_offline"),
        ("offline", "edge", "styletts2", "styletts2", ".wav", "_generate_offline"),
        ("auto", "edge", "system", "edge", ".mp3", "_generate_edge"),
    ],
)
def test_preview_generates_for_engine(
    qapp,
    tmp_path,
    monkeypatch,
    tts_mode,
    online_engine,
    offline_engine,
    voice_engine,
    suffix,
    generator,
):

    tts = _make_engine(tmp_path)
    voice = default_voice_for_tts_context(
        "en",
        tts_mode,
        offline_engine,
        online_engine=online_engine,
        app_dir=tmp_path,
    )
    assert voice.startswith(f"{voice_engine}:") or (
        tts_mode == "auto" and voice.startswith("edge:")
    )

    sample = voice_preview_sample("en")
    tts.set_voice(voice)
    tts.set_mode(tts_mode)
    tts.set_online_engine(online_engine)
    tts.set_offline_engine(offline_engine)
    tts.set_azure_credentials("key", "eastus")
    tts.set_google_tts_api_key("AIza-test")
    tts.set_elevenlabs_api_key("sk-test")
    tts.set_cartesia_api_key("sk_car_test")
    tts.set_murf_api_key("murf-test-key")

    if generator == "_generate_offline":
        def fake_offline(text, key, ctx):
            return _write_fake(tmp_path, suffix, tts, text)

        monkeypatch.setattr(tts, "_generate_offline", fake_offline)
        if tts_mode == "auto":
            monkeypatch.setattr(
                tts,
                "_generate_edge",
                lambda t, k, c: (_ for _ in ()).throw(RuntimeError("edge down")),
            )
            monkeypatch.setattr(
                tts,
                "_generate_azure",
                lambda t, k, c: (_ for _ in ()).throw(RuntimeError("azure down")),
            )
            monkeypatch.setattr(
                tts,
                "_generate_google",
                lambda t, k, c: (_ for _ in ()).throw(RuntimeError("google down")),
            )
    else:

        def fake_gen(text, key, ctx):
            return _write_fake(tmp_path, suffix, tts, text)

        monkeypatch.setattr(tts, generator, fake_gen)

    path = tts._generate_audio(sample, tts._cache_key(sample), tts._main_context())
    assert path.exists()
    assert path.stat().st_size > 0


def test_preview_sample_for_every_book_language():
    for lang_code, _name in BOOK_LANGUAGES:
        text = voice_preview_sample(lang_code)
        assert text.strip()
        assert lang_code == "en" or text != voice_preview_sample("en")


def test_preview_uses_non_advance_mode(qapp, tmp_path, monkeypatch):

    tts = _make_engine(tmp_path)
    tts.set_mode("online")
    tts.set_online_engine("edge")
    tts.set_voice(format_stored_voice("edge", "en-US-AriaNeural"))

    spoken: list[tuple[str, bool]] = []

    def fake_speak(text, *, advance=True):
        spoken.append((text, advance))

    monkeypatch.setattr(tts, "speak", fake_speak)
    tts.preview(voice_preview_sample("uk"))
    assert spoken == [(voice_preview_sample("uk"), False)]
