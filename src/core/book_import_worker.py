"""Background book import worker."""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal

from .book_parser import BookParser

logger = logging.getLogger(__name__)

MAX_IMPORT_BYTES = 80 * 1024 * 1024  # 80 MB


class BookImportWorker(QObject):
    finished = Signal(object, str)  # ParseResult, file_path
    failed = Signal(str)
    status = Signal(str)

    def __init__(
        self,
        file_path: str,
        block_words_target: int = 55,
        pdf_ocr_mode: str = "auto",
        ocr_language: str = "en",
        ocr_max_pages: int = 40,
    ) -> None:
        super().__init__()
        self.file_path = file_path
        self._parser = BookParser(
            block_words_target,
            pdf_ocr_mode=pdf_ocr_mode,
            ocr_language=ocr_language,
            ocr_max_pages=ocr_max_pages,
            cancel_check=lambda: self._cancelled,
            progress_callback=self.status.emit,
        )
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        try:
            path = Path(self.file_path)
            if not path.exists():
                self.failed.emit(f"File not found: {self.file_path}")
                return

            size = path.stat().st_size
            if size > MAX_IMPORT_BYTES:
                mb = size / (1024 * 1024)
                self.failed.emit(
                    f"File too large ({mb:.0f} MB). Maximum is {MAX_IMPORT_BYTES // (1024 * 1024)} MB."
                )
                return

            if self._cancelled:
                return

            self.status.emit("reading")
            result = self._parser.parse(self.file_path)

            if self._cancelled:
                return

            if not result.blocks:
                self.failed.emit("empty")
                return

            self.status.emit(f"blocks:{len(result.blocks)}")
            self.finished.emit(result, self.file_path)
        except Exception as e:
            logger.exception("Book import failed for %s", self.file_path)
            if not self._cancelled:
                self.failed.emit(str(e))


class BookImportThread(QThread):
    def __init__(
        self,
        file_path: str,
        block_words_target: int = 55,
        pdf_ocr_mode: str = "auto",
        ocr_language: str = "en",
        ocr_max_pages: int = 40,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._worker = BookImportWorker(
            file_path,
            block_words_target,
            pdf_ocr_mode,
            ocr_language,
            ocr_max_pages,
        )
        self._worker.moveToThread(self)

    @property
    def worker(self) -> BookImportWorker:
        return self._worker

    def start_import(self) -> BookImportWorker:
        self.started.connect(self._worker.run)
        self._worker.finished.connect(self.quit)
        self._worker.failed.connect(self.quit)
        self.start()
        return self._worker
