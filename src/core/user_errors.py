"""Turn raw API / engine errors into clear user-facing messages."""

from __future__ import annotations

from .i18n import tr


def _short_detail(raw: str, max_len: int = 140) -> str:
    text = " ".join(raw.strip().split())
    if len(text) <= max_len:
        return text
    return text[: max_len - 1] + "…"


def humanize_error(raw: str, *, area: str = "general") -> str:
    """Map technical errors to localized guidance (area: tts | translation | preview)."""
    if not raw or not raw.strip():
        return tr(f"errors.{area}.unknown")

    lower = raw.lower()

    if "apify api token is missing" in lower:
        return tr("errors.apify.no_token")

    if "apify" in lower and (
        "402" in raw
        or "memory limit" in lower
        or "exceed the memory limit" in lower
    ):
        return tr("errors.apify.memory_limit")

    if "apify" in lower and any(code in raw for code in ("401", "403")):
        return tr("errors.apify.auth")

    if "apify" in lower and "429" in raw:
        return tr("errors.apify.rate_limit")

    if "apify http" in lower or lower.startswith("apify "):
        return tr("errors.apify.generic", detail=_short_detail(raw))

    if "monthly limit reached" in lower or "limit exhausted" in lower:
        if area == "translation":
            return tr("errors.translation.quota")
        return tr("errors.tts.quota")

    if "character limit" in lower or "quota" in lower and "exhausted" in lower:
        return tr("errors.tts.quota")

    if "all translation providers failed" in lower:
        return tr("errors.translation.all_failed")

    if "all tts engines failed" in lower:
        return tr("errors.tts.all_failed")

    if "piper not configured" in lower or (
        "piper" in lower and ("not found" in lower or "no .onnx" in lower)
    ):
        return tr("errors.tts.piper")

    if "kokoro not configured" in lower or (
        "kokoro" in lower and "not found" in lower
    ):
        return tr("errors.tts.kokoro")

    if "xtts not configured" in lower:
        return tr("errors.tts.xtts")

    if "styletts2 not configured" in lower:
        return tr("errors.tts.styletts2")

    if "azure speech api key is missing" in lower:
        return tr("errors.tts.azure_key")

    if "azure speech region is missing" in lower:
        return tr("errors.tts.azure_region")

    if "elevenlabs api key is missing" in lower:
        return tr("errors.tts.elevenlabs_key")

    if "cartesia api key is missing" in lower:
        return tr("errors.tts.cartesia_key")

    if "murf api key is missing" in lower:
        return tr("errors.tts.murf_key")

    if "google cloud tts api key is missing" in lower:
        return tr("errors.tts.google_key")

    if "google cloud http 403" in lower or "google cloud http 401" in lower:
        if area == "translation":
            return tr("errors.google.auth_translate")
        return tr("errors.google.auth_tts")

    if "google cloud http 429" in lower:
        return tr("errors.google.quota")

    if "google cloud" in lower and area == "translation":
        return tr("errors.google.translate_generic", detail=_short_detail(raw))

    if "deepl" in lower and any(code in raw for code in ("401", "403")):
        return tr("errors.deepl.auth")

    if "deepl" in lower and ("456" in raw or "quota" in lower):
        return tr("errors.deepl.quota")

    if "deepl" in lower:
        return tr("errors.deepl.generic", detail=_short_detail(raw))

    if "bergamot" in lower:
        return tr("errors.bergamot.generic")

    if "ollama" in lower or "no ollama model" in lower:
        return tr("errors.ollama.generic", detail=_short_detail(raw))

    if any(
        token in lower
        for token in (
            "timeout",
            "timed out",
            "connection refused",
            "connection error",
            "network is unreachable",
            "failed to establish",
            "name resolution",
            "temporary failure",
        )
    ):
        return tr("errors.network", detail=_short_detail(raw))

    if "edge" in lower and area == "tts":
        return tr("errors.tts.edge_generic", detail=_short_detail(raw))

    if area == "translation":
        return tr("errors.translation.generic", detail=_short_detail(raw))
    if area in ("tts", "preview"):
        return tr("errors.tts.generic", detail=_short_detail(raw))
    return tr("errors.general.generic", detail=_short_detail(raw))
