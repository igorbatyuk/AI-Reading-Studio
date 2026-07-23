"""Local estimate of DeepL API character usage."""

from __future__ import annotations

from datetime import date

from .database import Database

FREE_MONTHLY_CHAR_LIMIT = 1_000_000
USAGE_MONTH_KEY = "deepl_translate_usage_month"
USAGE_CHARS_KEY = "deepl_translate_usage_chars"


class DeepLTranslateUsage:
    """Track approximate source characters sent via DeepL API."""

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
            self.db.set_setting(USAGE_CHARS_KEY, "0")
            return 0
        return int(self.db.get_setting(USAGE_CHARS_KEY, "0") or 0)

    def record(self, char_count: int) -> None:
        if char_count <= 0:
            return
        used = self._ensure_current_month()
        self.db.set_setting(USAGE_CHARS_KEY, str(used + char_count))

    def status(self) -> dict[str, int | str]:
        used = self._ensure_current_month()
        limit = FREE_MONTHLY_CHAR_LIMIT
        remaining = max(0, limit - used)
        percent = min(100, int(used * 100 / limit)) if limit else 0
        return {
            "month": self.current_month(),
            "used": used,
            "limit": limit,
            "remaining": remaining,
            "percent": percent,
        }
