"""Murf TTS character usage — local estimate + optional API sync from responses."""

from __future__ import annotations

from datetime import date

from .database import Database

FREE_MONTHLY_CHAR_LIMIT = 100_000
USAGE_MONTH_KEY = "murf_tts_usage_month"
USAGE_CHARS_KEY = "murf_tts_usage_chars"
API_REMAINING_KEY = "murf_tts_api_remaining"
API_SYNC_AT_KEY = "murf_tts_api_sync_at"


class MurfTTSUsage:
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
            self.db.set_setting(API_REMAINING_KEY, "")
            self.db.set_setting(API_SYNC_AT_KEY, "")
            return 0
        return int(self.db.get_setting(USAGE_CHARS_KEY, "0") or 0)

    def record(self, char_count: int) -> None:
        if char_count <= 0:
            return
        used = self._ensure_current_month()
        self.db.set_setting(USAGE_CHARS_KEY, str(used + char_count))

    def sync_from_response(self, *, consumed: int, remaining: int) -> None:
        self._ensure_current_month()
        if consumed > 0:
            self.db.set_setting(USAGE_CHARS_KEY, str(consumed))
        if remaining >= 0:
            self.db.set_setting(API_REMAINING_KEY, str(remaining))
            self.db.set_setting(API_SYNC_AT_KEY, self.current_month())

    def status(self) -> dict[str, int | str]:
        local_used = self._ensure_current_month()
        api_remaining_raw = self.db.get_setting(API_REMAINING_KEY, "")
        api_sync_month = self.db.get_setting(API_SYNC_AT_KEY, "")
        if api_remaining_raw.isdigit() and api_sync_month == self.current_month():
            remaining = int(api_remaining_raw)
            limit = remaining + local_used
            if limit <= 0:
                limit = FREE_MONTHLY_CHAR_LIMIT
            used = max(0, limit - remaining)
            source = "api"
        else:
            limit = FREE_MONTHLY_CHAR_LIMIT
            used = local_used
            remaining = max(0, limit - used)
            source = "local"
        percent = min(100, int(used * 100 / limit)) if limit else 0
        return {
            "month": self.current_month(),
            "used": used,
            "limit": limit,
            "remaining": remaining,
            "percent": percent,
            "local_used": local_used,
            "source": source,
        }

    def can_spend(self, char_count: int) -> bool:
        stats = self.status()
        return stats["remaining"] >= char_count
