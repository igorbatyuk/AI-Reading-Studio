"""Optional OCR for scanned PDFs via Tesseract."""

from __future__ import annotations

import io
import logging
import shutil
from pathlib import Path
from typing import Callable

logger = logging.getLogger(__name__)

# book_language code -> Tesseract language code(s)
TESSERACT_LANG: dict[str, str] = {
    "en": "eng",
    "uk": "ukr",
    "ru": "rus",
    "de": "deu",
    "fr": "fra",
    "es": "spa",
    "pl": "pol",
    "it": "ita",
    "pt": "por",
    "nb": "nor",
    "nl": "nld",
    "sv": "swe",
    "da": "dan",
    "fi": "fin",
    "cs": "ces",
    "ja": "jpn",
    "ko": "kor",
    "zh": "chi_sim",
}

DEFAULT_MAX_PAGES = 40


def is_available() -> bool:
    if shutil.which("tesseract") is None:
        return False
    try:
        import pytesseract  # noqa: F401

        return True
    except ImportError:
        return False


def tesseract_lang(book_language: str) -> str:
    return TESSERACT_LANG.get(book_language, "eng")


def extract_text(
    pdf_path: Path,
    lang: str = "eng",
    max_pages: int = DEFAULT_MAX_PAGES,
    cancelled: Callable[[], bool] | None = None,
    on_progress: Callable[[int, int], None] | None = None,
) -> str:
    import fitz
    import pytesseract
    from PIL import Image

    doc = fitz.open(str(pdf_path))
    total = min(len(doc), max_pages)
    parts: list[str] = []

    try:
        for index in range(total):
            if cancelled and cancelled():
                break
            if on_progress:
                on_progress(index + 1, total)
            page = doc[index]
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            text = pytesseract.image_to_string(img, lang=lang)
            if text.strip():
                parts.append(text)
    finally:
        doc.close()

    return "\n\n".join(parts)
