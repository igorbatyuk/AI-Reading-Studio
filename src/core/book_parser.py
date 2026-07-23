"""Parse EPUB, TXT, and PDF books into text blocks."""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path

from .parse_result import ParseResult
from .text_splitter import TextSplitter

logger = logging.getLogger(__name__)

MIN_PDF_WORDS = 40
MIN_SECTION_WORDS = 8
GARBAGE_RATIO = 0.35


class BookParser:
    def __init__(
        self,
        block_words_target: int = 55,
        pdf_ocr_mode: str = "auto",
        ocr_language: str = "en",
        ocr_max_pages: int = 40,
        cancel_check: Callable[[], bool] | None = None,
        progress_callback: Callable[[str], None] | None = None,
    ) -> None:
        self.splitter = TextSplitter(block_words_target)
        self.pdf_ocr_mode = pdf_ocr_mode
        self.ocr_language = ocr_language
        self.ocr_max_pages = ocr_max_pages
        self._cancel_check = cancel_check
        self._progress = progress_callback

    def parse(self, file_path: str) -> ParseResult:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        ext = path.suffix.lower()
        if ext == ".epub":
            return self._parse_epub(path)
        if ext == ".txt":
            return self._parse_txt(path)
        if ext == ".pdf":
            return self._parse_pdf(path)
        raise ValueError(f"Unsupported format: {ext}")

    def _parse_epub(self, path: Path) -> ParseResult:
        import ebooklib
        from ebooklib import epub
        from bs4 import BeautifulSoup

        book = epub.read_epub(str(path))
        title = book.get_metadata("DC", "title")
        author = book.get_metadata("DC", "creator")
        book_title = title[0][0] if title else path.stem
        book_author = author[0][0] if author else ""
        cover_bytes = self._extract_epub_cover(book)

        all_blocks: list[tuple[str, str]] = []
        for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
            name = (item.get_name() or "").lower()
            if any(part in name for part in ("nav", "toc", "cover")):
                continue
            soup = BeautifulSoup(item.get_content(), "lxml")
            for tag in soup(["script", "style", "nav"]):
                tag.decompose()
            text = soup.get_text(separator="\n")
            if len(text.split()) < MIN_SECTION_WORDS:
                continue
            chapter = ""
            h = soup.find(["h1", "h2", "h3"])
            if h:
                chapter = h.get_text(strip=True)
            blocks = self.splitter.split_into_blocks(text, chapter)
            all_blocks.extend(blocks)

        warnings = self._quality_warnings(all_blocks, path.suffix)
        return ParseResult(
            book_title, book_author, all_blocks, path.suffix, warnings, cover_bytes
        )

    @staticmethod
    def _extract_epub_cover(book) -> bytes | None:
        import ebooklib

        for item in book.get_items():
            if item.get_type() == ebooklib.ITEM_COVER:
                data = item.get_content()
                if data:
                    return data
        for item in book.get_items_of_type(ebooklib.ITEM_IMAGE):
            name = (item.get_name() or "").lower()
            if "cover" in name:
                data = item.get_content()
                if data:
                    return data
        return None

    def _parse_txt(self, path: Path) -> ParseResult:
        for encoding in ("utf-8", "utf-8-sig", "latin-1", "cp1252"):
            try:
                text = path.read_text(encoding=encoding)
                break
            except UnicodeDecodeError:
                continue
        else:
            text = path.read_text(encoding="utf-8", errors="replace")

        blocks = self.splitter.split_into_blocks(text)
        warnings = self._quality_warnings(blocks, path.suffix)
        return ParseResult(path.stem, "", blocks, path.suffix, warnings)

    def _parse_pdf(self, path: Path) -> ParseResult:
        import fitz

        doc = fitz.open(str(path))
        title = doc.metadata.get("title") or path.stem
        author = doc.metadata.get("author") or ""

        full_text_parts: list[str] = []
        for page in doc:
            full_text_parts.append(page.get_text())
        doc.close()

        raw = "\n\n".join(full_text_parts)
        word_count = len(raw.split())
        used_ocr = False

        need_ocr = self.pdf_ocr_mode == "always" or (
            self.pdf_ocr_mode == "auto" and word_count < MIN_PDF_WORDS
        )

        if need_ocr:
            ocr_text = self._try_ocr(path)
            if ocr_text and len(ocr_text.split()) > word_count:
                raw = ocr_text
                word_count = len(raw.split())
                used_ocr = True

        blocks = self.splitter.split_into_blocks(raw)
        warnings = self._quality_warnings(blocks, path.suffix)

        if used_ocr:
            warnings.append("pdf_ocr_used")
        elif word_count < MIN_PDF_WORDS:
            warnings.append("pdf_scanned")
        elif self._looks_garbled(raw):
            warnings.append("pdf_garbled")

        return ParseResult(title, author, blocks, path.suffix, warnings)

    def _try_ocr(self, path: Path) -> str:
        from . import pdf_ocr

        if not pdf_ocr.is_available():
            logger.warning("OCR requested but Tesseract/pytesseract unavailable")
            return ""

        lang = pdf_ocr.tesseract_lang(self.ocr_language)

        def on_page(current: int, total: int) -> None:
            if self._progress:
                self._progress(f"ocr:{current}:{total}")

        try:
            return pdf_ocr.extract_text(
                path,
                lang=lang,
                max_pages=self.ocr_max_pages,
                cancelled=self._cancel_check,
                on_progress=on_page,
            )
        except Exception as exc:
            logger.exception("PDF OCR failed: %s", exc)
            return ""

    @staticmethod
    def _looks_garbled(text: str) -> bool:
        if not text.strip():
            return True
        chars = [c for c in text if not c.isspace()]
        if not chars:
            return True
        weird = sum(
            1 for c in chars if not c.isalnum() and c not in ".,!?;:'\"()-—…"
        )
        return weird / len(chars) > GARBAGE_RATIO

    @staticmethod
    def _quality_warnings(
        blocks: list[tuple[str, str]], suffix: str
    ) -> list[str]:
        warnings: list[str] = []
        if not blocks:
            warnings.append("empty")
            return warnings
        total_words = sum(len(b[0].split()) for b in blocks)
        if total_words < 30:
            warnings.append("very_short")
        if suffix == ".pdf" and total_words < 200:
            warnings.append("pdf_low_text")
        return warnings

    @staticmethod
    def supported_extensions() -> list[str]:
        return [".epub", ".txt", ".pdf"]

    @staticmethod
    def warning_message(code: str) -> str:
        from .i18n import tr

        return tr(f"warn.{code}")
