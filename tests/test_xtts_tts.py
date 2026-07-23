"""Tests for XTTS TTS helpers."""

from pathlib import Path

from src.core import xtts_tts


def test_list_voices_without_speakers(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(
        xtts_tts,
        "bundled_speakers_dir",
        lambda: tmp_path / "missing_speakers",
    )
    voices = xtts_tts.list_voices_for_language("en", tmp_path)
    assert voices[0][0] == xtts_tts.DEFAULT_SPEAKER


def test_list_voices_from_legacy_folder(tmp_path: Path):
    speakers = tmp_path / "xtts_speakers"
    speakers.mkdir()
    (speakers / "alice.wav").write_bytes(b"RIFF")
    voices = xtts_tts.list_voices_for_language("en", tmp_path)
    assert ("alice", "XTTS — alice") in voices


def test_is_available_requires_speakers_and_runtime(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(xtts_tts, "worker_is_available", lambda: False)
    assert xtts_tts.is_available(tmp_path) is False
    speakers = tmp_path / "xtts_speakers"
    speakers.mkdir()
    (speakers / "demo.wav").write_bytes(b"RIFF")
    assert xtts_tts.is_available(tmp_path) is False


def test_is_available_with_worker(tmp_path: Path, monkeypatch):
    speakers = tmp_path / "xtts_speakers"
    speakers.mkdir()
    (speakers / "demo.wav").write_bytes(b"RIFF")
    monkeypatch.setattr(xtts_tts, "worker_is_available", lambda: True)
    assert xtts_tts.is_available(tmp_path) is True


def test_generate_wav_uses_worker_subprocess(tmp_path: Path, monkeypatch):
    speakers = tmp_path / "xtts_speakers"
    speakers.mkdir()
    (speakers / "demo.wav").write_bytes(b"RIFF")

    calls: list[list[str]] = []

    def fake_run(cmd, **kwargs):
        calls.append(list(cmd))
        out = Path(cmd[cmd.index("--output") + 1])
        out.write_bytes(b"RIFF")

        class Result:
            returncode = 0
            stdout = str(out)
            stderr = ""

        return Result()

    monkeypatch.setattr(xtts_tts, "worker_is_available", lambda: True)
    monkeypatch.setattr(xtts_tts, "find_xtts_worker", lambda: Path("xtts_worker.py"))
    monkeypatch.setattr(xtts_tts, "find_xtts_python", lambda: Path("python311"))
    monkeypatch.setattr(xtts_tts.subprocess, "run", fake_run)

    out = xtts_tts.generate_wav("Hello", "demo", "en", tmp_path, speed=1.0)
    assert out.exists()
    assert calls
    assert calls[0][0] == "python311"
    assert calls[0][1] == "xtts_worker.py"
    assert "--speakers-dir" in calls[0]
