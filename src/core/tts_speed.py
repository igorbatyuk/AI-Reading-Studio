"""Speech-rate mapping: UI settings -> TTS engine parameters."""

from __future__ import annotations

# UI combo values (Settings -> speech rate)
UI_SPEECH_RATES: dict[float, str] = {
    0.25: "-75%",
    0.3: "-70%",
    0.35: "-65%",
    0.4: "-60%",
    0.45: "-55%",
    0.5: "-50%",
    0.6: "-40%",
    0.7: "-30%",
    0.8: "-20%",
    0.9: "-10%",
    1.0: "+0%",
    1.25: "+25%",
    1.5: "+50%",
    1.75: "+75%",
    2.0: "+100%",
}

PLAYBACK_RATES = (1.0, 1.25, 1.5, 1.75, 2.0)

MIN_UI_SPEECH_RATE = 0.25
MAX_UI_SPEECH_RATE = 2.0
MIN_ENGINE_SPEECH_RATE = 0.2
MAX_ENGINE_SPEECH_RATE = 2.0

# Allowed Settings combo range per TTS engine (inclusive).
ENGINE_UI_SPEECH_RATE_LIMITS: dict[str, tuple[float, float]] = {
    "edge": (0.5, 2.0),
    "azure": (0.5, 2.0),
    "google": (0.25, 2.0),
    "elevenlabs": (0.25, 2.0),
    "cartesia": (0.5, 1.5),
    "murf": (0.25, 2.0),
    "kokoro": (0.5, 2.0),
    "piper": (0.25, 2.0),
    "xtts": (0.25, 2.0),
    "styletts2": (0.25, 2.0),
    "system": (0.25, 2.0),
}


def speech_rate_limits_for_engine(engine: str) -> tuple[float, float]:
    return ENGINE_UI_SPEECH_RATE_LIMITS.get(
        engine, (MIN_UI_SPEECH_RATE, MAX_UI_SPEECH_RATE)
    )


def speech_rate_limits_for_tts_context(
    tts_mode: str,
    offline_engine: str,
    online_engine: str = "edge",
) -> tuple[float, float]:
    """Return (min, max) UI speech rate for the active Settings TTS context."""
    if tts_mode == "online":
        return speech_rate_limits_for_engine(online_engine)
    if tts_mode == "offline":
        return speech_rate_limits_for_engine(offline_engine)
    on_min, on_max = speech_rate_limits_for_engine(online_engine)
    off_min, off_max = speech_rate_limits_for_engine(offline_engine)
    return max(on_min, off_min), min(on_max, off_max)


def allowed_ui_speech_rates(
    min_rate: float | None = None,
    max_rate: float | None = None,
) -> dict[float, str]:
    lo = MIN_UI_SPEECH_RATE if min_rate is None else float(min_rate)
    hi = MAX_UI_SPEECH_RATE if max_rate is None else float(max_rate)
    return {
        speed: label
        for speed, label in UI_SPEECH_RATES.items()
        if lo <= speed <= hi
    }


def clamp_ui_speech_rate_for_context(
    speed: float,
    tts_mode: str,
    offline_engine: str,
    online_engine: str = "edge",
) -> float:
    ui = normalize_speech_rate_to_combo(speed)
    min_rate, max_rate = speech_rate_limits_for_tts_context(
        tts_mode, offline_engine, online_engine
    )
    allowed = allowed_ui_speech_rates(min_rate, max_rate)
    if ui in allowed:
        return ui
    return min(allowed.keys(), key=lambda value: abs(value - ui))


def normalize_ui_speech_rate(speed: float) -> float:
    return max(MIN_UI_SPEECH_RATE, min(MAX_UI_SPEECH_RATE, float(speed)))


def normalize_speech_rate_to_combo(speed: float) -> float:
    """Snap UI speech rate to a Settings combo value."""
    ui = normalize_ui_speech_rate(speed)
    if ui in UI_SPEECH_RATES:
        return ui
    allowed = sorted(UI_SPEECH_RATES.keys())
    return min(allowed, key=lambda value: abs(value - ui))


