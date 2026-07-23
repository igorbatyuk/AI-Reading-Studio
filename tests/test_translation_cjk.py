"""Tests for CJK / Thai / Hangul word tokenization."""

from src.core.translation_service import (
    clean_lookup_word,
    extract_lookup_words,
    is_lookup_word,
)


def test_extract_lookup_words_japanese():
    text = "日本語のテストです。"
    words = extract_lookup_words(text)
    assert words == ["日本語のテストです"]
    assert len(words) == 1


def test_extract_lookup_words_chinese():
    text = "这是中文测试。"
    words = extract_lookup_words(text)
    assert words == ["这是中文测试"]


def test_extract_lookup_words_korean():
    text = "안녕하세요 세계"
    words = extract_lookup_words(text)
    assert "안녕하세요" in words
    assert "세계" in words


def test_extract_lookup_words_thai():
    text = "สวัสดีครับ"
    words = extract_lookup_words(text)
    assert words == ["สวัสดีครับ"]


def test_clean_lookup_word_preserves_cjk():
    assert clean_lookup_word("日本語") == "日本語"
    assert clean_lookup_word("안녕") == "안녕"


def test_is_lookup_word_single_cjk_char():
    assert is_lookup_word("字") is True


def test_mixed_latin_and_cjk():
    text = "Hello 世界 world"
    words = extract_lookup_words(text)
    assert "hello" in words
    assert "世界" in words
    assert "world" in words
