"""Sync quality tests for word highlight at various speeds and timing modes."""

import json

import pytest

from src.core.word_highlight import (
    ESTIMATED_SYNC_OFFSET_MS,
    EXACT_SYNC_OFFSET_MS,
    WordTimingsBundle,
    estimate_word_timings_from_text,
    highlight_sync_offset_ms,
    normalize_timings_to_duration,
    playback_progress,
    sync_error_words,
    word_spans,
)


def _sample_text(word_count: int = 24) -> str:
    return " ".join(f"word{i}" for i in range(word_count))


@pytest.mark.parametrize("duration_ms", [6000, 12000, 60000])
def test_estimated_timings_midpoint_within_two_words(duration_ms: int):
    text = _sample_text(24)
    spans = word_spans(text)
    timings = estimate_word_timings_from_text(text, duration_ms)
    assert len(timings) == len(spans)

    mid_ms = duration_ms // 2
    progress = playback_progress(
        position_ms=mid_ms,
        duration_ms=duration_ms,
        span_count=len(spans),
        timings=timings,
        estimated=True,
    )
    expected = (len(spans) - 1) // 2
    assert abs(progress.word_index - expected) <= 2


@pytest.mark.parametrize("playback_rate", [1.0, 1.25, 1.5, 2.0])
def test_sync_error_bounded_at_half_duration(playback_rate: float):
    text = _sample_text(30)
    duration_ms = 30000
    timings = estimate_word_timings_from_text(text, duration_ms)
    error = sync_error_words(
        position_ms=15000,
        duration_ms=duration_ms,
        span_count=30,
        timings=timings,
        estimated=True,
        playback_rate=playback_rate,
    )
    assert error <= 3


@pytest.mark.parametrize(
    ("estimated", "playback_rate", "minimum"),
    [
        (True, 1.0, ESTIMATED_SYNC_OFFSET_MS),
        (True, 2.0, ESTIMATED_SYNC_OFFSET_MS + 40),
        (False, 1.0, EXACT_SYNC_OFFSET_MS),
        (False, 1.5, EXACT_SYNC_OFFSET_MS + 30),
    ],
)
def test_highlight_sync_offset_scales_with_mode(
    estimated: bool, playback_rate: float, minimum: int
):
    offset = highlight_sync_offset_ms(
        estimated=estimated, playback_rate=playback_rate
    )
    assert offset >= minimum


def test_sync_offset_advances_highlight_vs_zero_offset():
    text = _sample_text(20)
    duration_ms = 20000
    timings = estimate_word_timings_from_text(text, duration_ms)
    position_ms = 10000

    without = playback_progress(
        position_ms=position_ms,
        duration_ms=duration_ms,
        span_count=20,
        timings=timings,
        estimated=True,
        sync_offset_ms=0,
    )
    with_offset = playback_progress(
        position_ms=position_ms,
        duration_ms=duration_ms,
        span_count=20,
        timings=timings,
        estimated=True,
        sync_offset_ms=ESTIMATED_SYNC_OFFSET_MS,
    )
    assert with_offset.word_index >= without.word_index


def test_word_timings_bundle_roundtrip(tmp_path):
    from src.core.tts_engine import TTSEngine

    tts = TTSEngine()
    tts.set_app_dir(tmp_path)
    key = tts._cache_key("hello world")
    tts._save_word_timings(
        key,
        [(0, 400), (400, 900)],
        estimated=True,
    )
    loaded = tts._load_word_timings(key)
    assert loaded is not None
    timings, estimated = loaded
    assert estimated is True
    assert timings == [(0, 400), (400, 900)]

    info = tts.word_timings_info_for("hello world")
    assert isinstance(info, WordTimingsBundle)
    assert info.estimated is True


def test_legacy_timings_json_treated_as_estimated(tmp_path):
    from src.core.tts_engine import TTSEngine

    tts = TTSEngine()
    tts.set_app_dir(tmp_path)
    key = tts._cache_key("legacy")
    path = tts._timings_path(key)
    path.write_text(json.dumps([[0, 500], [500, 1000]]), encoding="utf-8")

    loaded = tts._load_word_timings(key)
    assert loaded is not None
    _, estimated = loaded
    assert estimated is True


def test_engine_specific_offset_for_piper():
    offset = highlight_sync_offset_ms(estimated=True, engine="piper")
    assert offset >= 320


def test_normalize_skips_partial_player_duration():
    text = _sample_text(20)
    timings = estimate_word_timings_from_text(text, 20000)
    short_player = normalize_timings_to_duration(timings, 8000, estimated=True)
    assert short_player == timings
    full_player = normalize_timings_to_duration(timings, 20000, estimated=True)
    assert full_player[-1][1] == 20000


def test_should_normalize_timings():
    from src.core.word_highlight import should_normalize_timings

    timings = [(0, 500), (500, 10000)]
    assert should_normalize_timings(timings, 5000, estimated=True) is False
    assert should_normalize_timings(timings, 9500, estimated=True) is True


def test_normalize_exact_timings_adjusts_tail_only():
    timings = [(0, 500), (500, 1000), (1000, 1500)]
    adjusted = normalize_timings_to_duration(
        timings, 1800, estimated=False
    )
    assert adjusted[:2] == timings[:2]
    assert adjusted[-1][1] == 1800


def test_sentence_weighted_estimation_covers_duration():
    text = "First sentence here. Second sentence follows."
    duration_ms = 10000
    timings = estimate_word_timings_from_text(text, duration_ms)
    words = text.split()
    assert len(timings) == len(words)
    assert timings[-1][1] == duration_ms


def test_exact_timings_use_smaller_offset():
    timings = [(0, 500), (500, 1000), (1000, 1500)]
    estimated_progress = playback_progress(
        position_ms=800,
        duration_ms=1500,
        span_count=3,
        timings=timings,
        estimated=True,
    )
    exact_progress = playback_progress(
        position_ms=800,
        duration_ms=1500,
        span_count=3,
        timings=timings,
        estimated=False,
    )
    assert exact_progress.word_index >= estimated_progress.word_index - 1


@pytest.mark.parametrize("style_threshold", [(True, 0.006), (False, 0.035)])
def test_playback_progress_monotonic_over_time(style_threshold):
    text = _sample_text(16)
    duration_ms = 16000
    timings = estimate_word_timings_from_text(text, duration_ms)
    last_index = -1
    for pos in range(0, duration_ms, 400):
        progress = playback_progress(
            position_ms=pos,
            duration_ms=duration_ms,
            span_count=16,
            timings=timings,
            estimated=True,
        )
        assert progress.word_index >= last_index
        last_index = progress.word_index