def speed_cache_token(speed: float) -> str:
    """Stable token for audio cache keys."""
    return f"{normalize_speech_rate_to_combo(speed):g}"


def engine_speech_rate(ui_speed: float) -> float:
    """Map UI speech rate to engine parameter (stronger slow-down below 1x)."""
    ui = normalize_ui_speech_rate(ui_speed)
    if ui >= 1.0:
        return min(MAX_ENGINE_SPEECH_RATE, ui)
    # Power curve: 0.35 UI -> ~0.26 engine, 0.25 UI -> ~0.20 engine
    effective = ui**1.55
    return max(MIN_ENGINE_SPEECH_RATE, min(1.0, effective))


def edge_rate_string(ui_speed: float) -> str:
    """Edge/Azure prosody rate. Edge TTS clamps near -50% (0.5x); slower UI maps to -50%."""
    ui = normalize_speech_rate_to_combo(ui_speed)
    if ui >= 1.0:
        if ui in UI_SPEECH_RATES:
            return UI_SPEECH_RATES[ui]
        pct = int(round((ui - 1.0) * 100))
        return f"+{pct}%"
    if ui <= 0.5:
        return "-50%"
    if ui in UI_SPEECH_RATES:
        return UI_SPEECH_RATES[ui]
    pct = int(round((ui - 1.0) * 100))
    return f"{pct:+d}%"


def piper_length_scale(ui_speed: float) -> float:
    rate = engine_speech_rate(ui_speed)
    return max(0.45, min(4.5, 1.0 / max(rate, 0.1)))


def kokoro_speech_rate(ui_speed: float) -> float:
    """Kokoro ONNX accepts 0.5–2.0 only."""
    ui = normalize_speech_rate_to_combo(ui_speed)
    rate = engine_speech_rate(ui)
    return max(0.5, min(2.0, rate))


def clamp_playback_rate(rate: float) -> float:
    """Playback during reading — accelerate only (1x..2x)."""
    rate = float(rate)
    if rate < 1.0:
        return 1.0
    return min(2.0, rate)


def murf_speech_rate(ui_speed: float) -> int:
    """Map UI speech rate to Murf `rate` parameter (-50..50)."""
    ui = normalize_speech_rate_to_combo(ui_speed)
    if ui <= 1.0:
        # ui 0.25 -> -50, ui 1.0 -> 0 (linear)
        span = max(1.0 - MIN_UI_SPEECH_RATE, 0.01)
        return max(-50, min(0, int(round((ui - 1.0) / span * 50))))
    return max(0, min(50, int(round((ui - 1.0) * 50))))


def cartesia_generation_speed(ui_speed: float) -> float:
    """Map UI speech rate to Cartesia generation_config.speed (0.6–1.5)."""
    ui = normalize_speech_rate_to_combo(ui_speed)
    if ui >= 1.0:
        t = (ui - 1.0) / (MAX_UI_SPEECH_RATE - 1.0)
        return max(1.0, min(1.5, 1.0 + t * 0.5))
    # Cartesia API floor is 0.6x; map UI 0.25..1.0 -> 0.6..1.0 linearly.
    span = max(1.0 - MIN_UI_SPEECH_RATE, 0.01)
    t = (ui - MIN_UI_SPEECH_RATE) / span
    return max(0.6, min(1.0, 0.6 + t * 0.4))


def google_speaking_rate(ui_speed: float) -> float:
    """Map UI speech rate to Google Cloud speakingRate (0.25–4.0)."""
    ui = normalize_speech_rate_to_combo(ui_speed)
    return max(0.25, min(4.0, ui))


def elevenlabs_voice_speed(ui_speed: float) -> float:
    """Map UI speech rate to ElevenLabs voice_settings.speed (0.25–4.0)."""
    ui = normalize_speech_rate_to_combo(ui_speed)
    return max(0.25, min(4.0, ui))
