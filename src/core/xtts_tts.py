"""Local XTTS v2 TTS via Coqui TTS (Python 3.11 worker subprocess)."""

from __future__ import annotations

import logging
import subprocess
import sys
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "tts_models/multilingual/multi-dataset/xtts_v2"
DEFAULT_SPEAKER = "default"
WORKER_SCRIPT = "xtts_worker.py"


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def bundled_xtts_dir() -> Path:
    return project_root() / "tts" / "xtts"


def bundled_speakers_dir() -> Path:
    return bundled_xtts_dir() / "speakers"


def legacy_speakers_dir(app_dir: Path) -> Path:
    return app_dir / "xtts_speakers"


def find_xtts_worker() -> Path | None:
    worker = bundled_xtts_dir() / WORKER_SCRIPT
    return worker if worker.is_file() else None


def find_xtts_python() -> Path | None:
    base = bundled_xtts_dir()
    if sys.platform == "win32":
        candidates = (
            base / ".venv" / "Scripts" / "python.exe",
            base / ".venv" / "Scripts" / "python3.exe",
        )
    else:
        candidates = (
            base / ".venv" / "bin" / "python3",
            base / ".venv" / "bin" / "python",
        )
    for path in candidates:
        if path.is_file():
            return path
    return None


def worker_is_available() -> bool:
    return find_xtts_worker() is not None and find_xtts_python() is not None


def _speaker_wavs_in(folder: Path) -> list[Path]:
    if not folder.is_dir():
        return []
    return sorted(folder.glob("*.wav"))


def speaker_directories(app_dir: Path) -> list[Path]:
    dirs: list[Path] = []
    bundled = bundled_speakers_dir()
    if _speaker_wavs_in(bundled):
        dirs.append(bundled)
    legacy = legacy_speakers_dir(app_dir)
    if _speaker_wavs_in(legacy):
        dirs.append(legacy)
    return dirs


def has_speakers(app_dir: Path) -> bool:
    return bool(speaker_directories(app_dir))


def is_available(app_dir: Path) -> bool:
    if not has_speakers(app_dir):
        return False
    if worker_is_available():
        return True
    try:
        from TTS.api import TTS  # noqa: F401
    except ImportError:
        return False
    return True


def list_voices_for_language(lang_code: str, app_dir: Path) -> list[tuple[str, str]]:
    _ = lang_code
    voices: list[tuple[str, str]] = []
    seen: set[str] = set()
    for folder in speaker_directories(app_dir):
        for path in _speaker_wavs_in(folder):
            voice_id = path.stem
            if voice_id in seen:
                continue
            seen.add(voice_id)
            voices.append((voice_id, f"XTTS — {voice_id}"))
    if not voices:
        voices.append(
            (
                DEFAULT_SPEAKER,
                "XTTS — default speaker (add .wav to tts/xtts/speakers/)",
            )
        )
    return voices


def resolve_speaker_wav(voice: str, app_dir: Path) -> Path | None:
    folders = speaker_directories(app_dir)
    if not folders:
        return None
    if voice and voice != DEFAULT_SPEAKER:
        for folder in folders:
            candidate = folder / f"{voice}.wav"
            if candidate.is_file():
                return candidate
    for folder in folders:
        wavs = _speaker_wavs_in(folder)
        if wavs:
            return wavs[0]
    return None


def _generate_via_worker(
    text: str,
    voice: str,
    lang: str,
    app_dir: Path,
    speed: float,
    out_path: Path,
) -> Path:
    worker = find_xtts_worker()
    python_bin = find_xtts_python()
    if not worker or not python_bin:
        raise RuntimeError(
            "XTTS worker not found. Run tts/xtts/setup.bat (Python 3.11 venv)."
        )

    speaker_dirs = speaker_directories(app_dir)
    if not speaker_dirs:
        raise RuntimeError(
            "No XTTS speaker .wav found. Add reference audio to "
            "tts/xtts/speakers/ or ~/.ai_reading_studio/xtts_speakers/"
        )

    from .tts_speed import engine_speech_rate

    speed_value = engine_speech_rate(speed)

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, encoding="utf-8"
    ) as tmp_in:
        tmp_in.write(text)
        text_file = Path(tmp_in.name)

    cmd = [
        str(python_bin),
        str(worker),
        "--text-file",
        str(text_file),
        "--output",
        str(out_path),
        "--voice",
        voice or DEFAULT_SPEAKER,
        "--lang",
        lang,
        "--speed",
        str(speed_value),
        "--model",
        DEFAULT_MODEL,
    ]
    for folder in speaker_dirs:
        cmd.extend(["--speakers-dir", str(folder)])

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=600,
        )
    finally:
        text_file.unlink(missing_ok=True)

    if result.returncode != 0:
        out_path.unlink(missing_ok=True)
        detail = (result.stderr or result.stdout or "XTTS worker failed").strip()
        raise RuntimeError(detail)

    if not out_path.exists() or out_path.stat().st_size == 0:
        out_path.unlink(missing_ok=True)
        raise RuntimeError("XTTS produced no audio")

    return out_path


def _generate_inline(
    text: str,
    voice: str,
    lang: str,
    app_dir: Path,
    speed: float,
    out_path: Path,
) -> Path:
    try:
        from TTS.api import TTS
    except ImportError as exc:
        raise RuntimeError(
            "Coqui TTS not installed. Run tts/xtts/setup.bat"
        ) from exc

    speaker_wav = resolve_speaker_wav(voice, app_dir)
    if speaker_wav is None:
        raise RuntimeError(
            "No XTTS speaker .wav found. Add reference audio to "
            "tts/xtts/speakers/ or ~/.ai_reading_studio/xtts_speakers/"
        )

    lang_map = {
        "en": "en",
        "uk": "uk",
        "ru": "ru",
        "de": "de",
        "fr": "fr",
        "es": "es",
        "it": "it",
        "pt": "pt",
        "pl": "pl",
        "nl": "nl",
        "ja": "ja",
        "zh": "zh-cn",
    }

    tts = TTS(DEFAULT_MODEL, gpu=False)
    from .tts_speed import engine_speech_rate

    tts.tts_to_file(
        text=text,
        speaker_wav=str(speaker_wav),
        language=lang_map.get(lang, "en"),
        file_path=str(out_path),
        speed=engine_speech_rate(speed),
    )
    if not out_path.exists() or out_path.stat().st_size == 0:
        raise RuntimeError("XTTS produced no audio")
    return out_path


def generate_wav(
    text: str,
    voice: str,
    lang: str,
    app_dir: Path,
    speed: float = 1.0,
    out_path: Path | None = None,
) -> Path:
    if out_path is None:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            out_path = Path(tmp.name)

    if worker_is_available():
        return _generate_via_worker(text, voice, lang, app_dir, speed, out_path)

    return _generate_inline(text, voice, lang, app_dir, speed, out_path)
