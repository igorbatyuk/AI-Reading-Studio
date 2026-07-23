"""Tests for user-facing error messages."""

from src.core import i18n
from src.core.user_errors import humanize_error


def test_apify_memory_limit_message():
    i18n.set_language("uk")
    raw = (
        "Apify HTTP 402: By launching this job you will exceed the memory "
        "limit of 16384MB for all your Actor runs"
    )
    msg = humanize_error(raw, area="translation")
    assert "Apify" in msg
    assert "RAM" in msg or "пам" in msg.lower()
    assert "402" not in msg


def test_piper_not_configured():
    i18n.set_language("en")
    msg = humanize_error("Piper not configured", area="tts")
    assert "Piper" in msg
    assert "Settings" in msg


def test_all_translation_providers_failed():
    i18n.set_language("en")
    msg = humanize_error("All translation providers failed", area="translation")
    assert "translation" in msg.lower() or "Translation" in msg


def test_network_timeout():
    i18n.set_language("en")
    msg = humanize_error("HTTPSConnectionPool: Read timed out", area="tts")
    assert "Network" in msg or "network" in msg.lower()
