"""Save and load book cover images."""

from __future__ import annotations

import base64
from pathlib import Path


class CoverService:
    def __init__(self, app_dir: Path) -> None:
        self.covers_dir = app_dir / "covers"
        self.covers_dir.mkdir(parents=True, exist_ok=True)

    def save_cover(self, book_id: int, data: bytes) -> str:
        if not data:
            return ""
        ext = _detect_ext(data)
        path = self.covers_dir / f"{book_id}{ext}"
        path.write_bytes(data)
        self._remove_other_exts(book_id, ext)
        return str(path)

    def get_cover_path(self, book_id: int, stored_path: str | None = None) -> Path | None:
        if stored_path and Path(stored_path).exists():
            return Path(stored_path)
        for ext in (".jpg", ".jpeg", ".png", ".webp"):
            path = self.covers_dir / f"{book_id}{ext}"
            if path.exists():
                return path
        return None

    def read_cover_bytes(self, book_id: int, stored_path: str | None = None) -> bytes | None:
        path = self.get_cover_path(book_id, stored_path)
        if path and path.exists():
            return path.read_bytes()
        return None

    def import_cover_b64(self, book_id: int, cover_b64: str) -> str:
        if not cover_b64:
            return ""
        try:
            data = base64.b64decode(cover_b64)
        except Exception:
            return ""
        return self.save_cover(book_id, data)

    def delete_cover(self, book_id: int) -> None:
        for ext in (".jpg", ".jpeg", ".png", ".webp"):
            path = self.covers_dir / f"{book_id}{ext}"
            if path.exists():
                path.unlink(missing_ok=True)

    def _remove_other_exts(self, book_id: int, keep_ext: str) -> None:
        for ext in (".jpg", ".jpeg", ".png", ".webp"):
            if ext != keep_ext:
                path = self.covers_dir / f"{book_id}{ext}"
                if path.exists():
                    path.unlink(missing_ok=True)


def _detect_ext(data: bytes) -> str:
    if data[:3] == b"\xff\xd8\xff":
        return ".jpg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return ".png"
    if data[:4] == b"RIFF" and len(data) >= 12 and data[8:12] == b"WEBP":
        return ".webp"
    return ".jpg"
