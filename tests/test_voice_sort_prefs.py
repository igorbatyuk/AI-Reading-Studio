"""Tests for voice sorting preferences (Phases 2–3)."""

import json
from pathlib import Path

import pytest

from src.core.database import Database
from src.core.tts_voice_ranking import sort_voices_for_reading
from src.core.tts_voices import format_stored_voice, get_voices_for_tts_context
from src.core.voice_sort_prefs import (
    GENDER_MALE,
    PRESET_CUSTOM,
    PRESET_FAST,
    PRESET_NEWS,
    REGION_UK,
    VOICE_SORT_SETTING_KEYS,
    VoiceSortPrefs,
)


@pytest.fixture
def db(tmp_path: Path) -> Database:
    return Database(tmp_path / "test.db")


def test_voice_sort_prefs_roundtrip_settings():
    prefs = VoiceSortPrefs(
        preset=PRESET_CUSTOM,
        gender_pref=GENDER_MALE,
        region_pref=REGION_UK,
        hide_unsuitable=False,
        show_recommended_badge=True,
        custom_order={"edge": [format_stored_voice("edge", "en-US-GuyNeural")]},
    )
    loaded = VoiceSortPrefs.from_settings(prefs.to_settings())
    assert loaded.preset == PRESET_CUSTOM
    assert loaded.gender_pref == GENDER_MALE
    assert loaded.region_pref == REGION_UK
    assert loaded.hide_unsuitable is False
    assert loaded.show_recommended_badge is True
    assert loaded.custom_order["edge"][0].endswith("GuyNeural")


def test_news_preset_puts_male_first():
    voices = get_voices_for_tts_context(
        "en",
        "online",
        "system",
        online_engine="edge",
        voice_sort_prefs=VoiceSortPrefs(preset=PRESET_NEWS),
    )
    ids = [v[0] for v in voices]
    guy = format_stored_voice("edge", "en-US-GuyNeural")
    jenny = format_stored_voice("edge", "en-US-JennyNeural")
    assert guy in ids and jenny in ids
    assert ids.index(guy) < ids.index(jenny)


def test_fast_preset_shows_multilingual():
    voices = get_voices_for_tts_context(
        "en",
        "online",
        "system",
        online_engine="edge",
        voice_sort_prefs=VoiceSortPrefs(preset=PRESET_FAST),
    )
    ids = {v[0] for v in voices}
    assert format_stored_voice("edge", "en-US-AvaMultilingualNeural") in ids


def test_uk_region_pref():
    prefs = VoiceSortPrefs(region_pref=REGION_UK, hide_unsuitable=False)
    voices = get_voices_for_tts_context(
        "en",
        "online",
        "system",
        online_engine="edge",
        voice_sort_prefs=prefs,
    )
    ids = [v[0] for v in voices]
    sonia = format_stored_voice("edge", "en-GB-SoniaNeural")
    jenny = format_stored_voice("edge", "en-US-JennyNeural")
    assert sonia in ids and jenny in ids
    assert ids.index(sonia) < ids.index(jenny)


def test_custom_order_applied():
    guy = format_stored_voice("edge", "en-US-GuyNeural")
    jenny = format_stored_voice("edge", "en-US-JennyNeural")
    aria = format_stored_voice("edge", "en-US-AriaNeural")
    raw = [
        (jenny, "Edge — Jenny"),
        (aria, "Edge — Aria"),
        (guy, "Edge — Guy"),
    ]
    prefs = VoiceSortPrefs(
        preset=PRESET_CUSTOM,
        custom_order={"edge": [guy, jenny, aria]},
    )
    ordered = sort_voices_for_reading(raw, "en", "edge", prefs)
    assert [v[0] for v in ordered] == [guy, jenny, aria]


def test_recommended_badge_prefix():
    prefs = VoiceSortPrefs(show_recommended_badge=True)
    voices = get_voices_for_tts_context(
        "en",
        "online",
        "system",
        online_engine="edge",
        voice_sort_prefs=prefs,
    )
    assert voices[0][1].startswith("★ ")


def test_backup_exports_voice_sort_prefs(db: Database):
    prefs = VoiceSortPrefs(
        preset=PRESET_CUSTOM,
        gender_pref=GENDER_MALE,
        custom_order={"edge": ["edge:en-US-GuyNeural"]},
    )
    prefs.save_to_db(db)
    exported = db.export_data()
    assert exported["version"] == 5
    settings = exported["settings"]
    for key in VOICE_SORT_SETTING_KEYS:
        assert key in settings
    assert settings["voice_sort_preset"] == PRESET_CUSTOM
    assert json.loads(settings["voice_custom_order_json"])["edge"]


def test_backup_imports_voice_sort_prefs(db: Database):
    data = {
        "version": 5,
        "books": [],
        "daily_stats": [],
        "settings": VoiceSortPrefs(
            preset=PRESET_NEWS,
            region_pref=REGION_UK,
        ).to_settings(),
    }
    db.import_data(data, merge=True)
    loaded = VoiceSortPrefs.from_settings(db.get_all_settings())
    assert loaded.preset == PRESET_NEWS
    assert loaded.region_pref == REGION_UK
