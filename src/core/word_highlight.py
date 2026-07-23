"""Word span helpers for karaoke-style reading highlight."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

HIGHLIGHT_STYLE_GRADIENT = "gradient"
HIGHLIGHT_STYLE_WAVE = "wave"
HIGHLIGHT_STYLE_KARAOKE = "karaoke"
HIGHLIGHT_STYLE_LIQUID = "liquid"
HIGHLIGHT_STYLE_MARKER = "marker"
HIGHLIGHT_STYLE_AURORA = "aurora"
# Legacy saved values → real styles
HIGHLIGHT_STYLE_SMOOTH = "smooth"
HIGHLIGHT_STYLE_STEP = "step"
HIGHLIGHT_STYLE_FLOW = "flow"
HIGHLIGHT_STYLE_GLOW = "glow"
HIGHLIGHT_STYLE_WAVE_MASK = "wave_mask"
HIGHLIGHT_STYLE_BRUSH = "brush"
HIGHLIGHT_STYLE_SHIMMER = "shimmer"
HIGHLIGHT_STYLE_MORPH = "morph"

HIGHLIGHT_STYLES = (
    HIGHLIGHT_STYLE_GRADIENT,
    HIGHLIGHT_STYLE_KARAOKE,
    HIGHLIGHT_STYLE_LIQUID,
    HIGHLIGHT_STYLE_MARKER,
    HIGHLIGHT_STYLE_AURORA,
)

OVERLAY_STYLES = frozenset(
    {
        HIGHLIGHT_STYLE_GRADIENT,
        HIGHLIGHT_STYLE_LIQUID,
        HIGHLIGHT_STYLE_AURORA,
    }
)

_STYLE_ALIASES = {
    HIGHLIGHT_STYLE_WAVE: HIGHLIGHT_STYLE_GRADIENT,
    HIGHLIGHT_STYLE_FLOW: HIGHLIGHT_STYLE_GRADIENT,
    HIGHLIGHT_STYLE_GLOW: HIGHLIGHT_STYLE_GRADIENT,
    HIGHLIGHT_STYLE_SHIMMER: HIGHLIGHT_STYLE_GRADIENT,
    HIGHLIGHT_STYLE_WAVE_MASK: HIGHLIGHT_STYLE_LIQUID,
    HIGHLIGHT_STYLE_BRUSH: HIGHLIGHT_STYLE_MARKER,
    HIGHLIGHT_STYLE_SMOOTH: HIGHLIGHT_STYLE_KARAOKE,
    HIGHLIGHT_STYLE_STEP: HIGHLIGHT_STYLE_KARAOKE,
    HIGHLIGHT_STYLE_MORPH: HIGHLIGHT_STYLE_KARAOKE,
}

EXACT_SYNC_OFFSET_MS = 45
ESTIMATED_SYNC_OFFSET_MS = 200
FALLBACK_SYNC_OFFSET_MS = 140

# Extra lead for offline engines (highlight tends to lag QMediaPlayer position).
ENGINE_SYNC_OFFSET_MS: dict[str, int] = {
    "piper": 320,
    "kokoro": 200,
    "system": 220,
    "xtts": 260,
    "styletts2": 260,
}

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?…])\s+|\n+")


@dataclass(frozen=True)
class PlaybackProgress:
    word_index: int
    blend: float  # 0..1 progress within the current word


@dataclass(frozen=True)
class WordTimingsBundle:
    timings: list[tuple[int, int]]
    estimated: bool


def word_spans(text: str) -> list[tuple[int, int]]:
    """Return (start, end) character spans for each non-whitespace token."""
    return [(match.start(), match.end()) for match in re.finditer(r"\S+", text)]


def split_sentences(text: str) -> list[str]:
    text = text.strip()
    if not text:
        return []
    parts = [part.strip() for part in _SENTENCE_SPLIT.split(text) if part.strip()]
    return parts or [text]


def derive_word_timings_from_sentences(
    sentences: list[tuple[int, int, str]],
) -> list[tuple[int, int]]:
    """Build word timings from Edge TTS SentenceBoundary events."""
    timings: list[tuple[int, int]] = []
    for start_ms, end_ms, sentence in sentences:
        words = re.findall(r"\S+", sentence)
        if not words:
            continue
        span = max(1, end_ms - start_ms)
        weights = [max(1, len(word)) for word in words]
        total = sum(weights)
        cursor = float(start_ms)
        for weight in weights:
            duration = span * (weight / total)
            word_start = int(cursor)
            word_end = int(cursor + duration)
            timings.append((word_start, max(word_start + 1, word_end)))
            cursor += duration
    return timings


def _distribute_weighted_timings(
    units: list[str], duration_ms: int
) -> list[tuple[int, int]]:
    if duration_ms <= 0 or not units:
        return []
    weights = [max(1, len(unit)) for unit in units]
    total = sum(weights)
    usable_ms = duration_ms * 0.98
    cursor = 0.0
    timings: list[tuple[int, int]] = []
    for weight in weights:
        unit_ms = usable_ms * (weight / total)
        start = int(cursor)
        end = int(cursor + unit_ms)
        timings.append((start, max(start + 1, end)))
        cursor += unit_ms
    if timings:
        last_start, _ = timings[-1]
        timings[-1] = (last_start, duration_ms)
    return timings


def estimate_word_timings_from_text(
    text: str, duration_ms: int
) -> list[tuple[int, int]]:
    """Estimate per-word timings from total duration (offline TTS / Piper / Kokoro)."""
    if duration_ms <= 0:
        return []
    sentences = split_sentences(text)
    if len(sentences) > 1:
        sentence_weights = [max(1, len(sentence)) for sentence in sentences]
        total_weight = sum(sentence_weights)
        usable_ms = duration_ms * 0.98
        cursor = 0.0
        timings: list[tuple[int, int]] = []
        for sentence, weight in zip(sentences, sentence_weights):
            sentence_ms = usable_ms * (weight / total_weight)
            chunk = _distribute_weighted_timings(
                re.findall(r"\S+", sentence),
                max(1, int(sentence_ms)),
            )
            if not chunk:
                continue
            shift = int(cursor)
            for start, end in chunk:
                timings.append((start + shift, end + shift))
            cursor += sentence_ms
        if timings:
            last_start, _ = timings[-1]
            timings[-1] = (last_start, duration_ms)
        return timings

    words = re.findall(r"\S+", text)
    return _distribute_weighted_timings(words, duration_ms)


def highlight_sync_offset_ms(
    *,
    estimated: bool,
    playback_rate: float = 1.0,
    engine: str | None = None,
) -> int:
    """Positive offset advances highlight to compensate UI/audio lag (milliseconds)."""
    if estimated:
        base = ENGINE_SYNC_OFFSET_MS.get(
            (engine or "").strip().lower(),
            ESTIMATED_SYNC_OFFSET_MS,
        )
    else:
        base = EXACT_SYNC_OFFSET_MS
    rate = max(1.0, min(2.0, float(playback_rate)))
    rate_bonus = int((rate - 1.0) * 90) if rate >= 1.0 else 0
    return max(0, base + rate_bonus)


def should_normalize_timings(
    timings: list[tuple[int, int]],
    duration_ms: int,
    *,
    estimated: bool = True,
) -> bool:
    """Avoid scaling timings while the player still reports a partial duration."""
    if not timings or duration_ms <= 0:
        return False
    last_end = timings[-1][1]
    if last_end <= 0:
        return False
    if abs(last_end - duration_ms) < 80:
        return False
    if estimated and duration_ms < last_end * 0.85:
        return False
    return True


def normalize_timings_to_duration(
    timings: list[tuple[int, int]],
    duration_ms: int,
    *,
    estimated: bool = True,
) -> list[tuple[int, int]]:
    """Align timings to the media player's reported duration."""
    if not timings or duration_ms <= 0:
        return timings
    if not should_normalize_timings(timings, duration_ms, estimated=estimated):
        return timings
    last_end = timings[-1][1]
    if not estimated:
        # Exact cloud timings: adjust tail only to avoid mid-block drift.
        adjusted = list(timings)
        last_start, _ = adjusted[-1]
        adjusted[-1] = (last_start, max(last_start + 1, duration_ms))
        return adjusted
    scale = duration_ms / last_end
    return [
        (int(start * scale), int(end * scale))
        for start, end in timings
    ]


