"""Tests for word highlight helpers."""

from src.core.word_highlight import (
    HighlightColors,
    PlaybackProgress,
    build_flow_wave_slices,
    build_highlight_segments,
    derive_word_timings_from_sentences,
    flow_highlight_window,
    flow_wave_intensity,
    normalize_highlight_style,
    normalize_timings_to_duration,
    parse_hex_color,
    playback_progress,
    word_index_at_duration,
    word_index_at_time,
    word_index_for_playback,
    word_spans,
)


def test_word_spans_finds_tokens():
    text = "Hello, world!"
    spans = word_spans(text)
    assert spans == [(0, 6), (7, 13)]


def test_derive_word_timings_from_sentences():
    sentences = [(0, 1000, "One two"), (1000, 2500, "Three four five")]
    timings = derive_word_timings_from_sentences(sentences)
    assert len(timings) == 5
    assert timings[0][0] == 0
    assert timings[-1][1] == 2500


def test_normalize_timings_to_duration():
    timings = [(0, 500), (500, 1000)]
    scaled = normalize_timings_to_duration(timings, 2000)
    assert scaled[-1][1] == 2000


def test_playback_progress_exact_is_fractional():
    timings = [(0, 400), (400, 900), (900, 1200)]
    first = playback_progress(
        position_ms=650,
        duration_ms=1200,
        span_count=3,
        timings=timings,
        estimated=False,
    )
    assert isinstance(first, PlaybackProgress)
    assert first.word_index in (1, 2)
    assert 0.0 <= first.blend <= 1.0


def test_playback_progress_uses_synthesized_timings():
    from src.core.word_highlight import estimate_word_timings_from_text

    text = " ".join(f"word{i}" for i in range(10))
    timings = estimate_word_timings_from_text(text, 3000)
    early = playback_progress(
        position_ms=600,
        duration_ms=3000,
        span_count=10,
        timings=timings,
        estimated=True,
    )
    late = playback_progress(
        position_ms=1800,
        duration_ms=3000,
        span_count=10,
        timings=timings,
        estimated=True,
    )
    assert late.word_index >= early.word_index


def test_word_index_at_time_start_based():
    timings = [(0, 200), (200, 500), (500, 800)]
    assert word_index_at_time(timings, 250, lag_ms=0) == 1


def test_word_index_at_duration_uses_progress():
    index = word_index_at_duration(3000, 1500, 10, lag_ms=0)
    assert 3 <= index <= 5


def test_word_index_for_playback_wrapper():
    timings = [(0, 300), (300, 700), (700, 1000)]
    assert word_index_for_playback(
        position_ms=450,
        duration_ms=1000,
        span_count=3,
        timings=timings,
        estimated=False,
    ) in (1, 2)


def test_normalize_highlight_style():
    assert normalize_highlight_style("gradient") == "gradient"
    assert normalize_highlight_style("wave") == "gradient"
    assert normalize_highlight_style("flow") == "gradient"
    assert normalize_highlight_style("smooth") == "karaoke"
    assert normalize_highlight_style("brush") == "marker"
    assert normalize_highlight_style("glow") == "gradient"
    assert normalize_highlight_style("unknown") == "gradient"


def test_uses_painter_overlay():
    from src.core.word_highlight import uses_painter_overlay

    assert uses_painter_overlay("gradient") is True
    assert uses_painter_overlay("wave") is True
    assert uses_painter_overlay("liquid") is True
    assert uses_painter_overlay("aurora") is True
    assert uses_painter_overlay("karaoke") is False
    assert uses_painter_overlay("marker") is False


def test_subtle_gradient_intensity():
    from src.core.word_highlight import subtle_gradient_intensity

    assert subtle_gradient_intensity(0.0) == 1.0
    assert subtle_gradient_intensity(1.0) == 0.0
    assert subtle_gradient_intensity(0.5) < flow_wave_intensity(0.5)


def test_detect_palette_preset():
    from src.core.word_highlight import (
        HIGHLIGHT_PALETTE_CUSTOM,
        detect_palette_preset,
        palette_colors_as_settings,
        palette_preset_by_id,
    )

    warm = palette_preset_by_id("warm")
    assert warm is not None
    assert detect_palette_preset(palette_colors_as_settings(warm)) == "warm"
    custom_settings = palette_colors_as_settings(warm)
    custom_settings["word_highlight_color"] = "#123456"
    assert detect_palette_preset(custom_settings) == HIGHLIGHT_PALETTE_CUSTOM


def test_parse_hex_color():
    assert parse_hex_color("#ff0000") == (255, 0, 0)
    assert parse_hex_color("ffe08a") == (255, 224, 138)
    assert parse_hex_color("#ff0000") == (255, 0, 0)
    assert parse_hex_color("ffe08a") == (255, 224, 138)


def test_build_highlight_segments_for_styles():
    text = " ".join(f"word{i}" for i in range(12))
    spans = word_spans(text)
    colors = HighlightColors(
        primary=(255, 224, 138),
        secondary=(142, 197, 255),
        accent=(196, 168, 255),
        text=(26, 26, 26),
        text_soft=(68, 68, 68),
    )
    for style in ("gradient", "liquid", "aurora"):
        center, segments = build_highlight_segments(
            style, spans, 4.5, len(text), colors
        )
        assert center >= 0
        assert segments == []

    center, karaoke = build_highlight_segments(
        "karaoke", spans, 4.5, len(text), colors
    )
    assert center >= 0
    assert len(karaoke) == 1

    center, marker = build_highlight_segments(
        "marker", spans, 4.5, len(text), colors
    )
    assert center >= 0
    assert len(marker) == 5
    assert all(segment.underline for segment in marker)


def test_flow_highlight_window_moves():
    text = " ".join(f"word{i}" for i in range(20))
    spans = word_spans(text)
    start_a, end_a = flow_highlight_window(spans, 2.0, len(text))
    start_b, end_b = flow_highlight_window(spans, 14.0, len(text))
    assert start_b > start_a
    assert (end_a - start_a) < len(text) * 0.5


def test_flow_wave_intensity_is_smooth_bell():
    assert flow_wave_intensity(0.0) == 1.0
    assert flow_wave_intensity(1.0) == 0.0
    assert flow_wave_intensity(0.5) > flow_wave_intensity(0.8)


def test_build_flow_wave_slices_many_layers():
    text = " ".join(f"word{i}" for i in range(30))
    spans = word_spans(text)
    center, slices = build_flow_wave_slices(spans, 8.5, len(text))
    assert center > 0
    assert len(slices) >= 20
    peak = max(s.intensity for s in slices)
    assert peak >= 0.95
