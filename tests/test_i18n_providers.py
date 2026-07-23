"""Cartesia / Murf / Bergamot strings must be translated in de, fr, es, pl."""

from src.core.i18n import _STRINGS, set_language, tr

_PROVIDER_KEYS = [
    "settings.cartesia_api_key_hint",
    "settings.cartesia_tts_usage_hint",
    "settings.murf_api_key_hint",
    "settings.murf_tts_usage_hint",
    "settings.translation_block.hint.bergamot",
    "settings.api_info",
]

_LOCALIZED_MARKERS = {
    "de": ("registrierung", "credits", "schlüssel", "bergamot", "zeichen", "diese app"),
    "fr": ("inscription", "crédits", "clés", "bergamot", "caractères", "cette app"),
    "es": ("registro", "créditos", "claves", "bergamot", "caracteres", "esta app"),
    "pl": ("rejestracja", "kredyt", "klucz", "bergamot", "znak", "aplikacja"),
}


def test_cartesia_murf_hints_not_english_fallback():
    en = _STRINGS["en"]
    for lang, markers in _LOCALIZED_MARKERS.items():
        partial = _STRINGS[lang]
        for key in _PROVIDER_KEYS:
            assert key in partial, f"{lang} missing explicit key {key}"
            assert partial[key] != en[key], f"{lang}.{key} still English"
            blob = partial[key].lower()
            assert any(m.lower() in blob for m in markers), (
                f"{lang}.{key} does not look localized"
            )


def test_tr_returns_localized_provider_strings(qapp):
    set_language("de")
    assert "Registrierung" in tr("settings.cartesia_api_key_hint")
    set_language("pl")
    assert "kredyt" in tr("settings.cartesia_tts_usage_fmt", remaining=1, limit=20000, month="2026-07", used=0, percent=0).lower()
