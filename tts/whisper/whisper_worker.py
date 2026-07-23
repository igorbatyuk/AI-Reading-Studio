"""Whisper word alignment worker (optional venv: tts/whisper/setup.bat)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _transcribe_words(audio_path: Path, lang: str, model_size: str) -> list[dict]:
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise RuntimeError(
            "faster-whisper not installed. Run tts/whisper/setup.bat"
        ) from exc

    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    segments, _info = model.transcribe(
        str(audio_path),
        language=lang or None,
        word_timestamps=True,
        vad_filter=True,
    )
    words: list[dict] = []
    for segment in segments:
        if not segment.words:
            continue
        for word in segment.words:
            token = (word.word or "").strip()
            if not token:
                continue
            words.append(
                {
                    "word": token,
                    "start_ms": int(max(0, word.start * 1000)),
                    "end_ms": int(max(word.start * 1000 + 1, word.end * 1000)),
                }
            )
    return words


def main() -> int:
    parser = argparse.ArgumentParser(description="Whisper word alignment worker")
    parser.add_argument("--audio", required=True, type=Path)
    parser.add_argument("--lang", default="en")
    parser.add_argument("--model", default="tiny")
    args = parser.parse_args()

    if not args.audio.is_file():
        print(json.dumps({"error": f"Audio not found: {args.audio}"}))
        return 1

    try:
        words = _transcribe_words(args.audio, args.lang, args.model)
    except Exception as exc:
        print(json.dumps({"error": str(exc)}))
        return 1

    print(json.dumps({"words": words}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
