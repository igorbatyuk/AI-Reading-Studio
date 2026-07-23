"""Neural offline TTS via Piper CLI."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

# Fallback when folder is empty (voice list placeholder only).
MODEL_HINTS: dict[str, str] = {
    "en": "en_US-lessac-medium.onnx",
    "uk": "uk_UA-lada-x_low.onnx",
    "de": "de_DE-thorsten-medium.onnx",
    "fr": "fr_FR-siwis-medium.onnx",
    "es": "es_ES-sharvard-medium.onnx",
    "pl": "pl_PL-gosia-medium.onnx",
    "ru": "ru_RU-ruslan-medium.onnx",
}


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def bundled_piper_dir() -> Path:
    return project_root() / "tts" / "piper"


def find_piper_install_dir() -> Path | None:
    bundled = bundled_piper_dir()
    for folder in (bundled / "piper", bundled):
        exe = folder / "piper.exe"
        if exe.is_file() and (folder / "onnxruntime.dll").is_file():
            return folder
    return None


def find_piper_binary() -> str | None:
    for name in ("piper", "piper.exe"):
        path = shutil.which(name)
        if path:
            return path
    install = find_piper_install_dir()
    if install:
        return str(install / "piper.exe")
    return None


def _model_added_timestamp(path: Path) -> float:
    try:
        stat = path.stat()
    except OSError:
        return 0.0
    if os.name == "nt":
        return stat.st_ctime
    birthtime = getattr(stat, "st_birthtime", None)
    if birthtime:
        return birthtime
    return stat.st_mtime


def list_models(app_dir: Path) -> list[tuple[str, Path]]:
    """Return Piper .onnx models oldest-first (by file add/modify time)."""
    candidates: list[Path] = []

    bundled = bundled_piper_dir()
    if bundled.is_dir():
        candidates.extend(bundled.glob("*.onnx"))

    legacy_dir = app_dir / "piper_models"
    if legacy_dir.is_dir():
        candidates.extend(legacy_dir.rglob("*.onnx"))

    candidates.sort(key=lambda path: (_model_added_timestamp(path), path.name.lower()))

    seen: set[str] = set()
    models: list[tuple[str, Path]] = []
    for path in candidates:
        stem = path.stem
        if stem in seen:
            continue
        seen.add(stem)
        models.append((stem, path))

    return models


def _pick_model(candidates: list[Path], hint: str) -> Path | None:
    if hint:
        for candidate in candidates:
            if hint in candidate.name:
                return candidate
    return candidates[0] if candidates else None


def resolve_model(
    lang: str,
    custom_path: str,
    app_dir: Path,
    voice: str = "",
) -> Path | None:
    if voice:
        for stem, path in list_models(app_dir):
            if stem == voice:
                return path

    if custom_path:
        path = Path(custom_path)
        if path.exists():
            return path
        stem = path.stem
        for model_stem, model_path in list_models(app_dir):
            if model_stem == stem:
                return model_path

    models = list_models(app_dir)
    if models:
        hint = MODEL_HINTS.get(lang, "")
        if hint:
            for stem, path in models:
                if hint in path.name:
                    return path
        return models[0][1]

    return None


def is_available(lang: str, custom_path: str, app_dir: Path) -> bool:
    return find_piper_binary() is not None and bool(list_models(app_dir))


def list_voices_for_language(lang_code: str, app_dir: Path) -> list[tuple[str, str]]:
    _ = lang_code
    models = list_models(app_dir)
    if models:
        return [(stem, f"Piper — {stem}") for stem, _path in models]
    hint = MODEL_HINTS.get(lang_code, "model.onnx")
    return [(Path(hint).stem, f"Piper — {hint} (add .onnx to tts/piper/)")]


def generate_wav(
    text: str,
    lang: str,
    custom_path: str,
    app_dir: Path,
    speed: float = 1.0,
    out_path: Path | None = None,
    voice: str = "",
) -> Path:
    piper = find_piper_binary()
    if not piper:
        raise RuntimeError(
            "Piper binary not found. Run tts/piper/setup.bat or add piper to PATH."
        )

    model = resolve_model(lang, custom_path, app_dir, voice=voice)
    if not model:
        raise RuntimeError(
            "Piper model not found. Place .onnx files in tts/piper/ or "
            "~/.ai_reading_studio/piper_models/"
        )

    if out_path is None:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            out_path = Path(tmp.name)

    from .tts_speed import piper_length_scale

    length_scale = piper_length_scale(speed)
    cmd = [
        piper,
        "--model",
        str(model),
        "--output_file",
        str(out_path),
        "--length_scale",
        str(length_scale),
    ]

    result = subprocess.run(
        cmd,
        input=text,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=180,
        cwd=str(find_piper_install_dir() or Path(piper).parent),
    )
    if result.returncode != 0:
        out_path.unlink(missing_ok=True)
        raise RuntimeError(result.stderr or result.stdout or "Piper failed")

    if not out_path.exists() or out_path.stat().st_size == 0:
        out_path.unlink(missing_ok=True)
        raise RuntimeError("Piper produced no audio")

    return out_path
