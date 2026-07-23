"""Tests for Ollama client helpers."""

from src.core import ollama_client


def test_normalize_url():
    assert ollama_client.normalize_url("") == ollama_client.DEFAULT_URL
    assert ollama_client.normalize_url("http://127.0.0.1:11434/") == "http://127.0.0.1:11434"


def test_resolve_model_prefers_configured():
    assert ollama_client.resolve_model("http://127.0.0.1:11434", "mistral") == "mistral"


def test_is_available_false_when_unreachable(monkeypatch):
    def _fail(*args, **kwargs):
        raise ConnectionError("offline")

    monkeypatch.setattr(ollama_client.requests, "get", _fail)
    assert ollama_client.is_available("http://127.0.0.1:11434") is False
