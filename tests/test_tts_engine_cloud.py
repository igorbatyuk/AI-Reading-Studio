"""Tests for TTSEngine cloud/offline routing."""

from pathlib import Path

import pytest

from src.core.tts_engine import TTSEngine


@pytest.fixture
def engine(tmp_path: Path) -> TTSEngine:
    tts = TTSEngine("azure:en-US-JennyNeural")
    tts.set_app_dir(tmp_path)
    tts.set_offline_language("en")
    tts.set_azure_credentials("key", "eastus")
    tts.set_google_tts_api_key("AIza-test")
    return tts


def test_online_azure_uses_azure_generator(engine: TTSEngine, monkeypatch):
    called = {"azure": False}

    def fake_azure(text, key, ctx, *, for_word=False):
        called["azure"] = True
        path = engine._cache_file_path(key, ".mp3", for_word=for_word)
        path.write_bytes(b"mp3")
        return path

    monkeypatch.setattr(engine, "_generate_azure", fake_azure)
    engine.set_mode("online")
    engine.set_online_engine("azure")
    path = engine._generate_audio(
        "hello", engine._cache_key("hello"), engine._main_context()
    )
    assert called["azure"]
    assert path.exists()


def test_auto_falls_back_to_offline(engine: TTSEngine, monkeypatch):
    monkeypatch.setattr(engine, "_generate_edge", lambda t, k, c, **kw: (_ for _ in ()).throw(RuntimeError("edge down")))
    monkeypatch.setattr(engine, "_generate_azure", lambda t, k, c, **kw: (_ for _ in ()).throw(RuntimeError("azure down")))
    monkeypatch.setattr(engine, "_generate_google", lambda t, k, c, **kw: (_ for _ in ()).throw(RuntimeError("google down")))

    def fake_offline(text, key, ctx, *, for_word=False):
        path = engine._cache_file_path(key, ".wav", for_word=for_word)
        path.write_bytes(b"wav")
        return path

    monkeypatch.setattr(engine, "_generate_offline", fake_offline)
    engine.set_mode("auto")
    path = engine._generate_audio(
        "hello", engine._cache_key("hello"), engine._main_context()
    )
    assert path.suffix == ".wav"
