"""Secure storage for API keys via OS keyring (fallback: settings DB)."""

from __future__ import annotations

SERVICE_NAME = "ai_reading_studio"
OPENAI_API_KEY_ACCOUNT = "openai_api_key"
APIFY_API_TOKEN_ACCOUNT = "apify_api_token"
GOOGLE_API_KEY_ACCOUNT = "google_api_key"
DEEPL_API_KEY_ACCOUNT = "deepl_api_key"
AZURE_SPEECH_KEY_ACCOUNT = "azure_speech_key"
GOOGLE_TTS_API_KEY_ACCOUNT = "google_tts_api_key"
ELEVENLABS_API_KEY_ACCOUNT = "elevenlabs_api_key"
CARTESIA_API_KEY_ACCOUNT = "cartesia_api_key"
MURF_API_KEY_ACCOUNT = "murf_api_key"

# Backward-compatible alias
API_KEY_ACCOUNT = OPENAI_API_KEY_ACCOUNT


def get_openai_api_key(db_fallback: str = "") -> str:
    return _get_key(OPENAI_API_KEY_ACCOUNT, db_fallback)


def get_apify_api_token(db_fallback: str = "") -> str:
    token = _get_key(APIFY_API_TOKEN_ACCOUNT, "")
    if token:
        return token
    legacy = _get_key(GOOGLE_API_KEY_ACCOUNT, "")
    if legacy and legacy.startswith("apify_api_"):
        return legacy
    if db_fallback and db_fallback.startswith("apify_api_"):
        return db_fallback
    return db_fallback


def get_google_api_key(db_fallback: str = "") -> str:
    key = _get_key(GOOGLE_API_KEY_ACCOUNT, "")
    if key and not key.startswith("apify_api_"):
        return key
    if db_fallback and db_fallback.startswith("AIza"):
        return db_fallback
    return ""


def get_deepl_api_key(db_fallback: str = "") -> str:
    return _get_key(DEEPL_API_KEY_ACCOUNT, db_fallback)


def get_azure_speech_key(db_fallback: str = "") -> str:
    return _get_key(AZURE_SPEECH_KEY_ACCOUNT, db_fallback)


def get_google_tts_api_key(db_fallback: str = "") -> str:
    key = _get_key(GOOGLE_TTS_API_KEY_ACCOUNT, "")
    if key:
        return key
    return get_google_api_key(db_fallback)


def get_elevenlabs_api_key(db_fallback: str = "") -> str:
    return _get_key(ELEVENLABS_API_KEY_ACCOUNT, db_fallback)


def get_cartesia_api_key(db_fallback: str = "") -> str:
    return _get_key(CARTESIA_API_KEY_ACCOUNT, db_fallback)


def get_murf_api_key(db_fallback: str = "") -> str:
    return _get_key(MURF_API_KEY_ACCOUNT, db_fallback)


def get_api_key(db_fallback: str = "") -> str:
    return get_openai_api_key(db_fallback)


def _get_key(account: str, db_fallback: str = "") -> str:
    try:
        import keyring

        stored = keyring.get_password(SERVICE_NAME, account)
        if stored:
            return stored
    except Exception:
        pass
    return db_fallback


def set_openai_api_key(key: str, db: object | None = None) -> None:
    _set_key(OPENAI_API_KEY_ACCOUNT, key)
    if db is not None:
        db.set_setting("openai_api_key", "")


def set_apify_api_token(token: str, db: object | None = None) -> None:
    _set_key(APIFY_API_TOKEN_ACCOUNT, token)
    if db is not None:
        db.set_setting("apify_api_token", "")


def set_google_api_key(key: str, db: object | None = None) -> None:
    _set_key(GOOGLE_API_KEY_ACCOUNT, key)
    if db is not None:
        db.set_setting("google_api_key", "")


def set_deepl_api_key(key: str, db: object | None = None) -> None:
    _set_key(DEEPL_API_KEY_ACCOUNT, key)
    if db is not None:
        db.set_setting("deepl_api_key", "")


def set_azure_speech_key(key: str, db: object | None = None) -> None:
    _set_key(AZURE_SPEECH_KEY_ACCOUNT, key)
    if db is not None:
        db.set_setting("azure_speech_key", "")


def set_google_tts_api_key(key: str, db: object | None = None) -> None:
    _set_key(GOOGLE_TTS_API_KEY_ACCOUNT, key)
    if db is not None:
        db.set_setting("google_tts_api_key", "")


def set_elevenlabs_api_key(key: str, db: object | None = None) -> None:
    _set_key(ELEVENLABS_API_KEY_ACCOUNT, key)
    if db is not None:
        db.set_setting("elevenlabs_api_key", "")


def set_cartesia_api_key(key: str, db: object | None = None) -> None:
    _set_key(CARTESIA_API_KEY_ACCOUNT, key)
    if db is not None:
        db.set_setting("cartesia_api_key", "")


def set_murf_api_key(key: str, db: object | None = None) -> None:
    _set_key(MURF_API_KEY_ACCOUNT, key)
    if db is not None:
        db.set_setting("murf_api_key", "")


def set_api_key(key: str, db: object | None = None) -> None:
    set_openai_api_key(key, db)


def _set_key(account: str, key: str) -> None:
    cleaned = key.strip()
    try:
        import keyring

        if cleaned:
            keyring.set_password(SERVICE_NAME, account, cleaned)
        else:
            try:
                keyring.delete_password(SERVICE_NAME, account)
            except Exception:
                pass
    except Exception:
        pass
