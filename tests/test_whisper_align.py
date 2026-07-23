"""Tests for Whisper word alignment helpers."""

from pathlib import Path

from src.core import whisper_align


def test_normalize_mode():
    assert whisper_align.normalize_mode("OFF") == "off"
    assert whisper_align.normalize_mode("invalid") == "auto"


def test_map_whisper_words_to_text():
    text = "Hello brave world"
    whisper_words = [
        {"word": "Hello", "start_ms": 0, "end_ms": 400},
        {"word": "brave", "start_ms": 410, "end_ms": 800},
        {"word": "world", "start_ms": 810, "end_ms": 1200},
    ]
    timings = whisper_align.map_whisper_words_to_text(text, whisper_words)
    assert timings == [(0, 400), (410, 800), (810, 1200)]


def test_map_whisper_words_requires_enough_matches():
    text = "One two three four five six"
    whisper_words = [{"word": "One", "start_ms": 0, "end_ms": 100}]
    assert whisper_align.map_whisper_words_to_text(text, whisper_words) == []


def test_try_align_words_off_mode(tmp_path: Path):
    audio = tmp_path / "a.wav"
    audio.write_bytes(b"x")
    assert (
        whisper_align.try_align_words("hello", audio, lang="en", mode="off") is None
    )


def test_try_align_words_uses_worker(monkeypatch, tmp_path: Path, qapp):
    audio = tmp_path / "a.wav"
    audio.write_bytes(b"wav")
    monkeypatch.setattr(whisper_align, "is_worker_available", lambda: True)
    monkeypatch.setattr(
        whisper_align,
        "_run_worker",
        lambda _audio, _lang, timeout=300: [
            {"word": "Hello", "start_ms": 0, "end_ms": 300},
            {"word": "world", "start_ms": 310, "end_ms": 700},
        ],
    )

    timings = whisper_align.try_align_words(
        "Hello world", audio, lang="en", mode="on"
    )
    assert timings == [(0, 300), (310, 700)]


def test_finalize_uses_whisper_timings(qapp, tmp_path: Path, monkeypatch):
    import json
    import wave

    from src.core.tts_engine import TTSEngine

    tts = TTSEngine()
    tts.set_app_dir(tmp_path)
    tts.set_whisper_word_align("on")
    text = "Hello world"
    key = tts._cache_key(text)
    wav_path = tts._cache_file_path(key, ".wav")
    rate = 22050
    with wave.open(str(wav_path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(b"\x00\x00" * rate)

    monkeypatch.setattr(
        "src.core.whisper_align.try_align_words",
        lambda *_a, **_k: [(0, 400), (410, 900)],
    )

    tts._finalize_generated_audio(text, key, wav_path)
    raw = json.loads(tts._timings_path(key).read_text(encoding="utf-8"))
    assert raw["estimated"] is False
    assert len(raw["words"]) == 2
