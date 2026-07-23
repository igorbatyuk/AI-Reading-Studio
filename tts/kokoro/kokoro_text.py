"""Text cleanup and chunking for Kokoro TTS (shared by worker and app)."""

from __future__ import annotations

import re

MAX_CHUNK_CHARS = 380

_SENTENCE_END = re.compile(r"(?<=[.!?…])\s+")

_REPLACEMENTS = {
    "\u200b": "",
    "\ufeff": "",
    "\u00ad": "",
    "\u2018": "'",
    "\u2019": "'",
    "\u201c": '"',
    "\u201d": '"',
    "\u2013": "-",
    "\u2014": "-",
    "\u2026": "...",
    "\u00a0": " ",
}


def prepare_text_for_kokoro(text: str) -> str:
    """Normalize book text so Kokoro/espeak handle it reliably."""
    text = text.replace("\r\n", " ").replace("\n", " ").replace("\r", " ")
    for old, new in _REPLACEMENTS.items():
        text = text.replace(old, new)
    text = re.sub(r"[*_#<>|{}\[\]\\/`~^]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def split_text_for_kokoro(text: str, max_chars: int = MAX_CHUNK_CHARS) -> list[str]:
    """Split long passages at sentence/word boundaries."""
    text = prepare_text_for_kokoro(text)
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]

    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for sentence in _SENTENCE_END.split(text):
        sentence = sentence.strip()
        if not sentence:
            continue

        part_len = len(sentence) + (1 if current else 0)
        if len(sentence) > max_chars:
            if current:
                chunks.append(" ".join(current))
                current = []
                current_len = 0
            chunks.extend(_split_by_words(sentence, max_chars))
            continue

        if current_len + part_len > max_chars and current:
            chunks.append(" ".join(current))
            current = [sentence]
            current_len = len(sentence)
        else:
            current.append(sentence)
            current_len += part_len

    if current:
        chunks.append(" ".join(current))
    return [chunk for chunk in chunks if chunk.strip()]


def _split_by_words(text: str, max_chars: int) -> list[str]:
    pieces: list[str] = []
    current: list[str] = []
    current_len = 0

    for word in text.split():
        word_len = len(word) + (1 if current else 0)
        if current_len + word_len > max_chars and current:
            pieces.append(" ".join(current))
            current = [word]
            current_len = len(word)
        else:
            current.append(word)
            current_len += word_len

    if current:
        pieces.append(" ".join(current))
    return pieces
