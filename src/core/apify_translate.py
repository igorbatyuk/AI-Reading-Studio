"""Apify Google Translate actor client."""

from __future__ import annotations

import logging
from typing import Any

import requests

logger = logging.getLogger(__name__)

DEFAULT_ACTOR = "maged120~google-translate-scraper"
SYNC_URL = (
    "https://api.apify.com/v2/acts/"
    f"{DEFAULT_ACTOR}/run-sync-get-dataset-items"
)


def translate_text(
    text: str,
    *,
    token: str,
    source_lang: str,
    target_lang: str,
    timeout: int = 120,
) -> tuple[str, str]:
    """Return (translation, error). Empty translation means failure."""
    text = text.strip()
    if not text:
        return "", ""
    if not token:
        return "", "Apify API token is missing"

    try:
        resp = requests.post(
            SYNC_URL,
            params={"token": token.strip()},
            json={
                "batch_items": [
                    {
                        "text": text,
                        "source_lang": source_lang or "auto",
                        "target_lang": target_lang,
                    }
                ]
            },
            timeout=timeout,
        )
    except requests.RequestException as exc:
        logger.warning("Apify translation request failed: %s", exc)
        return "", str(exc)

    if resp.status_code != 201 and resp.status_code != 200:
        detail = resp.text[:300]
        try:
            payload = resp.json()
            detail = payload.get("error", {}).get("message", detail)
        except Exception:
            pass
        return "", f"Apify HTTP {resp.status_code}: {detail}"

    try:
        payload = resp.json()
    except ValueError as exc:
        return "", f"Invalid Apify response: {exc}"

    item = _first_item(payload)
    if not item:
        return "", "Apify returned no translation items"

    if item.get("success") is False:
        return "", str(item.get("error") or "Apify translation failed")

    result = (
        item.get("translated_text")
        or item.get("output_text")
        or item.get("translation")
        or ""
    ).strip()
    if not result:
        return "", "Apify returned empty translation"
    return result, ""


def _first_item(payload: Any) -> dict[str, Any] | None:
    if isinstance(payload, list):
        return payload[0] if payload else None
    if isinstance(payload, dict):
        items = payload.get("items")
        if isinstance(items, list) and items:
            return items[0]
        data = payload.get("data")
        if isinstance(data, list) and data:
            return data[0]
    return None