def map_timing_index(timing_index: int, timing_count: int, span_count: int) -> int:
    """Align TTS boundary index to text token index when counts differ."""
    if span_count <= 0:
        return -1
    if timing_index < 0:
        return -1
    if timing_count <= 0:
        return min(span_count - 1, timing_index)
    if timing_count == span_count:
        return min(span_count - 1, timing_index)
    scaled = int(timing_index * span_count / timing_count)
    return min(span_count - 1, max(0, scaled))


def _float_index_from_timings(
    timings: list[tuple[int, int]],
    position_ms: int,
    span_count: int,
    sync_offset_ms: int,
) -> float:
    adjusted = max(0, position_ms + sync_offset_ms)
    timing_count = len(timings)
    if timing_count <= 0 or span_count <= 0:
        return 0.0
    if timing_count == 1:
        start, end = timings[0]
        local = (adjusted - start) / max(1, end - start)
        local = min(1.0, max(0.0, local))
        return local * max(0, span_count - 1)

    for index, (start, end) in enumerate(timings):
        if adjusted < end or index == timing_count - 1:
            local = (adjusted - start) / max(1, end - start)
            local = min(1.0, max(0.0, local))
            timing_float = index + local
            return timing_float * (span_count - 1) / (timing_count - 1)
    return float(span_count - 1)


