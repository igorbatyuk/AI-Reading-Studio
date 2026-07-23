"""Tests for Kokoro TTS helpers."""

from pathlib import Path

from src.core import kokoro_tts


def test_list_voices_for_english():
    voices = kokoro_tts.list_voices_for_language("en")
    ids = [voice_id for voice_id, _label in voices]
    assert "af_heart" in ids
    assert "bf_emma" in ids


def test_list_voices_for_french():
    voices = kokoro_tts.list_voices_for_language("fr")
    assert voices[0][0] == "ff_siwis"


def test_list_voices_for_ukrainian_empty():
    assert kokoro_tts.list_voices_for_language("uk") == []


def test_is_available_requires_models_and_runtime(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(kokoro_tts, "worker_is_available", lambda: False)
    monkeypatch.setattr(kokoro_tts, "find_kokoro_binary", lambda: None)
    assert kokoro_tts.is_available(tmp_path) is False
    model_dir = tmp_path / "kokoro_models"
    model_dir.mkdir()
    (model_dir / kokoro_tts.MODEL_ONNX).write_bytes(b"x")
    (model_dir / kokoro_tts.MODEL_VOICES).write_bytes(b"x")
    assert kokoro_tts.is_available(tmp_path) is False


def test_is_available_with_worker(tmp_path: Path, monkeypatch):
    model_dir = tmp_path / "kokoro_models"
    model_dir.mkdir()
    (model_dir / kokoro_tts.MODEL_ONNX).write_bytes(b"x")
    (model_dir / kokoro_tts.MODEL_VOICES).write_bytes(b"x")
    monkeypatch.setattr(kokoro_tts, "worker_is_available", lambda: True)
    assert kokoro_tts.is_available(tmp_path) is True


def test_generate_wav_uses_worker_subprocess(tmp_path: Path, monkeypatch):
    model_dir = tmp_path / "kokoro_models"
    model_dir.mkdir()
    (model_dir / kokoro_tts.MODEL_ONNX).write_bytes(b"x")
    (model_dir / kokoro_tts.MODEL_VOICES).write_bytes(b"x")

    calls: list[list[str]] = []

    def fake_worker(*args, **kwargs):
        calls.append(list(args[0]))
        out = Path(args[0][args[0].index("--output") + 1])
        out.write_bytes(b"RIFF")
        class Result:
            returncode = 0
            stdout = str(out)
            stderr = ""

        return Result()

    monkeypatch.setattr(kokoro_tts, "worker_is_available", lambda: True)
    monkeypatch.setattr(kokoro_tts, "find_kokoro_worker", lambda: Path("worker.py"))
    monkeypatch.setattr(kokoro_tts, "find_kokoro_python", lambda: Path("python312"))
    monkeypatch.setattr(kokoro_tts.subprocess, "run", fake_worker)

    out = kokoro_tts.generate_wav(
        "Hello",
        "af_heart",
        "en",
        tmp_path,
        speed=1.0,
    )
    assert out.exists()
    assert calls
    assert calls[0][0] == "python312"
    assert calls[0][1] == "worker.py"
    assert "--voice" in calls[0]
    assert "af_heart" in calls[0]


def test_generate_wav_falls_back_to_cli(tmp_path: Path, monkeypatch):
    model_dir = tmp_path / "kokoro_models"
    model_dir.mkdir()
    (model_dir / kokoro_tts.MODEL_ONNX).write_bytes(b"x")
    (model_dir / kokoro_tts.MODEL_VOICES).write_bytes(b"x")

    calls: list[list[str]] = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        out = Path(cmd[2])
        out.write_bytes(b"RIFF")
        class Result:
            returncode = 0
            stdout = ""
            stderr = ""

        return Result()

    monkeypatch.setattr(kokoro_tts, "worker_is_available", lambda: False)
    monkeypatch.setattr(kokoro_tts, "find_kokoro_binary", lambda: "kokoro-tts")
    monkeypatch.setattr(kokoro_tts.subprocess, "run", fake_run)

    out = kokoro_tts.generate_wav(
        "Hello",
        "af_heart",
        "en",
        tmp_path,
        speed=1.0,
    )
    assert out.exists()
    assert calls[0][0] == "kokoro-tts"


def test_prepare_text_for_kokoro_normalizes_quotes_and_whitespace():
    raw = "Hello \u201cworld\u201d.\n\nSecond\u2014line."
    cleaned = kokoro_tts.prepare_text_for_kokoro(raw)
    assert cleaned == 'Hello "world". Second-line.'


def test_split_text_for_kokoro_splits_long_passages():
    sentence = "Word " * 120
    text = f"{sentence.strip()}. {sentence.strip()}."
    chunks = kokoro_tts.split_text_for_kokoro(text, max_chars=200)
    assert len(chunks) >= 2
    assert all(len(chunk) <= 200 for chunk in chunks)
    assert "".join(chunks).replace(" ", "") != ""


def test_timeout_for_text_scales_with_length():
    short = kokoro_tts.timeout_for_text("Hello world.")
    long = kokoro_tts.timeout_for_text("Word " * 2000)
    assert short >= 180
    assert long > short
    assert long <= 900


def test_kokoro_lang_for_voice_uses_voice_definition():
    assert kokoro_tts.kokoro_lang_for_voice("bf_emma", "en") == "en-gb"
    assert kokoro_tts.kokoro_lang_for_voice("af_heart", "en") == "en-us"
    assert kokoro_tts.kokoro_lang_for_voice("ff_siwis", "en") == "fr-fr"


def test_split_text_for_kokoro_uses_smaller_default_chunks():
    sentence = "Word " * 120
    text = f"{sentence.strip()}. {sentence.strip()}."
    chunks = kokoro_tts.split_text_for_kokoro(text)
    assert len(chunks) >= 2
    assert all(len(chunk) <= 380 for chunk in chunks)


def test_generate_wav_rejects_empty_text_after_cleanup(tmp_path: Path, monkeypatch):
    model_dir = tmp_path / "kokoro_models"
    model_dir.mkdir()
    (model_dir / kokoro_tts.MODEL_ONNX).write_bytes(b"x")
    (model_dir / kokoro_tts.MODEL_VOICES).write_bytes(b"x")
    monkeypatch.setattr(kokoro_tts, "worker_is_available", lambda: True)

    try:
        kokoro_tts.generate_wav("***", "af_heart", "en", tmp_path, speed=1.0)
    except RuntimeError as exc:
        assert "Empty text" in str(exc)
    else:
        raise AssertionError("Expected empty text failure")
