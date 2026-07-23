"""Tests for Azure Speech TTS client."""

from src.core import azure_tts


def test_list_voices_for_english():
    voices = azure_tts.list_voices_for_language("en")
    assert voices
    assert voices[0][0].startswith("en-")


def test_synthesize_mp3(monkeypatch):
    captured: dict = {}

    class FakeResp:
        status_code = 200
        content = b"mp3-bytes"

    def fake_post(url, data, headers, timeout):
        captured["url"] = url
        captured["data"] = data.decode("utf-8")
        captured["headers"] = headers
        return FakeResp()

    monkeypatch.setattr(azure_tts.requests, "post", fake_post)

    audio = azure_tts.synthesize_mp3(
        "Hello",
        voice="en-US-JennyNeural",
        lang="en",
        api_key="test-key",
        region="eastus",
        speed=1.0,
    )
    assert audio == b"mp3-bytes"
    assert "eastus.tts.speech.microsoft.com" in captured["url"]
    assert "JennyNeural" in captured["data"]
    assert captured["headers"]["Ocp-Apim-Subscription-Key"] == "test-key"
