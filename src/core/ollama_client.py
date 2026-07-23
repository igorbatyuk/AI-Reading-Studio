"""Local LLM client for Ollama (http://localhost:11434)."""

from __future__ import annotations

import logging
from typing import Any

import requests

logger = logging.getLogger(__name__)

DEFAULT_URL = "http://127.0.0.1:11434"
DEFAULT_TIMEOUT = 90


def normalize_url(url: str) -> str:
    value = (url or DEFAULT_URL).strip().rstrip("/")
    return value or DEFAULT_URL


def is_available(base_url: str, timeout: float = 3.0) -> bool:
    try:
        response = requests.get(f"{normalize_url(base_url)}/api/tags", timeout=timeout)
        return response.status_code == 200
    except Exception as exc:
        logger.debug("Ollama unavailable at %s: %s", base_url, exc)
        return False


def list_models(base_url: str, timeout: float = 5.0) -> list[str]:
    try:
        response = requests.get(f"{normalize_url(base_url)}/api/tags", timeout=timeout)
        response.raise_for_status()
        models = response.json().get("models") or []
        return [item.get("name", "") for item in models if item.get("name")]
    except Exception as exc:
        logger.debug("Failed to list Ollama models: %s", exc)
        return []


def resolve_model(base_url: str, preferred: str) -> str:
    preferred = (preferred or "").strip()
    if preferred:
        return preferred
    models = list_models(base_url)
    return models[0] if models else ""


def chat(
    base_url: str,
    model: str,
    system: str,
    user: str,
    *,
    timeout: int = DEFAULT_TIMEOUT,
    json_mode: bool = False,
) -> str:
    resolved = resolve_model(base_url, model)
    if not resolved:
        raise RuntimeError("No Ollama model configured or available")

    payload: dict[str, Any] = {
        "model": resolved,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "stream": False,
    }
    if json_mode:
        payload["format"] = "json"

    response = requests.post(
        f"{normalize_url(base_url)}/api/chat",
        json=payload,
        timeout=timeout,
    )
    response.raise_for_status()
    content = response.json().get("message", {}).get("content", "")
    return (content or "").strip()
