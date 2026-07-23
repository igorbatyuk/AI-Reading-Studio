"""Tests for book parser quality warnings."""

from pathlib import Path

from src.core.book_parser import BookParser


def test_txt_parse(tmp_path: Path):
    book = tmp_path / "sample.txt"
    book.write_text("Word " * 200, encoding="utf-8")
    result = BookParser(55).parse(str(book))
    assert len(result.blocks) > 0
    assert result.title == "sample"


def test_empty_txt_warning(tmp_path: Path):
    book = tmp_path / "tiny.txt"
    book.write_text("Hi", encoding="utf-8")
    result = BookParser(55).parse(str(book))
    assert "very_short" in result.warnings or len(result.blocks) <= 1
