"""Local StyleTTS2 via bundled worker subprocess or external CLI."""

from __future__ import annotations

import logging
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "default"
WORKER_SCRIPT = "styletts2_worker.py"


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def bundled_styletts2_dir() -> Path:
    return project_root() / "tts" / "styletts2"


def models_dir(app_dir: Path) -> Path:
    return app_dir / "styletts2_models"


def find_styletts2_worker() -> Path | None:
    worker = bundled_styletts2_dir() / WORKER_SCRIPT
    return worker if worker.is_file() else None


def find_styletts2_python() -> Path | None:
    base = bundled_styletts2_dir()
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
    return find_styletts2_worker() is not None and find_styletts2_python() is not None


def find_binary() -> str | None:
    worker = find_styletts2_worker()
    python_bin = find_styletts2_python()
    if worker and python_bin:
        return str(python_bin)
    for name in ("styletts2", "styletts2.exe"):
        path = shutil.which(name)
        if path:
            return path
    return None


def is_available(app_dir: Path, custom_model: str = "") -> bool:
    if find_binary() is None:
        return False
    if custom_model and Path(custom_model).exists():
        return True
    folder = models_dir(app_dir)
    return folder.exists() and any(folder.rglob("*.pth"))


def list_voices_for_language(lang_code: str, app_dir: Path, custom_model: str = "") -> list[tuple[str, str]]:
    _ = lang_code
    voices: list[tuple[str, str]] = []
    seen: set[str] = set()

    if custom_model:
        stem = Path(custom_model).stem
        seen.add(stem)
        voices.append((stem, f"StyleTTS2 — {stem}"))

    folder = models_dir(app_dir)
    if folder.exists():
        for path in sorted(folder.rglob("*.pth")):
            stem = path.stem
            if stem in seen:
                continue
            seen.add(stem)
            voices.append((stem, f"StyleTTS2 — {stem}"))

    if not voices:
        voices.append((DEFAULT_MODEL, "StyleTTS2 — default (add .pth to styletts2_models/)"))
    return voices


def resolve_model(voice: str, app_dir: Path, custom_model: str) -> Path | None:
    if custom_model:
        path = Path(custom_model)
        if path.exists():
            return path
    folder = models_dir(app_dir)
    if not folder.exists():
        return None
    if voice and voice != DEFAULT_MODEL:
        for candidate in folder.rglob(f"{voice}.pth"):
            return candidate
        for candidate in folder.rglob(f"*{voice}*.pth"):
            return candidate
    models = sorted(folder.rglob("*.pth"))
    return models[0] if models else None


def _styletts2_speed_value(speed: float) -> str:
    from .tts_speed import engine_speech_rate

    return str(engine_speech_rate(speed))


def _generate_via_worker(
    text: str,
    model: Path,
    speed: float,
    out_path: Path,
) -> Path:
    worker = find_styletts2_worker()
    python_bin = find_styletts2_python()
    if not worker or not python_bin:
        raise RuntimeError(
            "StyleTTS2 worker not found. Run tts/styletts2/setup.bat (Python 3.10 venv)."
        )

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, encoding="utf-8"
    ) as tmp_in:
        tmp_in.write(text)
        text_file = Path(tmp_in.name)

    try:
        cmd = [
            str(python_bin),
            str(worker),
            "--text-file",
            str(text_file),
            "--output",
            str(out_path),
            "--model",
            str(model),
            "--speed",
            _styletts2_speed_value(speed),
        ]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=600,
            cwd=str(worker.parent),
        )
    finally:
        text_file.unlink(missing_ok=True)

    if result.returncode != 0:
        out_path.unlink(missing_ok=True)
        raise RuntimeError((result.stderr or result.stdout or "StyleTTS2 worker failed").strip())

    if not out_path.exists() or out_path.stat().st_size == 0:
        out_path.unlink(missing_ok=True)
        raise RuntimeError("StyleTTS2 produced no audio")
    return out_path


def _generate_via_cli(
    text: str,
    model: Path,
    speed: float,
    out_path: Path,
) -> Path:
    binary = find_binary()
    if not binary:
        raise RuntimeError("styletts2 CLI not found in PATH")

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, encoding="utf-8"
    ) as tmp_in:
        tmp_in.write(text)
        input_path = Path(tmp_in.name)

    try:
        cmd = [
            binary,
            "--text",
            str(input_path),
            "--model",
            str(model),
            "--output",
            str(out_path),
            "--speed",
            _styletts2_speed_value(speed),
        ]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=600,
        )
    finally:
        input_path.unlink(missing_ok=True)

    if result.returncode != 0:
        out_path.unlink(missing_ok=True)
        raise RuntimeError(result.stderr or result.stdout or "StyleTTS2 failed")

    if not out_path.exists() or out_path.stat().st_size == 0:
        out_path.unlink(missing_ok=True)
        raise RuntimeError("StyleTTS2 produced no audio")
    return out_path


def generate_wav(
    text: str,
    voice: str,
    lang: str,
    app_dir: Path,
    custom_model: str = "",
    speed: float = 1.0,
    out_path: Path | None = None,
) -> Path:
    _ = lang
    model = resolve_model(voice, app_dir, custom_model)
    if model is None:
        raise RuntimeError(
            "StyleTTS2 model not found. Place .pth + config.yml in "
            "~/.ai_reading_studio/styletts2_models/"
        )

    if out_path is None:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            out_path = Path(tmp.name)

    if worker_is_available():
        return _generate_via_worker(text, model, speed, out_path)
    return _generate_via_cli(text, model, speed, out_path)
