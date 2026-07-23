"""Tests for backup sync folder and sensitive settings stripping."""

import json
from pathlib import Path

import pytest

from src.core.backup_service import BackupService
from src.core.database import BACKUP_STRIPPED_SETTINGS, Database


@pytest.fixture
def db(tmp_path: Path) -> Database:
    return Database(tmp_path / "test.db")


def test_sync_to_folder_writes_backup(db: Database, tmp_path: Path) -> None:
    db.add_book("Sync Book", "Author", "/fake/book.txt", ".txt", [("Hello", "")])
    service = BackupService(db)
    folder = tmp_path / "sync"
    path = service.sync_to_folder(folder)
    assert path.exists()
    assert path.name == BackupService.DEFAULT_FILENAME
    assert "Sync Book" in path.read_text(encoding="utf-8")


def test_export_auto_syncs_when_folder_set(db: Database, tmp_path: Path) -> None:
    db.add_book("Auto Sync", "Author", "/fake/book.txt", ".txt", [("Hi", "")])
    sync_dir = tmp_path / "cloud"
    db.set_setting("sync_folder", str(sync_dir))
    service = BackupService(db)
    export_path = tmp_path / "manual.json"
    service.export_to_file(export_path)
    synced = sync_dir / BackupService.DEFAULT_FILENAME
    assert export_path.exists()
    assert synced.exists()
    assert "Auto Sync" in synced.read_text(encoding="utf-8")


def test_export_strips_all_api_keys(db: Database) -> None:
    for key in BACKUP_STRIPPED_SETTINGS:
        db.set_setting(key, f"secret-{key}")
    db.set_setting("azure_speech_region", "westeurope")
    db.set_setting("tts_voice", "en-US-AriaNeural")

    payload = db.export_data()
    settings = payload["settings"]

    for key in BACKUP_STRIPPED_SETTINGS:
        assert key not in settings, f"{key} must not appear in backup export"
    assert settings.get("azure_speech_region") == "westeurope"
    assert settings.get("tts_voice") == "en-US-AriaNeural"


def test_import_skips_api_keys_from_backup(db: Database) -> None:
    data = {
        "version": Database.BACKUP_VERSION,
        "books": [],
        "daily_stats": [],
        "settings": {
            "elevenlabs_api_key": "sk-leaked",
            "cartesia_api_key": "sk_car_leaked",
            "murf_api_key": "murf-leaked",
            "azure_speech_key": "azure-leaked",
            "google_tts_api_key": "google-tts-leaked",
            "theme": "dark",
        },
    }
    db.import_data(data, merge=True)
    assert db.get_setting("elevenlabs_api_key", "") == ""
    assert db.get_setting("cartesia_api_key", "") == ""
    assert db.get_setting("theme") == "dark"


def test_export_json_contains_no_api_key_fields(db: Database, tmp_path: Path) -> None:
    db.set_setting("murf_api_key", "leak-test")
    export_path = tmp_path / "backup.json"
    BackupService(db).export_to_file(export_path)
    raw = json.loads(export_path.read_text(encoding="utf-8"))
    for key in BACKUP_STRIPPED_SETTINGS:
        assert key not in raw.get("settings", {})
