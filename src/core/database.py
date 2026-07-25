"""SQLite database for books, progress, and statistics."""

from __future__ import annotations

import base64
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from .cover_service import CoverService

# Never export/import via backup JSON (keys live in OS keyring).
BACKUP_STRIPPED_SETTINGS = frozenset(
    {
        "openai_api_key",
        "apify_api_token",
        "google_api_key",
        "deepl_api_key",
        "azure_speech_key",
        "google_tts_api_key",
        "elevenlabs_api_key",
        "cartesia_api_key",
        "murf_api_key",
    }
)


@dataclass
class Book:
    id: int
    title: str
    author: str
    file_path: str
    format: str
    total_blocks: int
    current_block: int
    progress_percent: float
    last_read_at: str | None
    added_at: str
    cover_path: str | None = None
    use_saved_audio: bool = True


class Database:
    BACKUP_VERSION = 5

    def __init__(self, db_path: Path | None = None) -> None:
        if db_path is None:
            app_dir = Path.home() / ".ai_reading_studio"
            app_dir.mkdir(parents=True, exist_ok=True)
            db_path = app_dir / "reading_studio.db"
        self.db_path = db_path
        self.app_dir = db_path.parent
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS books (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    author TEXT DEFAULT '',
                    file_path TEXT NOT NULL UNIQUE,
                    format TEXT NOT NULL,
                    total_blocks INTEGER DEFAULT 0,
                    current_block INTEGER DEFAULT 0,
                    progress_percent REAL DEFAULT 0,
                    last_read_at TEXT,
                    added_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS blocks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    book_id INTEGER NOT NULL,
                    block_index INTEGER NOT NULL,
                    text TEXT NOT NULL,
                    chapter TEXT DEFAULT '',
                    FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE,
                    UNIQUE(book_id, block_index)
                );

                CREATE TABLE IF NOT EXISTS daily_stats (
                    date TEXT PRIMARY KEY,
                    seconds INTEGER DEFAULT 0,
                    goal_met INTEGER DEFAULT 0,
                    words_read INTEGER DEFAULT 0,
                    blocks_read INTEGER DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS read_blocks (
                    date TEXT NOT NULL,
                    book_id INTEGER NOT NULL,
                    block_index INTEGER NOT NULL,
                    words INTEGER DEFAULT 0,
                    PRIMARY KEY (date, book_id, block_index),
                    FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                """
            )
            defaults = {
                "daily_goal_blocks": "10",
                "daily_goal_type": "blocks",
                "daily_goal_minutes": "15",
                "ui_language": "uk",
                "translation_language": "uk",
                "tts_speed": "1.0",
                "font_size": "18",
                "font_family": "Segoe UI",
                "line_width": "680",
                "block_words_target": "55",
                "theme": "light",
                "tts_voice": "en-US-AriaNeural",
                "book_language": "en",
                "tts_mode": "auto",
                "pdf_ocr_mode": "auto",
                "pdf_ocr_max_pages": "40",
                "offline_engine": "system",
                "online_engine": "edge",
                "piper_model_path": "",
                "styletts2_model_path": "",
                "azure_speech_key": "",
                "azure_speech_region": "",
                "google_tts_api_key": "",
                "elevenlabs_api_key": "",
                "cartesia_api_key": "",
                "murf_api_key": "",
                "update_check": "1",
                "github_repo": "",
                "translation_provider": "auto",
                "translation_block_provider": "auto",
                "translation_word_provider": "free",
                "translation_selection_provider": "apify",
                "ollama_url": "http://127.0.0.1:11434",
                "ollama_model": "",
                "openai_api_key": "",
                "apify_api_token": "",
                "google_api_key": "",
                "deepl_api_key": "",
                "word_highlight": "1",
                "word_highlight_style": "gradient",
                "word_highlight_color": "#ffe08a",
                "word_highlight_color_2": "#8ec5ff",
                "word_highlight_color_3": "#c4a8ff",
                "word_highlight_text_color": "#1a1a1a",
                "word_highlight_palette": "warm",
                "word_tts": "1",
                "word_tts_profile": "same",
                "word_tts_mode": "auto",
                "word_tts_online_engine": "edge",
                "word_tts_offline_engine": "system",
                "word_tts_voice": "",
                "playback_rate": "1.0",
                "whisper_word_align": "auto",
                "sync_folder": "",
            }
            for key, value in defaults.items():
                conn.execute(
                    "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
                    (key, value),
                )
            self._migrate_schema(conn)

    def _migrate_schema(self, conn: sqlite3.Connection) -> None:
        columns = {
            row[1]
            for row in conn.execute("PRAGMA table_info(daily_stats)").fetchall()
        }
        if "blocks_read" not in columns:
            conn.execute(
                "ALTER TABLE daily_stats ADD COLUMN blocks_read INTEGER DEFAULT 0"
            )
        conn.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES ('daily_goal_blocks', '10')"
        )
        conn.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES ('daily_goal_type', 'blocks')"
        )
        conn.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES ('daily_goal_minutes', '15')"
        )
        conn.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES ('ui_language', 'uk')"
        )
        conn.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES ('block_words_target', '55')"
        )
        conn.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES ('translation_language', 'uk')"
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS read_blocks (
                date TEXT NOT NULL,
                book_id INTEGER NOT NULL,
                block_index INTEGER NOT NULL,
                words INTEGER DEFAULT 0,
                PRIMARY KEY (date, book_id, block_index),
                FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE
            )
            """
        )
        conn.execute("DROP TABLE IF EXISTS bookmarks")
        conn.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES ('tts_mode', 'auto')"
        )
        conn.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES ('pdf_ocr_mode', 'auto')"
        )
        conn.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES ('pdf_ocr_max_pages', '40')"
        )
        conn.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES ('offline_engine', 'system')"
        )
        conn.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES ('update_check', '1')"
        )
        conn.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES ('piper_model_path', '')"
        )
        conn.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES ('github_repo', '')"
        )
        conn.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES ('translation_provider', 'auto')"
        )
        conn.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES ('translation_block_provider', 'auto')"
        )
        conn.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES ('translation_word_provider', 'free')"
        )
        conn.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES ('translation_selection_provider', 'apify')"
        )
        conn.execute(
            "UPDATE settings SET value = 'apify' WHERE key LIKE 'translation_%_provider' AND value = 'google'"
        )
        conn.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES ('ollama_url', 'http://127.0.0.1:11434')"
        )
        conn.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES ('ollama_model', '')"
        )
        conn.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES ('apify_api_token', '')"
        )
        conn.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES ('google_api_key', '')"
        )
        conn.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES ('apify_translate_usage_month', '')"
        )
        conn.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES ('apify_translate_usage_chars', '0')"
        )
        conn.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES ('google_translate_usage_month', '')"
        )
        conn.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES ('google_translate_usage_chars', '0')"
        )
        conn.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES ('deepl_api_key', '')"
        )
        conn.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES ('deepl_translate_usage_month', '')"
        )
        conn.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES ('deepl_translate_usage_chars', '0')"
        )
        conn.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES ('word_highlight', '1')"
        )
        for key, value in (
            ("online_engine", "edge"),
            ("styletts2_model_path", ""),
            ("azure_speech_key", ""),
            ("azure_speech_region", ""),
            ("google_tts_api_key", ""),
            ("azure_tts_usage_month", ""),
            ("azure_tts_usage_chars", "0"),
            ("google_tts_usage_month", ""),
            ("google_tts_usage_chars", "0"),
            ("elevenlabs_api_key", ""),
            ("elevenlabs_tts_usage_month", ""),
            ("elevenlabs_tts_usage_credits", "0"),
            ("elevenlabs_tts_api_used", "0"),
            ("elevenlabs_tts_api_limit", "0"),
            ("elevenlabs_tts_api_sync_at", ""),
            ("elevenlabs_tts_api_tier", ""),
            ("cartesia_api_key", ""),
            ("cartesia_tts_usage_month", ""),
            ("cartesia_tts_usage_credits", "0"),
            ("murf_api_key", ""),
            ("murf_tts_usage_month", ""),
            ("murf_tts_usage_chars", "0"),
            ("murf_tts_api_remaining", ""),
            ("murf_tts_api_sync_at", ""),
        ):
            conn.execute(
                "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
                (key, value),
            )
        conn.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES ('word_highlight_style', 'smooth')"
        )
        conn.execute(
            """
            UPDATE settings SET value = 'gradient'
            WHERE key = 'word_highlight_style'
              AND value IN ('wave', 'flow', 'glow', 'shimmer')
            """
        )
        for key, value in (
            ("word_highlight_color", "#ffe08a"),
            ("word_highlight_color_2", "#8ec5ff"),
            ("word_highlight_color_3", "#c4a8ff"),
            ("word_highlight_text_color", "#1a1a1a"),
            ("word_highlight_palette", "warm"),
            ("word_tts", "1"),
            ("word_tts_profile", "same"),
            ("word_tts_mode", "auto"),
            ("word_tts_online_engine", "edge"),
            ("word_tts_offline_engine", "system"),
            ("word_tts_voice", ""),
            ("playback_rate", "1.0"),
            ("whisper_word_align", "auto"),
            ("sync_folder", ""),
        ):
            conn.execute(
                "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
                (key, value),
            )
        conn.execute(
            "UPDATE settings SET value = ? WHERE key = 'tts_voice' AND value = ?",
            (
                "elevenlabs:EXAVITQu4vr4xnSDxMaL",
                "elevenlabs:21m00Tcm4TlvDq8ikWAM",
            ),
        )
        book_cols = {
            row[1] for row in conn.execute("PRAGMA table_info(books)").fetchall()
        }
        if "cover_path" not in book_cols:
            conn.execute("ALTER TABLE books ADD COLUMN cover_path TEXT DEFAULT ''")
        if "use_saved_audio" not in book_cols:
            conn.execute(
                "ALTER TABLE books ADD COLUMN use_saved_audio INTEGER DEFAULT 1"
            )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS book_tags (
                book_id INTEGER NOT NULL,
                tag TEXT NOT NULL,
                PRIMARY KEY (book_id, tag),
                FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE
            )
            """
        )

    def get_setting(self, key: str, default: str = "") -> str:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT value FROM settings WHERE key = ?", (key,)
            ).fetchone()
            return row["value"] if row else default

    def set_setting(self, key: str, value: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                (key, value),
            )

    def get_all_settings(self) -> dict[str, str]:
        with self._connect() as conn:
            rows = conn.execute("SELECT key, value FROM settings").fetchall()
            return {row["key"]: row["value"] for row in rows}

    def get_daily_goal_settings(self) -> dict[str, str]:
        settings = self.get_all_settings()
        return {
            "daily_goal_type": settings.get("daily_goal_type", "blocks"),
            "daily_goal_blocks": settings.get("daily_goal_blocks", "10"),
            "daily_goal_minutes": settings.get("daily_goal_minutes", "15"),
        }

    def _sync_goal_met(self, conn: sqlite3.Connection, day: str) -> None:
        from .reading_stats import is_daily_goal_met

        row = conn.execute(
            "SELECT blocks_read, seconds FROM daily_stats WHERE date = ?",
            (day,),
        ).fetchone()
        if not row:
            return
        blocks = row["blocks_read"] or 0
        seconds = row["seconds"] or 0
        goal_met = 1 if is_daily_goal_met(blocks, seconds, self.get_daily_goal_settings()) else 0
        conn.execute(
            "UPDATE daily_stats SET goal_met = ? WHERE date = ?",
            (goal_met, day),
        )

    def add_book(
        self,
        title: str,
        author: str,
        file_path: str,
        book_format: str,
        blocks: list[tuple[str, str]],
    ) -> int:
        now = datetime.now().isoformat()
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO books (title, author, file_path, format, total_blocks, added_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (title, author, file_path, book_format, len(blocks), now),
            )
            book_id = cursor.lastrowid
            conn.executemany(
                """
                INSERT INTO blocks (book_id, block_index, text, chapter)
                VALUES (?, ?, ?, ?)
                """,
                [
                    (book_id, i, text, chapter)
                    for i, (text, chapter) in enumerate(blocks)
                ],
            )
            return book_id

    def set_book_use_saved_audio(self, book_id: int, enabled: bool) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE books SET use_saved_audio = ? WHERE id = ?",
                (1 if enabled else 0, book_id),
            )

    def get_book_use_saved_audio(self, book_id: int) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT use_saved_audio FROM books WHERE id = ?", (book_id,)
            ).fetchone()
            if not row:
                return True
            keys = row.keys()
            if "use_saved_audio" not in keys:
                return True
            return bool(row["use_saved_audio"])

    def update_cover_path(self, book_id: int, cover_path: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE books SET cover_path = ? WHERE id = ?",
                (cover_path, book_id),
            )

    def set_book_tags(self, book_id: int, tags: list[str]) -> None:
        cleaned = sorted({t.strip().lower() for t in tags if t.strip()})
        with self._connect() as conn:
            conn.execute("DELETE FROM book_tags WHERE book_id = ?", (book_id,))
            conn.executemany(
                "INSERT INTO book_tags (book_id, tag) VALUES (?, ?)",
                [(book_id, tag) for tag in cleaned],
            )

    def get_book_tags(self, book_id: int) -> list[str]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT tag FROM book_tags WHERE book_id = ? ORDER BY tag",
                (book_id,),
            ).fetchall()
            return [row["tag"] for row in rows]

    def get_all_tags(self) -> list[str]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT DISTINCT tag FROM book_tags ORDER BY tag"
            ).fetchall()
            return [row["tag"] for row in rows]

    def book_exists(self, file_path: str) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM books WHERE file_path = ?", (file_path,)
            ).fetchone()
            return row is not None

    def get_book(self, book_id: int) -> Book | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM books WHERE id = ?", (book_id,)).fetchone()
            if not row:
                return None
            return self._row_to_book(row)

    def get_book_by_title(self, title: str) -> Book | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM books WHERE title = ? LIMIT 1", (title,)
            ).fetchone()
            return self._row_to_book(row) if row else None

    def get_all_books(self, sort: str = "recent") -> list[Book]:
        order_sql = {
            "recent": (
                "CASE WHEN last_read_at IS NULL THEN 1 ELSE 0 END, "
                "last_read_at DESC, title COLLATE NOCASE"
            ),
            "title": "title COLLATE NOCASE",
            "author": "author COLLATE NOCASE, title COLLATE NOCASE",
            "progress": "progress_percent DESC, title COLLATE NOCASE",
            "added": "added_at DESC",
        }.get(sort, "last_read_at DESC")
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM books ORDER BY {order_sql}"
            ).fetchall()
            return [self._row_to_book(row) for row in rows]

    def get_last_read_book(self) -> Book | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM books
                WHERE last_read_at IS NOT NULL
                ORDER BY last_read_at DESC LIMIT 1
                """
            ).fetchone()
            return self._row_to_book(row) if row else None

    def update_book_progress(
        self, book_id: int, block_index: int, progress_percent: float
    ) -> None:
        now = datetime.now().isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE books
                SET current_block = ?, progress_percent = ?, last_read_at = ?
                WHERE id = ?
                """,
                (block_index, progress_percent, now, book_id),
            )

    def get_book_block_texts(self, book_id: int) -> list[str]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT text FROM blocks
                WHERE book_id = ?
                ORDER BY block_index
                """,
                (book_id,),
            ).fetchall()
            return [row["text"] for row in rows]

    def get_block(self, book_id: int, block_index: int) -> tuple[str, str] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT text, chapter FROM blocks
                WHERE book_id = ? AND block_index = ?
                """,
                (book_id, block_index),
            ).fetchone()
            if not row:
                return None
            return row["text"], row["chapter"]

    def record_block_read(
        self, book_id: int, block_index: int, words: int = 0
    ) -> bool:
        """Record a block as read today. Returns False if already counted."""
        today = date.today().isoformat()
        with self._connect() as conn:
            try:
                conn.execute(
                    """
                    INSERT INTO read_blocks (date, book_id, block_index, words)
                    VALUES (?, ?, ?, ?)
                    """,
                    (today, book_id, block_index, words),
                )
            except sqlite3.IntegrityError:
                return False

            row = conn.execute(
                "SELECT blocks_read, words_read FROM daily_stats WHERE date = ?",
                (today,),
            ).fetchone()
            if row:
                new_blocks = (row["blocks_read"] or 0) + 1
                conn.execute(
                    """
                    UPDATE daily_stats
                    SET blocks_read = ?, words_read = words_read + ?
                    WHERE date = ?
                    """,
                    (new_blocks, words, today),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO daily_stats
                    (date, seconds, goal_met, words_read, blocks_read)
                    VALUES (?, 0, 0, ?, 1)
                    """,
                    (today, words),
                )
            self._sync_goal_met(conn, today)
        return True

    def add_reading_seconds(self, seconds: int) -> None:
        if seconds <= 0:
            return
        today = date.today().isoformat()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT seconds FROM daily_stats WHERE date = ?", (today,)
            ).fetchone()
            if row:
                conn.execute(
                    "UPDATE daily_stats SET seconds = seconds + ? WHERE date = ?",
                    (seconds, today),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO daily_stats
                    (date, seconds, goal_met, words_read, blocks_read)
                    VALUES (?, ?, 0, 0, 0)
                    """,
                    (today, seconds),
                )
            self._sync_goal_met(conn, today)

    def update_book_file_path(self, book_id: int, file_path: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE books SET file_path = ? WHERE id = ?",
                (file_path, book_id),
            )

    def replace_book_blocks(
        self, book_id: int, blocks: list[tuple[str, str]]
    ) -> None:
        total = len(blocks)
        with self._connect() as conn:
            row = conn.execute(
                "SELECT current_block FROM books WHERE id = ?", (book_id,)
            ).fetchone()
            if not row:
                return
            current = min(row["current_block"], max(total - 1, 0))
            progress = (
                (current / max(total - 1, 1)) * 100 if total > 1 else (100.0 if total else 0)
            )
            conn.execute("DELETE FROM blocks WHERE book_id = ?", (book_id,))
            conn.executemany(
                """
                INSERT INTO blocks (book_id, block_index, text, chapter)
                VALUES (?, ?, ?, ?)
                """,
                [
                    (book_id, i, text, chapter)
                    for i, (text, chapter) in enumerate(blocks)
                ],
            )
            conn.execute(
                """
                UPDATE books
                SET total_blocks = ?, current_block = ?, progress_percent = ?
                WHERE id = ?
                """,
                (total, current, progress, book_id),
            )

    def get_today_reading_seconds(self) -> int:
        today = date.today().isoformat()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT seconds FROM daily_stats WHERE date = ?", (today,)
            ).fetchone()
        return int(row["seconds"] or 0) if row else 0

    def get_recent_daily_stats(self, days: int = 7) -> list[dict[str, Any]]:
        start = (date.today() - timedelta(days=days - 1)).isoformat()
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT date, blocks_read, words_read, seconds
                FROM daily_stats
                WHERE date >= ?
                ORDER BY date
                """,
                (start,),
            ).fetchall()
        by_date = {row["date"]: dict(row) for row in rows}
        result: list[dict[str, Any]] = []
        for offset in range(days):
            day = date.today() - timedelta(days=days - 1 - offset)
            key = day.isoformat()
            row = by_date.get(key)
            result.append(
                {
                    "date": key,
                    "blocks": (row["blocks_read"] if row else 0) or 0,
                    "words": (row["words_read"] if row else 0) or 0,
                    "seconds": (row["seconds"] if row else 0) or 0,
                }
            )
        return result

    def get_monthly_stats(self, months: int = 12) -> list[dict[str, Any]]:
        today = date.today()
        keys: list[str] = []
        year, month = today.year, today.month
        for _ in range(months):
            keys.append(f"{year:04d}-{month:02d}")
            month -= 1
            if month == 0:
                month = 12
                year -= 1
        keys.reverse()
        start = f"{keys[0]}-01"
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT substr(date, 1, 7) AS period,
                       SUM(blocks_read) AS blocks,
                       SUM(words_read) AS words,
                       SUM(seconds) AS seconds
                FROM daily_stats
                WHERE date >= ?
                GROUP BY period
                """,
                (start,),
            ).fetchall()
        by_period = {row["period"]: dict(row) for row in rows}
        return [
            {
                "date": key,
                "blocks": int((by_period.get(key) or {}).get("blocks") or 0),
                "words": int((by_period.get(key) or {}).get("words") or 0),
                "seconds": int((by_period.get(key) or {}).get("seconds") or 0),
            }
            for key in keys
        ]

    def get_yearly_stats(self, years: int = 5) -> list[dict[str, Any]]:
        current_year = date.today().year
        keys = [str(current_year - offset) for offset in range(years - 1, -1, -1)]
        start = f"{keys[0]}-01-01"
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT substr(date, 1, 4) AS period,
                       SUM(blocks_read) AS blocks,
                       SUM(words_read) AS words,
                       SUM(seconds) AS seconds
                FROM daily_stats
                WHERE date >= ?
                GROUP BY period
                """,
                (start,),
            ).fetchall()
        by_period = {row["period"]: dict(row) for row in rows}
        return [
            {
                "date": key,
                "blocks": int((by_period.get(key) or {}).get("blocks") or 0),
                "words": int((by_period.get(key) or {}).get("words") or 0),
                "seconds": int((by_period.get(key) or {}).get("seconds") or 0),
            }
            for key in keys
        ]

    def export_stats_csv(self) -> str:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT date, blocks_read, words_read, goal_met, seconds
                FROM daily_stats ORDER BY date
                """
            ).fetchall()
        lines = ["date,blocks,words,seconds,goal_met"]
        for row in rows:
            lines.append(
                f"{row['date']},{row['blocks_read'] or 0},{row['words_read'] or 0},"
                f"{row['seconds'] or 0},{row['goal_met'] or 0}"
            )
        return "\n".join(lines) + "\n"

    def get_today_blocks_read(self) -> int:
        today = date.today().isoformat()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT blocks_read FROM daily_stats WHERE date = ?", (today,)
            ).fetchone()
            return row["blocks_read"] if row and row["blocks_read"] else 0

    def delete_book(self, book_id: int) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM books WHERE id = ?", (book_id,))

    def clear_library_data(self) -> dict[str, int]:
        """Remove all books, blocks, tags, and reading statistics. Keep settings."""
        with self._connect() as conn:
            books = conn.execute("SELECT COUNT(*) AS c FROM books").fetchone()["c"]
            stats_days = conn.execute(
                "SELECT COUNT(*) AS c FROM daily_stats"
            ).fetchone()["c"]
            conn.execute("DELETE FROM books")
            conn.execute("DELETE FROM daily_stats")
        return {"books": books, "stats_days": stats_days}

    def is_goal_met_today(self) -> bool:
        from .reading_stats import is_daily_goal_met

        today = date.today().isoformat()
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT blocks_read, seconds FROM daily_stats WHERE date = ?
                """,
                (today,),
            ).fetchone()
        if not row:
            return False
        return is_daily_goal_met(
            row["blocks_read"] or 0,
            row["seconds"] or 0,
            self.get_daily_goal_settings(),
        )

    def get_day_stats(self, day_date: str) -> dict[str, int | str | bool] | None:
        from .reading_stats import parse_daily_goal_settings

        goal_settings = self.get_daily_goal_settings()
        goal = parse_daily_goal_settings(goal_settings)
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT blocks_read, words_read, seconds
                FROM daily_stats WHERE date = ?
                """,
                (day_date,),
            ).fetchone()
        if not row:
            return None
        blocks = row["blocks_read"] or 0
        words = row["words_read"] or 0
        seconds = row["seconds"] or 0
        if blocks == 0 and words == 0 and seconds == 0:
            return None
        if goal["type"] == "time":
            goal_met = seconds >= int(goal["minutes"]) * 60
        else:
            goal_met = blocks >= int(goal["blocks"])
        return {
            "blocks": blocks,
            "words": words,
            "seconds": seconds,
            "goal_met": goal_met,
            "goal_type": str(goal["type"]),
            "goal_blocks": int(goal["blocks"]),
            "goal_minutes": int(goal["minutes"]),
        }

    def get_calendar_month(self, year: int, month: int) -> dict[str, dict[str, int | str]]:
        """Per-day stats for a month, colored by the active daily goal type."""
        from .reading_stats import day_reading_status

        prefix = f"{year:04d}-{month:02d}"
        goal_settings = self.get_daily_goal_settings()
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT date, blocks_read, words_read, seconds FROM daily_stats
                WHERE date LIKE ?
                """,
                (f"{prefix}%",),
            ).fetchall()
        result: dict[str, dict[str, int | str]] = {}
        for row in rows:
            day = int(row["date"].split("-")[2])
            blocks = row["blocks_read"] or 0
            words = row["words_read"] or 0
            seconds = row["seconds"] or 0
            if blocks == 0 and words == 0 and seconds == 0:
                continue
            status = day_reading_status(
                blocks,
                0,
                seconds=seconds,
                settings=goal_settings,
            )
            result[str(day)] = {
                "blocks": blocks,
                "words": words,
                "seconds": seconds,
                "status": status,
            }
        return result

    def get_calendar_data(self, year: int, month: int) -> dict[str, str]:
        month_data = self.get_calendar_month(year, month)
        return {
            day: str(info["status"])
            for day, info in month_data.items()
        }

    def get_statistics(self) -> dict[str, Any]:
        with self._connect() as conn:
            total_words = conn.execute(
                "SELECT COALESCE(SUM(words_read), 0) as w FROM daily_stats"
            ).fetchone()["w"]
            total_blocks = conn.execute(
                "SELECT COALESCE(SUM(blocks_read), 0) as b FROM daily_stats"
            ).fetchone()["b"]
            books_completed = conn.execute(
                "SELECT COUNT(*) as c FROM books WHERE progress_percent >= 99.5"
            ).fetchone()["c"]
            books_in_progress = conn.execute(
                "SELECT COUNT(*) as c FROM books WHERE progress_percent > 0 "
                "AND progress_percent < 99.5"
            ).fetchone()["c"]
            streak = self._calculate_streak(conn)
            today_row = conn.execute(
                """
                SELECT blocks_read, words_read, goal_met, seconds
                FROM daily_stats WHERE date = ?
                """,
                (date.today().isoformat(),),
            ).fetchone()
            total_seconds = conn.execute(
                "SELECT COALESCE(SUM(seconds), 0) as s FROM daily_stats"
            ).fetchone()["s"]
        today_blocks = today_row["blocks_read"] if today_row else 0
        today_words = today_row["words_read"] if today_row else 0
        today_seconds = today_row["seconds"] if today_row else 0
        goal_settings = self.get_daily_goal_settings()
        from .reading_stats import is_daily_goal_met, parse_daily_goal_settings

        goal = parse_daily_goal_settings(goal_settings)
        goal_met = is_daily_goal_met(
            today_blocks or 0, today_seconds or 0, goal_settings
        )
        return {
            "total_blocks": total_blocks,
            "total_words": total_words,
            "total_seconds": int(total_seconds or 0),
            "books_completed": books_completed,
            "books_in_progress": books_in_progress,
            "current_streak": streak,
            "today_blocks": today_blocks or 0,
            "today_words": today_words or 0,
            "today_seconds": today_seconds or 0,
            "goal_met_today": goal_met,
            "daily_goal_blocks": int(goal["blocks"]),
            "daily_goal_minutes": int(goal["minutes"]),
            "daily_goal_type": str(goal["type"]),
        }

    def _calculate_streak(self, conn: sqlite3.Connection) -> int:
        from .reading_stats import is_daily_goal_met

        rows = conn.execute(
            """
            SELECT date, blocks_read, seconds FROM daily_stats
            ORDER BY date DESC
            """
        ).fetchall()
        if not rows:
            return 0
        goal_settings = self.get_daily_goal_settings()
        dates_met = {
            row["date"]
            for row in rows
            if is_daily_goal_met(
                row["blocks_read"] or 0,
                row["seconds"] or 0,
                goal_settings,
            )
        }
        streak = 0
        expected = date.today()
        while expected.isoformat() in dates_met:
            streak += 1
            expected = expected - timedelta(days=1)
        return streak

    def export_data(self) -> dict[str, Any]:
        covers = CoverService(self.app_dir)
        with self._connect() as conn:
            books: list[dict[str, Any]] = []
            for row in conn.execute("SELECT * FROM books").fetchall():
                book_id = row["id"]
                stored_cover = row["cover_path"] if "cover_path" in row.keys() else ""
                cover_bytes = covers.read_cover_bytes(book_id, stored_cover or None)
                cover_b64 = (
                    base64.b64encode(cover_bytes).decode("ascii") if cover_bytes else ""
                )
                block_rows = conn.execute(
                    """
                    SELECT block_index, text, chapter FROM blocks
                    WHERE book_id = ? ORDER BY block_index
                    """,
                    (book_id,),
                ).fetchall()
                books.append(
                    {
                        "title": row["title"],
                        "author": row["author"],
                        "file_path": row["file_path"],
                        "format": row["format"],
                        "total_blocks": row["total_blocks"],
                        "current_block": row["current_block"],
                        "progress_percent": row["progress_percent"],
                        "last_read_at": row["last_read_at"],
                        "added_at": row["added_at"],
                        "cover_path": stored_cover,
                        "cover_b64": cover_b64,
                        "tags": self.get_book_tags(book_id),
                        "blocks": [dict(b) for b in block_rows],
                    }
                )
            stats = [
                dict(row)
                for row in conn.execute("SELECT * FROM daily_stats").fetchall()
            ]
        settings = self.get_all_settings()
        for key in BACKUP_STRIPPED_SETTINGS:
            settings.pop(key, None)

        return {
            "version": self.BACKUP_VERSION,
            "exported_at": datetime.now().isoformat(),
            "books": books,
            "daily_stats": stats,
            "settings": settings,
        }

    def import_data(self, data: dict[str, Any], merge: bool = True) -> dict[str, int]:
        counts = {"books": 0, "stats": 0, "books_created": 0}
        covers = CoverService(self.app_dir)

        with self._connect() as conn:
            for stat in data.get("daily_stats", []):
                existing = conn.execute(
                    """
                    SELECT seconds, goal_met, words_read, blocks_read
                    FROM daily_stats WHERE date = ?
                    """,
                    (stat["date"],),
                ).fetchone()
                if existing and merge:
                    conn.execute(
                        """
                        UPDATE daily_stats
                        SET seconds = MAX(seconds, ?),
                            goal_met = MAX(goal_met, ?),
                            words_read = MAX(words_read, ?),
                            blocks_read = MAX(blocks_read, ?)
                        WHERE date = ?
                        """,
                        (
                            stat.get("seconds", 0),
                            stat.get("goal_met", 0),
                            stat.get("words_read", 0),
                            stat.get("blocks_read", 0),
                            stat["date"],
                        ),
                    )
                else:
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO daily_stats
                        (date, seconds, goal_met, words_read, blocks_read)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (
                            stat["date"],
                            stat.get("seconds", 0),
                            stat.get("goal_met", 0),
                            stat.get("words_read", 0),
                            stat.get("blocks_read", 0),
                        ),
                    )
                counts["stats"] += 1

            for book_data in data.get("books", []):
                file_path = book_data.get("file_path", "")
                existing = None
                if file_path:
                    existing = conn.execute(
                        "SELECT id, current_block FROM books WHERE file_path = ?",
                        (file_path,),
                    ).fetchone()
                if not existing:
                    existing = conn.execute(
                        """
                        SELECT id, current_block FROM books
                        WHERE title = ? AND author = ?
                        """,
                        (book_data["title"], book_data.get("author", "")),
                    ).fetchone()

                cover_b64 = book_data.get("cover_b64", "")

                if existing and merge:
                    new_block = max(
                        existing["current_block"],
                        book_data.get("current_block", 0),
                    )
                    conn.execute(
                        """
                        UPDATE books
                        SET current_block = ?,
                            progress_percent = MAX(progress_percent, ?),
                            last_read_at = COALESCE(?, last_read_at)
                        WHERE id = ?
                        """,
                        (
                            new_block,
                            book_data.get("progress_percent", 0),
                            book_data.get("last_read_at"),
                            existing["id"],
                        ),
                    )
                    if cover_b64:
                        cover_path = covers.import_cover_b64(existing["id"], cover_b64)
                        if cover_path:
                            conn.execute(
                                "UPDATE books SET cover_path = ? WHERE id = ?",
                                (cover_path, existing["id"]),
                            )
                    counts["books"] += 1
                elif not existing:
                    blocks = book_data.get("blocks") or []
                    if not blocks:
                        continue
                    now = datetime.now().isoformat()
                    cursor = conn.execute(
                        """
                        INSERT INTO books (
                            title, author, file_path, format, total_blocks,
                            current_block, progress_percent, last_read_at, added_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            book_data["title"],
                            book_data.get("author", ""),
                            file_path or f"backup://{book_data['title']}",
                            book_data.get("format", ".txt"),
                            len(blocks),
                            book_data.get("current_block", 0),
                            book_data.get("progress_percent", 0),
                            book_data.get("last_read_at"),
                            book_data.get("added_at", now),
                        ),
                    )
                    book_id = cursor.lastrowid
                    if cover_b64:
                        cover_path = covers.import_cover_b64(book_id, cover_b64)
                        if cover_path:
                            conn.execute(
                                "UPDATE books SET cover_path = ? WHERE id = ?",
                                (cover_path, book_id),
                            )
                    conn.executemany(
                        """
                        INSERT INTO blocks (book_id, block_index, text, chapter)
                        VALUES (?, ?, ?, ?)
                        """,
                        [
                            (
                                book_id,
                                b.get("block_index", i),
                                b["text"],
                                b.get("chapter", ""),
                            )
                            for i, b in enumerate(blocks)
                        ],
                    )
                    for tag in book_data.get("tags") or []:
                        if str(tag).strip():
                            conn.execute(
                                "INSERT OR IGNORE INTO book_tags (book_id, tag) VALUES (?, ?)",
                                (book_id, str(tag).strip().lower()),
                            )
                    counts["books"] += 1
                    counts["books_created"] += 1

        blocked = BACKUP_STRIPPED_SETTINGS | {"sync_folder"}
        for key, value in data.get("settings", {}).items():
            if key not in blocked:
                self.set_setting(key, str(value))

        return counts

    def _row_to_book(self, row: sqlite3.Row) -> Book:
        keys = row.keys()
        cover = row["cover_path"] if "cover_path" in keys else None
        use_saved = bool(row["use_saved_audio"]) if "use_saved_audio" in keys else True
        return Book(
            id=row["id"],
            title=row["title"],
            author=row["author"] or "",
            file_path=row["file_path"],
            format=row["format"],
            total_blocks=row["total_blocks"],
            current_block=row["current_block"],
            progress_percent=row["progress_percent"],
            last_read_at=row["last_read_at"],
            added_at=row["added_at"],
            cover_path=cover or None,
            use_saved_audio=use_saved,
        )