def _float_index_from_ratio(
    position_ms: int,
    duration_ms: int,
    span_count: int,
    sync_offset_ms: int,
) -> float:
    """Drift-free mapping for old cached audio without boundary sidecars."""
    if span_count <= 1 or duration_ms <= 0:
        return 0.0
    adjusted = max(0, position_ms + sync_offset_ms)
    ratio = min(1.0, adjusted / duration_ms)
    return ratio * (span_count - 1)


def playback_progress(
    *,
    position_ms: int,
    duration_ms: int,
    span_count: int,
    timings: list[tuple[int, int]] | None = None,
    estimated: bool = False,
    playback_rate: float = 1.0,
    sync_offset_ms: int | None = None,
    engine: str | None = None,
) -> PlaybackProgress:
    """Continuous word position for smooth highlight (index + within-word blend)."""
    if span_count <= 0 or duration_ms <= 0:
        return PlaybackProgress(-1, 0.0)

    offset = (
        sync_offset_ms
        if sync_offset_ms is not None
        else highlight_sync_offset_ms(
            estimated=estimated,
            playback_rate=playback_rate,
            engine=engine,
        )
    )
    if timings:
        float_index = _float_index_from_timings(
            timings, position_ms, span_count, offset
        )
    else:
        float_index = _float_index_from_ratio(
            position_ms, duration_ms, span_count, offset
        )

    float_index = min(float(span_count - 1), max(0.0, float_index))
    word_index = int(float_index)
    blend = float_index - word_index
    if word_index >= span_count - 1:
        return PlaybackProgress(span_count - 1, min(1.0, blend))
    return PlaybackProgress(word_index, blend)


def normalize_highlight_style(style: str) -> str:
    value = (style or HIGHLIGHT_STYLE_GRADIENT).strip().lower()
    value = _STYLE_ALIASES.get(value, value)
    return value if value in HIGHLIGHT_STYLES else HIGHLIGHT_STYLE_GRADIENT


def uses_painter_overlay(style: str) -> bool:
    return normalize_highlight_style(style) in OVERLAY_STYLES


def parse_hex_color(value: str, fallback: str = "#ffe08a") -> tuple[int, int, int]:
    raw = (value or fallback).strip()
    if not raw.startswith("#"):
        raw = f"#{raw}"
    if len(raw) == 4:
        raw = "#" + "".join(ch * 2 for ch in raw[1:])
    try:
        return (
            int(raw[1:3], 16),
            int(raw[3:5], 16),
            int(raw[5:7], 16),
        )
    except ValueError:
        return parse_hex_color(fallback, "#ffe08a")


@dataclass(frozen=True)
class HighlightPalettePreset:
    id: str
    primary: str
    secondary: str
    accent: str
    text: str


HIGHLIGHT_PALETTE_CUSTOM = "custom"

