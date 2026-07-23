"""DeepL API translation client."""

from __future__ import annotations

import logging

import requests

logger = logging.getLogger(__name__)

FREE_API_URL = "https://api-free.deepl.com/v2/translate"
PRO_API_URL = "https://api.deepl.com/v2/translate"

LANG_MAP: dict[str, str] = {
    "en": "EN",
    "uk": "UK",
    "de": "DE",
    "fr": "FR",
    "es": "ES",
    "pl": "PL",
    "it": "IT",
    "pt": "PT",
    "nl": "NL",
    "sv": "SV",
    "da": "DA",
    "fi": "FI",
    "cs": "CS",
    "ja": "JA",
    "ko": "KO",
    "nb": "NB",
    "ru": "RU",
    "zh": "ZH",
}


def api_url(api_key: str) -> str:
    cleaned = api_key.strip()
    if cleaned.endswith(":fx"):
        return FREE_API_URL
    return PRO_API_URL


def to_deepl_lang(code: str) -> str:
    return LANG_MAP.get((code or "").strip().lower(), "")


def translate_text(
    text: str,
    *,
    api_key: str,
    source_lang: str,
    target_lang: str,
    timeout: int = 30,
) -> tuple[str, str]:
    """Return (translation, error). Empty translation means failure."""
    text = text.strip()
    if not text:
        return "", ""
    if not api_key:
        return "", "DeepL API key is missing"

    target = to_deepl_lang(target_lang)
    if not target:
        return "", f"DeepL does not support target language: {target_lang}"

    data: dict[str, str] = {"text": text, "target_lang": target}
    source = to_deepl_lang(source_lang)
    if source and source != target:
        data["source_lang"] = source

    try:
        resp = requests.post(
            api_url(api_key),
            data=data,
            headers={"Authorization": f"DeepL-Auth-Key {api_key.strip()}"},
            timeout=timeout,
        )
    except requests.RequestException as exc:
        logger.warning("DeepL translation request failed: %s", exc)
        return "", str(exc)

    if resp.status_code != 200:
        detail = resp.text[:300]
        try:
            payload = resp.json()
            detail = payload.get("message", detail)
        except Exception:
            pass
        return "", f"DeepL HTTP {resp.status_code}: {detail}"

    try:
        payload = resp.json()
        translations = payload.get("translations") or []
        result = (translations[0].get("text") if translations else "") or ""
        result = result.strip()
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        return "", f"Invalid DeepL response: {exc}"

    if not result:
        return "", "DeepL returned empty translation"
    return result, ""
