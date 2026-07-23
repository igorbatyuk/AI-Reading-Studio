"""Tests for Google Cloud Text-to-Speech client."""

import base64

from src.core import google_cloud_tts


def test_list_voices_for_english():
    voices = google_cloud_tts.list_voices_for_language("en")
    assert voices
    assert "Neural2" in voices[0][0]


def test_synthesize_mp3(monkeypatch):
    payload = {"audioContent": base64.b64encode(b"mp3-bytes").decode("ascii")}
    captured: dict = {}

    class FakeResp:
        status_code = 200

        @staticmethod
        def json():
            return payload

    def fake_post(url, params, json, timeout):
        captured["params"] = params
        captured["json"] = json
        return FakeResp()

    monkeypatch.setattr(google_cloud_tts.requests, "post", fake_post)

    audio = google_cloud_tts.synthesize_mp3(
        "Hello",
        voice="en-US-Neural2-F",
        lang="en",
        api_key="AIza-test",
        speed=1.0,
    )
    assert audio == b"mp3-bytes"
    assert captured["params"]["key"] == "AIza-test"
    assert captured["json"]["input"]["text"] == "Hello"
