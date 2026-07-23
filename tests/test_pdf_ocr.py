"""Tests for PDF OCR helpers."""

from src.core.pdf_ocr import tesseract_lang


def test_tesseract_lang():
    assert tesseract_lang("en") == "eng"
    assert tesseract_lang("uk") == "ukr"
    assert tesseract_lang("xx") == "eng"
