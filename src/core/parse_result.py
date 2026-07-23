"""Book parsing result with optional quality warnings."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ParseResult:
    title: str
    author: str
    blocks: list[tuple[str, str]]
    file_suffix: str = ""
    warnings: list[str] = field(default_factory=list)
    cover_bytes: bytes | None = None
