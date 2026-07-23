"""TTS engine policy helpers (block size, prefetch depth)."""

from __future__ import annotations

SLOW_OFFLINE_ENGINES = frozenset({"kokoro", "xtts", "styletts2"})

RECOMMENDED_BLOCK_WORDS: dict[str, int] = {
    "system": 130,
    "piper": 100,
    "kokoro": 55,
    "xtts": 55,
    "styletts2": 45,
}


def is_slow_offline_engine(engine: str) -> bool:
    return engine in SLOW_OFFLINE_ENGINES


def recommended_block_words(engine: str) -> int:
    return RECOMMENDED_BLOCK_WORDS.get(engine, 75)


def prefetch_ahead_blocks(
    *,
    tts_mode: str,
    offline_engine: str,
) -> int:
    if tts_mode == "offline" and is_slow_offline_engine(offline_engine):
        return 2
    if tts_mode == "auto" and is_slow_offline_engine(offline_engine):
        return 2
    return 1
