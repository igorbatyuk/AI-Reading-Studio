"""Local backup export and import."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from .database import Database

logger = logging.getLogger(__name__)


class BackupService:
    DEFAULT_FILENAME = "reading_studio_backup.json"
    SUPPORTED_VERSIONS = {3, 4}

    def __init__(self, db: Database) -> None:
        self.db = db

    def export_to_file(self, file_path: str | Path) -> Path:
        data = self.db.export_data()
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        logger.info("Backup exported to %s (%d books)", path, len(data.get("books", [])))

        sync_folder = self.db.get_setting("sync_folder", "").strip()
        if sync_folder:
            self.sync_to_folder(Path(sync_folder))

        return path

    def sync_to_folder(self, folder: Path) -> Path:
        """Write the latest backup JSON into a sync folder."""
        folder = Path(folder)
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / self.DEFAULT_FILENAME
        data = self.db.export_data()
        target.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.info("Backup synced to %s", target)
        return target

    def import_from_file(self, file_path: str | Path, merge: bool = True) -> dict:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Backup file not found: {path}")

        try:
            raw = path.read_text(encoding="utf-8")
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid backup JSON: {exc}") from exc

        version = data.get("version", 0)
        if version not in self.SUPPORTED_VERSIONS:
            raise ValueError(
                f"Unsupported backup version {version}. "
                f"Supported: {sorted(self.SUPPORTED_VERSIONS)}"
            )

        result = self.db.import_data(data, merge=merge)
        logger.info(
            "Backup imported from %s: %s",
            path,
            result,
        )
        return result

    def clear_user_data(self) -> dict[str, int]:
        """Remove books, reading stats, audio cache, and covers. Keep settings/API keys."""
        counts = self.db.clear_library_data()
        counts["audio_files"] = self._clear_directory(self.db.app_dir / "audio")
        counts["cover_files"] = self._clear_directory(self.db.app_dir / "covers")
        logger.info("User data cleared: %s", counts)
        return counts

    @staticmethod
    def _clear_directory(path: Path) -> int:
        removed = 0
        if not path.is_dir():
            return removed
        for item in path.iterdir():
            if not item.is_file():
                continue
            try:
                item.unlink()
                removed += 1
            except OSError as exc:
                logger.warning("Could not delete %s: %s", item, exc)
        return removed