HIGHLIGHT_PALETTE_PRESETS: tuple[HighlightPalettePreset, ...] = (
    HighlightPalettePreset(
        "warm",
        "#ffe08a",
        "#8ec5ff",
        "#c4a8ff",
        "#1a1a1a",
    ),
    HighlightPalettePreset(
        "soft_green",
        "#c8e6c9",
        "#81c784",
        "#a5d6a7",
        "#1b2e1c",
    ),
    HighlightPalettePreset(
        "sepia",
        "#e8dcc8",
        "#d4c4a8",
        "#c9b896",
        "#3d3428",
    ),
    HighlightPalettePreset(
        "sky",
        "#bbdefb",
        "#90caf9",
        "#b3e5fc",
        "#0d2137",
    ),
    HighlightPalettePreset(
        "lavender",
        "#e1bee7",
        "#ce93d8",
        "#b39ddb",
        "#2a1f33",
    ),
    HighlightPalettePreset(
        "night",
        "#6a7a38",
        "#4a7a9a",
        "#7a6a9a",
        "#f5f5f5",
    ),
)


def palette_preset_by_id(palette_id: str) -> HighlightPalettePreset | None:
    for preset in HIGHLIGHT_PALETTE_PRESETS:
        if preset.id == palette_id:
            return preset
    return None


def _normalize_hex(value: str) -> str:
    red, green, blue = parse_hex_color(value)
    return f"#{red:02x}{green:02x}{blue:02x}"


def detect_palette_preset(settings: dict[str, str]) -> str:
    current = (
        _normalize_hex(settings.get("word_highlight_color", "#ffe08a")),
        _normalize_hex(settings.get("word_highlight_color_2", "#8ec5ff")),
        _normalize_hex(settings.get("word_highlight_color_3", "#c4a8ff")),
        _normalize_hex(settings.get("word_highlight_text_color", "#1a1a1a")),
    )
    for preset in HIGHLIGHT_PALETTE_PRESETS:
        if current == (
            _normalize_hex(preset.primary),
            _normalize_hex(preset.secondary),
            _normalize_hex(preset.accent),
            _normalize_hex(preset.text),
        ):
            return preset.id
    return HIGHLIGHT_PALETTE_CUSTOM


def palette_colors_as_settings(preset: HighlightPalettePreset) -> dict[str, str]:
    return {
        "word_highlight_color": preset.primary,
        "word_highlight_color_2": preset.secondary,
        "word_highlight_color_3": preset.accent,
        "word_highlight_text_color": preset.text,
    }


@dataclass(frozen=True)
class HighlightColors:
    primary: tuple[int, int, int]
    secondary: tuple[int, int, int]
    accent: tuple[int, int, int]
    text: tuple[int, int, int]
    text_soft: tuple[int, int, int]


@dataclass(frozen=True)
class HighlightSegment:
    start: int
    end: int
    bg: tuple[int, int, int, int] | None = None
    fg: tuple[int, int, int, int] | None = None
    bold: bool = False
    weight: int | None = None
    underline: bool = False
    underline_rgba: tuple[int, int, int, int] | None = None


def highlight_colors_from_settings(settings: dict[str, str]) -> HighlightColors:
    primary = parse_hex_color(settings.get("word_highlight_color", "#ffe08a"))
    secondary = parse_hex_color(settings.get("word_highlight_color_2", "#8ec5ff"))
    accent = parse_hex_color(settings.get("word_highlight_color_3", "#c4a8ff"))
    text = parse_hex_color(settings.get("word_highlight_text_color", "#1a1a1a"))
    soft = tuple(int(channel * 0.72 + 68 * 0.28) for channel in text)
    return HighlightColors(
        primary=primary,
        secondary=secondary,
        accent=accent,
        text=text,
        text_soft=soft,
    )


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def _lerp_color(
    left: tuple[int, int, int], right: tuple[int, int, int], t: float
) -> tuple[int, int, int]:
    return (
        int(_lerp(left[0], right[0], t)),
        int(_lerp(left[1], right[1], t)),
        int(_lerp(left[2], right[2], t)),
    )


def _rgba(color: tuple[int, int, int], alpha: float) -> tuple[int, int, int, int]:
    return (color[0], color[1], color[2], int(min(255, max(0, 255 * alpha))))


def _char_frontier(spans: list[tuple[int, int]], float_index: float) -> float:
    if not spans:
        return 0.0
    float_index = min(float(len(spans) - 1), max(0.0, float_index))
    index = int(float_index)
    blend = float_index - index
    start, end = spans[index]
    return _lerp(float(start), float(end), blend)


