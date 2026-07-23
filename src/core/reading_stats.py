"""Helpers for reading statistics estimates."""

from __future__ import annotations

GOAL_TYPE_BLOCKS = "blocks"
GOAL_TYPE_TIME = "time"


def parse_daily_goal_settings(settings: dict[str, str]) -> dict[str, int | str]:
    goal_type = settings.get("daily_goal_type", GOAL_TYPE_BLOCKS)
    if goal_type not in (GOAL_TYPE_BLOCKS, GOAL_TYPE_TIME):
        goal_type = GOAL_TYPE_BLOCKS
    return {
        "type": goal_type,
        "blocks": max(1, int(settings.get("daily_goal_blocks", "10") or 10)),
        "minutes": max(1, int(settings.get("daily_goal_minutes", "15") or 15)),
    }


def goal_target_seconds(settings: dict[str, str]) -> int:
    goal = parse_daily_goal_settings(settings)
    return int(goal["minutes"]) * 60


def is_daily_goal_met(
    blocks: int, seconds: int, settings: dict[str, str]
) -> bool:
    goal = parse_daily_goal_settings(settings)
    if goal["type"] == GOAL_TYPE_TIME:
        return seconds >= int(goal["minutes"]) * 60
    return blocks >= int(goal["blocks"])


def day_reading_status(
    blocks: int,
    goal_blocks: int,
    *,
    seconds: int = 0,
    settings: dict[str, str] | None = None,
) -> str:
    """completed = goal reached, partial = some reading, missed = none."""
    if settings is not None:
        goal = parse_daily_goal_settings(settings)
        if goal["type"] == GOAL_TYPE_TIME:
            target = int(goal["minutes"]) * 60
            if seconds >= target:
                return "completed"
            if seconds > 0 or blocks > 0:
                return "partial"
            return "missed"
        goal_blocks = int(goal["blocks"])

    if blocks >= goal_blocks:
        return "completed"
    if blocks > 0 or seconds > 0:
        return "partial"
    return "missed"


def format_reading_duration(seconds: int) -> str:
    """Format seconds as H:MM:SS or M:SS."""
    if seconds < 0:
        seconds = 0
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def estimate_reading_minutes(blocks: int, words: int) -> int:
    """Rough reading time from blocks and word count (~55 words/block, ~180 wpm)."""
    if blocks <= 0 and words <= 0:
        return 0
    by_blocks = blocks * 1.0
    by_words = words / 180.0
    if blocks > 0 and words > 0:
        return max(1, round((by_blocks + by_words) / 2))
    if blocks > 0:
        return max(1, round(by_blocks))
    return max(1, round(by_words))


def chart_bar_label(
    date_key: str, period: str, month_name_fn: callable | None = None
) -> str:
    if period == "week":
        return date_key[-5:].replace("-", "/")
    if period == "month":
        parts = date_key.split("-")
        if len(parts) >= 2 and month_name_fn:
            name = month_name_fn(int(parts[1]))
            return name[:3] if name else parts[1]
        return date_key[-2:]
    return date_key[:4]
