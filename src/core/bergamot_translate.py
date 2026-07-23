"""Mozilla Bergamot offline translation via bundled worker subprocess."""

from __future__ import annotations

import json
import logging
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

WORKER_SCRIPT = "bergamot_worker.py"
DEFAULT_TIMEOUT = 120


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def bundled_bergamot_dir() -> Path:
    return project_root() / "tts" / "bergamot"


def find_worker() -> Path | None:
    worker = bundled_bergamot_dir() / WORKER_SCRIPT
    return worker if worker.is_file() else None


def find_python() -> Path | None:
    base = bundled_bergamot_dir()
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


def model_code(source: str, target: str) -> str:
    return f"{source[:2]}{target[:2]}".lower()


def _run_worker(args: list[str], *, timeout: int = DEFAULT_TIMEOUT) -> dict:
    python = find_python()
    worker = find_worker()
    if not python or not worker:
        raise RuntimeError(
            "Bergamot not set up. Run tts/bergamot/setup.bat and download a model."
        )

    cmd = [str(python), str(worker), *args]
    try:
        completed = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            cwd=str(bundled_bergamot_dir()),
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("Bergamot translation timed out") from exc

    stdout = (completed.stdout or "").strip()
    if not stdout:
        stderr = (completed.stderr or "").strip()
        raise RuntimeError(stderr or "Bergamot worker produced no output")

    try:
        payload = json.loads(stdout.splitlines()[-1])
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid Bergamot worker output: {stdout[:200]}") from exc

    if completed.returncode != 0 or payload.get("error"):
        raise RuntimeError(payload.get("error") or "Bergamot worker failed")
    return payload


def worker_is_ready() -> bool:
    if not find_python() or not find_worker():
        return False
    try:
        payload = _run_worker(["ping"], timeout=15)
        return bool(payload.get("ok"))
    except Exception as exc:
        logger.debug("Bergamot ping failed: %s", exc)
        return False


def list_models() -> list[str]:
    payload = _run_worker(["list-models"], timeout=30)
    return list(payload.get("models") or [])


def has_model(source: str, target: str) -> bool:
    code = model_code(source, target)
    return code in list_models()


def is_available(source: str, target: str) -> bool:
    if source == target:
        return False
    if not worker_is_ready():
        return False
    try:
        return has_model(source, target)
    except Exception as exc:
        logger.debug("Bergamot model check failed: %s", exc)
        return False


def translate(text: str, source: str, target: str) -> str:
    text = text.strip()
    if not text:
        return ""
    if source == target:
        return text

    payload = _run_worker(
        [
            "translate",
            "--source",
            source,
            "--target",
            target,
            "--text",
            text,
        ],
        timeout=max(DEFAULT_TIMEOUT, min(300, 30 + len(text) // 20)),
    )
    result = (payload.get("text") or "").strip()
    if not result:
        raise RuntimeError("Bergamot returned empty translation")
    return result