def _aurora_color(phase: float, colors: HighlightColors) -> tuple[int, int, int]:
    phase = phase % 1.0
    if phase < 0.33:
        return _lerp_color(colors.primary, colors.secondary, phase / 0.33)
    if phase < 0.66:
        return _lerp_color(colors.secondary, colors.accent, (phase - 0.33) / 0.33)
    return _lerp_color(colors.accent, colors.primary, (phase - 0.66) / 0.34)


def _build_karaoke_segments(
    spans: list[tuple[int, int]],
    float_index: float,
    colors: HighlightColors,
) -> list[HighlightSegment]:
    if not spans:
        return []
    word_index = int(min(len(spans) - 1, max(0.0, float_index)))
    start, end = spans[word_index]
    return [
        HighlightSegment(
            start,
            end,
            bg=_rgba(colors.primary, 0.88),
            fg=_rgba(colors.text, 1.0),
            bold=True,
        )
    ]


def _build_marker_segments(
    spans: list[tuple[int, int]],
    float_index: float,
    colors: HighlightColors,
) -> list[HighlightSegment]:
    if not spans:
        return []
    word_index = int(min(len(spans) - 1, max(0.0, float_index)))
    segments: list[HighlightSegment] = []
    mark_color = _rgba(colors.primary, 0.95)
    for idx, (start, end) in enumerate(spans):
        if idx > word_index:
            break
        segments.append(
            HighlightSegment(
                start,
                end,
                fg=_rgba(colors.text if idx == word_index else colors.text_soft, 1.0),
                underline=True,
                underline_rgba=mark_color,
                bold=idx == word_index,
            )
        )
    return segments


def build_text_highlight_segments(
    style: str,
    spans: list[tuple[int, int]],
    float_index: float,
    colors: HighlightColors,
) -> tuple[float, list[HighlightSegment]]:
    normalized = normalize_highlight_style(style)
    center = flow_highlight_center(spans, float_index) if spans else 0.0
    if normalized == HIGHLIGHT_STYLE_KARAOKE:
        return center, _build_karaoke_segments(spans, float_index, colors)
    if normalized == HIGHLIGHT_STYLE_MARKER:
        return center, _build_marker_segments(spans, float_index, colors)
    return center, []


def build_highlight_segments(
    style: str,
    spans: list[tuple[int, int]],
    float_index: float,
    text_length: int,
    colors: HighlightColors,
) -> tuple[float, list[HighlightSegment]]:
    """Text-format segments (karaoke, marker). Overlay styles return empty."""
    if uses_painter_overlay(style):
        center = flow_highlight_center(spans, float_index) if spans else 0.0
        return center, []
    return build_text_highlight_segments(style, spans, float_index, colors)


def flow_highlight_center(spans: list[tuple[int, int]], float_index: float) -> float:
    """Character position at the center of the flowing highlight zone."""
    if not spans:
        return 0.0
    float_index = min(float(len(spans) - 1), max(0.0, float_index))
    index = int(float_index)
    blend = float_index - index

    def midpoint(word_index: int) -> float:
        start, end = spans[word_index]
        return (start + end) / 2.0

    center = midpoint(index)
    if index + 1 < len(spans) and blend > 0:
        center = midpoint(index) * (1.0 - blend) + midpoint(index + 1) * blend
    return center


@dataclass(frozen=True)
class FlowWaveSlice:
    start: int
    end: int
    intensity: float  # 0..1, smooth bell curve


def flow_wave_intensity(normalized_distance: float) -> float:
    """Raised cosine bell — soft peak, invisible edges."""
    distance = min(1.0, max(0.0, normalized_distance))
    cosine = (math.cos(distance * math.pi) + 1.0) * 0.5
    return cosine**1.25


def subtle_gradient_intensity(normalized_distance: float) -> float:
    """Very soft bell for low-contrast gradient highlight."""
    distance = min(1.0, max(0.0, normalized_distance))
    cosine = (math.cos(distance * math.pi) + 1.0) * 0.5
    return cosine**2.2


