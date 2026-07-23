"""Tests for TextSplitter."""

from src.core.text_splitter import TextSplitter


def test_merge_orphan_words():
    splitter = TextSplitter(55)
    text = "Hello\n\nWorld\n\nThis is a longer paragraph with enough words to make a proper block for reading aloud in the application."
    blocks = splitter.split_into_blocks(text)
    assert len(blocks) >= 2
    assert len(blocks[0][0].split()) >= 2


def test_hyphen_line_break():
    splitter = TextSplitter(55)
    text = "Some-\nthing happened. Then every-\nthing was fine again and people continued reading their books without any trouble at all."
    blocks = splitter.split_into_blocks(text)
    assert "Something" in blocks[0][0]
    assert "everything" in blocks[0][0]


def test_no_single_word_blocks():
    splitter = TextSplitter(55)
    text = (
        "The sun rose. "
        "Birds sang loudly in the trees while people walked slowly through the park. "
        "It was a beautiful morning."
    )
    blocks = splitter.split_into_blocks(text)
    for block_text, _ in blocks:
        assert len(block_text.split()) >= 5
