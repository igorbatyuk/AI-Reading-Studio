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


def normalize_ui_speech_rate(speed: float) -> float:
    return max(MIN_UI_SPEECH_RATE, min(MAX_UI_SPEECH_RATE, float(speed)))


def engine_speech_rate(ui_speed: float) -> float:
    """Map UI speech rate to engine parameter (stronger slow-down below 1x)."""
    ui = normalize_ui_speech_rate(ui_speed)
    if ui >= 1.0:
        return min(MAX_ENGINE_SPEECH_RATE, ui)
    # Power curve: 0.35 UI -> ~0.26 engine, 0.25 UI -> ~0.20 engine
    effective = ui**1.55
    return max(MIN_ENGINE_SPEECH_RATE, min(1.0, effective))


def edge_rate_string(ui_speed: float) -> str:
    ui = normalize_ui_speech_rate(ui_speed)
    if ui in UI_SPEECH_RATES:
        return UI_SPEECH_RATES[ui]
    if ui <= 1.0:
        pct = int(round((ui - 1.0) * 100))
        return f"{pct:+d}%"
    pct = int(round((ui - 1.0) * 100))
    return f"+{pct}%"


def piper_length_scale(ui_speed: float) -> float:
    rate = engine_speech_rate(ui_speed)
    return max(0.45, min(4.5, 1.0 / max(rate, 0.1)))


def kokoro_speech_rate(ui_speed: float) -> float:
    """Kokoro ONNX accepts 0.5–2.0 only."""
    ui = normalize_ui_speech_rate(ui_speed)
    return max(0.5, min(2.0, ui))


def clamp_playback_rate(rate: float) -> float:
    """Playback during reading — accelerate only (1x..2x)."""
    rate = float(rate)
    if rate < 1.0:
        return 1.0
    return min(2.0, rate)


def murf_speech_rate(ui_speed: float) -> int:
    """Map UI speech rate to Murf `rate` parameter (-50..50)."""
    ui = normalize_ui_speech_rate(ui_speed)
    if ui <= 1.0:
        return max(-50, min(0, int(round((ui - 1.0) / 0.75 * 50))))
    return max(0, min(50, int(round((ui - 1.0) * 50))))


def cartesia_generation_speed(ui_speed: float) -> float:
    """Map UI speech rate to Cartesia generation_config.speed (0.6–1.5)."""
    ui = normalize_ui_speech_rate(ui_speed)
    if ui <= 1.0:
        # 0.25 UI -> 0.6, 1.0 UI -> 1.0
        t = (ui - MIN_UI_SPEECH_RATE) / (1.0 - MIN_UI_SPEECH_RATE)
        return max(0.6, min(1.0, 0.6 + t * 0.4))
    # 1.0 UI -> 1.0, 2.0 UI -> 1.5
    t = (ui - 1.0) / (MAX_UI_SPEECH_RATE - 1.0)
    return max(1.0, min(1.5, 1.0 + t * 0.5))