def build_flow_wave_slices(
    spans: list[tuple[int, int]],
    float_index: float,
    text_length: int,
    *,
    window_words: float = 3.6,
    slice_count: int = 48,
) -> tuple[float, list[FlowWaveSlice]]:
    """Build a narrow, smooth wave as many thin slices with bell-curve intensity."""
    if not spans or text_length <= 0:
        return 0.0, []

    center = flow_highlight_center(spans, float_index)
    avg_width = sum(end - start for start, end in spans) / len(spans)
    half_width = max(16.0, avg_width * window_words / 2.0)
    zone_start = max(0, int(center - half_width))
    zone_end = min(text_length, int(center + half_width))
    span_len = max(1, zone_end - zone_start)

    slices: list[FlowWaveSlice] = []
    for index in range(slice_count):
        fraction_start = index / slice_count
        fraction_end = (index + 1) / slice_count
        seg_start = zone_start + int(span_len * fraction_start)
        seg_end = zone_start + int(span_len * fraction_end)
        if seg_end <= seg_start:
            seg_end = min(text_length, seg_start + 1)
        seg_end = min(text_length, seg_end)
        seg_mid = (seg_start + seg_end) / 2.0
        distance = abs(seg_mid - center) / half_width
        intensity = flow_wave_intensity(distance)
        if intensity >= 0.03:
            slices.append(FlowWaveSlice(seg_start, seg_end, intensity))

    slices.sort(key=lambda item: item.intensity)
    return center, slices


def flow_highlight_window(
    spans: list[tuple[int, int]],
    float_index: float,
    text_length: int,
    *,
    window_words: float = 3.6,
) -> tuple[int, int]:
    """Character range enclosing the flow wave (for tests and scroll bounds)."""
    if not spans or text_length <= 0:
        return 0, 0
    center = flow_highlight_center(spans, float_index)
    avg_width = sum(end - start for start, end in spans) / len(spans)
    half_width = max(16.0, avg_width * window_words / 2.0)
    start = max(0, int(center - half_width))
    end = min(text_length, int(center + half_width))
    if end <= start:
        end = min(text_length, start + 1)
    return start, end


# Backward-compatible helpers used in tests.
def word_index_at_time(
    timings: list[tuple[int, int]],
    position_ms: int,
    lag_ms: int = 0,
) -> int:
    if not timings:
        return -1
    sync_offset_ms = -lag_ms
    progress = playback_progress(
        position_ms=position_ms,
        duration_ms=timings[-1][1],
        span_count=len(timings),
        timings=timings,
        estimated=False,
        sync_offset_ms=sync_offset_ms,
    )
    return progress.word_index


def word_index_at_duration(
    duration_ms: int,
    position_ms: int,
    word_count: int,
    lag_ms: int = 0,
) -> int:
    if word_count <= 0 or duration_ms <= 0:
        return -1
    sync_offset_ms = (
        -lag_ms if lag_ms else FALLBACK_SYNC_OFFSET_MS
    )
    progress = playback_progress(
        position_ms=position_ms,
        duration_ms=duration_ms,
        span_count=word_count,
        timings=None,
        estimated=True,
        sync_offset_ms=sync_offset_ms,
    )
    return progress.word_index


def word_index_for_playback(
    *,
    position_ms: int,
    duration_ms: int,
    span_count: int,
    timings: list[tuple[int, int]] | None = None,
    estimated: bool = False,
    playback_rate: float = 1.0,
) -> int:
    return playback_progress(
        position_ms=position_ms,
        duration_ms=duration_ms,
        span_count=span_count,
        timings=timings,
        estimated=estimated,
        playback_rate=playback_rate,
    ).word_index


def expected_word_index_at_ratio(
    span_count: int,
    position_ms: int,
    duration_ms: int,
) -> int:
    """Reference index for linear speech (used in sync tests)."""
    if span_count <= 1 or duration_ms <= 0:
        return 0
    ratio = min(1.0, max(0.0, position_ms / duration_ms))
    return min(span_count - 1, int(ratio * (span_count - 1)))


def sync_error_words(
    *,
    position_ms: int,
    duration_ms: int,
    span_count: int,
    timings: list[tuple[int, int]] | None = None,
    estimated: bool = False,
    playback_rate: float = 1.0,
) -> int:
    """Absolute word-index error vs linear reference (lower is better)."""
    expected = expected_word_index_at_ratio(span_count, position_ms, duration_ms)
    actual = playback_progress(
        position_ms=position_ms,
        duration_ms=duration_ms,
        span_count=span_count,
        timings=timings,
        estimated=estimated,
        playback_rate=playback_rate,
    ).word_index
    if actual < 0:
        return span_count
    return abs(actual - expected)
