"""Voice sorting preferences (Settings → Voice preferences, backup v5)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field, replace

VOICE_SORT_SETTING_KEYS: tuple[str, ...] = (
    "voice_sort_preset",
    "voice_gender_pref",
    "voice_region_pref",
    "voice_hide_unsuitable",
    "voice_show_recommended_badge",
    "voice_custom_order_json",
)

PRESET_BOOK = "book"
PRESET_NEWS = "news"
PRESET_FAST = "fast"
PRESET_CUSTOM = "custom"

GENDER_FEMALE = "female"
GENDER_MALE = "male"
GENDER_MIX = "mix"

REGION_US = "us"
REGION_UK = "uk"
REGION_AU = "au"
REGION_ANY = "any"

_VALID_PRESETS = frozenset({PRESET_BOOK, PRESET_NEWS, PRESET_FAST, PRESET_CUSTOM})
_VALID_GENDERS = frozenset({GENDER_FEMALE, GENDER_MALE, GENDER_MIX})
_VALID_REGIONS = frozenset({REGION_US, REGION_UK, REGION_AU, REGION_ANY})


@dataclass
class VoiceSortPrefs:
    preset: str = PRESET_BOOK
    gender_pref: str = GENDER_FEMALE
    region_pref: str = REGION_US
    hide_unsuitable: bool = True
    show_recommended_badge: bool = False
    custom_order: dict[str, list[str]] = field(default_factory=dict)

    def effective(self) -> VoiceSortPrefs:
        """Preset overrides applied at sort time."""
        if self.preset == PRESET_NEWS:
            return replace(
                self,
                gender_pref=GENDER_MALE,
                hide_unsuitable=True,
            )
        if self.preset == PRESET_FAST:
            return replace(
                self,
                gender_pref=GENDER_MIX,
                region_pref=REGION_ANY,
                hide_unsuitable=False,
                show_recommended_badge=False,
            )
        return self

    @classmethod
    def from_settings(cls, settings: dict[str, str]) -> VoiceSortPrefs:
        preset = settings.get("voice_sort_preset", PRESET_BOOK)
        if preset not in _VALID_PRESETS:
            preset = PRESET_BOOK
        gender = settings.get("voice_gender_pref", GENDER_FEMALE)
        if gender not in _VALID_GENDERS:
            gender = GENDER_FEMALE
        region = settings.get("voice_region_pref", REGION_US)
        if region not in _VALID_REGIONS:
            region = REGION_US
        hide = settings.get("voice_hide_unsuitable", "1") != "0"
        badge = settings.get("voice_show_recommended_badge", "0") == "1"
        custom_raw = settings.get("voice_custom_order_json", "").strip()
        custom_order: dict[str, list[str]] = {}
        if custom_raw:
            try:
                parsed = json.loads(custom_raw)
                if isinstance(parsed, dict):
                    for engine, ids in parsed.items():
                        if isinstance(engine, str) and isinstance(ids, list):
                            custom_order[engine] = [str(v) for v in ids if v]
            except json.JSONDecodeError:
                pass
        return cls(
            preset=preset,
            gender_pref=gender,
            region_pref=region,
            hide_unsuitable=hide,
            show_recommended_badge=badge,
            custom_order=custom_order,
        )

    def to_settings(self) -> dict[str, str]:
        return {
            "voice_sort_preset": self.preset,
            "voice_gender_pref": self.gender_pref,
            "voice_region_pref": self.region_pref,
            "voice_hide_unsuitable": "1" if self.hide_unsuitable else "0",
            "voice_show_recommended_badge": "1" if self.show_recommended_badge else "0",
            "voice_custom_order_json": json.dumps(
                self.custom_order, ensure_ascii=False, separators=(",", ":")
            ),
        }

    def save_to_db(self, db) -> None:
        for key, value in self.to_settings().items():
            db.set_setting(key, value)

    @classmethod
    def load_from_db(cls, db) -> VoiceSortPrefs:
        return cls.from_settings(db.get_all_settings())
