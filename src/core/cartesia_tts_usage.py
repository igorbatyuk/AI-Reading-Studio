"""Cartesia TTS credit usage — local estimate (free tier ~20k credits/month)."""

from __future__ import annotations

from datetime import date

from .database import Database

FREE_MONTHLY_CREDIT_LIMIT = 20_000
USAGE_MONTH_KEY = "cartesia_tts_usage_month"
USAGE_CREDITS_KEY = "cartesia_tts_usage_credits"

# Standard TTS: ~1 credit per character (see Cartesia pricing docs).
CREDITS_PER_CHARACTER = 1.0


class CartesiaTTSUsage:
    def __init__(self, db: Database) -> None:
        self.db = db

    @staticmethod
    def current_month() -> str:
        return date.today().strftime("%Y-%m")

    def _ensure_current_month(self) -> int:
        month = self.current_month()
        stored_month = self.db.get_setting(USAGE_MONTH_KEY, "")
        if stored_month != month:
            self.db.set_setting(USAGE_MONTH_KEY, month)
            self.db.set_setting(USAGE_CREDITS_KEY, "0")
            return 0
        return int(self.db.get_setting(USAGE_CREDITS_KEY, "0") or 0)

    def estimate_credits(self, char_count: int) -> int:
        if char_count <= 0:
            return 0
        import math

        return max(1, math.ceil(char_count * CREDITS_PER_CHARACTER))

    def record(self, char_count: int) -> None:
        credits = self.estimate_credits(char_count)
        if credits <= 0:
            return
        used = self._ensure_current_month()
        self.db.set_setting(USAGE_CREDITS_KEY, str(used + credits))

    def status(self) -> dict[str, int | str]:
        used = self._ensure_current_month()
        limit = FREE_MONTHLY_CREDIT_LIMIT
        remaining = max(0, limit - used)
        percent = min(100, int(used * 100 / limit)) if limit else 0
        return {
            "month": self.current_month(),
            "used": used,
            "limit": limit,
            "remaining": remaining,
            "percent": percent,
        }

    def can_spend(self, char_count: int) -> bool:
        needed = self.estimate_credits(char_count)
        stats = self.status()
        return stats["remaining"] >= needed
