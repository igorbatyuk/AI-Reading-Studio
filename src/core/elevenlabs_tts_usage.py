"""ElevenLabs TTS credit usage — local estimate + optional API sync."""

from __future__ import annotations

from datetime import date, datetime, timezone

from .database import Database

FREE_MONTHLY_CREDIT_LIMIT = 10_000
USAGE_MONTH_KEY = "elevenlabs_tts_usage_month"
USAGE_CREDITS_KEY = "elevenlabs_tts_usage_credits"
API_USED_KEY = "elevenlabs_tts_api_used"
API_LIMIT_KEY = "elevenlabs_tts_api_limit"
API_SYNC_AT_KEY = "elevenlabs_tts_api_sync_at"
API_TIER_KEY = "elevenlabs_tts_api_tier"

# Flash v2.5: ~0.5 credit per character (Multilingual v2 ≈ 1:1).
CREDITS_PER_CHARACTER = 0.5
SYNC_MIN_INTERVAL_HOURS = 24


class ElevenLabsTTSUsage:
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

    def _last_sync_age_hours(self) -> float | None:
        sync_at = self.db.get_setting(API_SYNC_AT_KEY, "")
        if not sync_at:
            return None
        try:
            synced = datetime.fromisoformat(sync_at)
            if synced.tzinfo is None:
                synced = synced.replace(tzinfo=timezone.utc)
            return (datetime.now(timezone.utc) - synced).total_seconds() / 3600
        except ValueError:
            return None

    def sync_from_api(self, api_key: str, *, force: bool = False) -> bool:
        from . import elevenlabs_tts

        if not api_key:
            return False
        age = self._last_sync_age_hours()
        if not force and age is not None and age < SYNC_MIN_INTERVAL_HOURS:
            return True
        try:
            stats = elevenlabs_tts.fetch_subscription(api_key)
        except Exception:
            return False
        self.db.set_setting(API_USED_KEY, str(int(stats["used"])))
        self.db.set_setting(API_LIMIT_KEY, str(int(stats["limit"])))
        self.db.set_setting(API_TIER_KEY, str(stats.get("tier") or ""))
        self.db.set_setting(
            API_SYNC_AT_KEY,
            datetime.now(timezone.utc).isoformat(),
        )
        return True

    def _api_snapshot(self) -> dict[str, int | str] | None:
        sync_at = self.db.get_setting(API_SYNC_AT_KEY, "")
        if not sync_at:
            return None
        age = self._last_sync_age_hours()
        if age is None or age > SYNC_MIN_INTERVAL_HOURS * 7:
            return None
        limit = int(self.db.get_setting(API_LIMIT_KEY, "0") or 0)
        if limit <= 0:
            return None
        used = int(self.db.get_setting(API_USED_KEY, "0") or 0)
        return {
            "used": used,
            "limit": limit,
            "remaining": max(0, limit - used),
            "tier": self.db.get_setting(API_TIER_KEY, ""),
            "source": "api",
        }

    def status(self) -> dict[str, int | str]:
        local_used = self._ensure_current_month()
        local_limit = FREE_MONTHLY_CREDIT_LIMIT
        api = self._api_snapshot()
        if api:
            used = int(api["used"])
            limit = int(api["limit"])
            source = "api"
            tier = str(api.get("tier") or "")
        else:
            used = local_used
            limit = local_limit
            source = "local"
            tier = ""
        remaining = max(0, limit - used)
        percent = min(100, int(used * 100 / limit)) if limit else 0
        return {
            "month": self.current_month(),
            "used": used,
            "limit": limit,
            "remaining": remaining,
            "percent": percent,
            "local_used": local_used,
            "source": source,
            "tier": tier,
        }

    def can_spend(self, char_count: int) -> bool:
        needed = self.estimate_credits(char_count)
        stats = self.status()
        if stats["remaining"] < needed:
            return False
        local_used = int(stats.get("local_used", 0))
        if stats.get("source") == "local" and local_used + needed > FREE_MONTHLY_CREDIT_LIMIT:
            return False
        return True

    def should_sync_subscription(self) -> bool:
        age = self._last_sync_age_hours()
        return age is None or age >= SYNC_MIN_INTERVAL_HOURS
