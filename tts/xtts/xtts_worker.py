#!/usr/bin/env python3
"""XTTS v2 worker — run under Python 3.9–3.11 (Coqui TTS, not the main app)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

DEFAULT_MODEL = "tts_models/multilingual/multi-dataset/xtts_v2"
DEFAULT_SPEAKER = "default"

LANG_MAP = {
    "en": "en",
    "uk": "uk",
    "ru": "ru",
    "de": "de",
    "fr": "fr",
    "es": "es",
    "it": "it",
    "pt": "pt",
    "pl": "pl",
    "nl": "nl",
    "ja": "ja",
    "zh": "zh-cn",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="XTTS v2 worker for AI Reading Studio")
    parser.add_argument("--output", required=True, type=Path, help="Output .wav path")
    parser.add_argument("--voice", default=DEFAULT_SPEAKER)
    parser.add_argument("--lang", default="en")
    parser.add_argument("--speed", type=float, default=1.0)
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help="Coqui TTS model name",
    )
    parser.add_argument(
        "--speakers-dir",
        action="append",
        type=Path,
        default=[],
        help="Folder with reference speaker .wav files (repeatable)",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--text", help="Text to synthesize")
    group.add_argument("--text-file", type=Path, help="UTF-8 text file")
    return parser.parse_args()


def iter_speaker_dirs(dirs: list[Path]) -> list[Path]:
    seen: set[Path] = set()
    ordered: list[Path] = []
    for folder in dirs:
        folder = folder.expanduser().resolve()
        if folder in seen or not folder.is_dir():
            continue
        seen.add(folder)
        ordered.append(folder)
    return ordered


def resolve_speaker_wav(voice: str, speaker_dirs: list[Path]) -> Path:
    folders = iter_speaker_dirs(speaker_dirs)
    if not folders:
        raise SystemExit(
            "No speakers directory provided. Add .wav files to tts/xtts/speakers/ "
            "or ~/.ai_reading_studio/xtts_speakers/"
        )

    if voice and voice != DEFAULT_SPEAKER:
        for folder in folders:
            candidate = folder / f"{voice}.wav"
            if candidate.is_file():
                return candidate

    for folder in folders:
        wavs = sorted(folder.glob("*.wav"))
        if wavs:
            return wavs[0]

    raise SystemExit(
        "No XTTS speaker .wav found. Add reference audio (e.g. my_voice.wav) "
        "to tts/xtts/speakers/ or ~/.ai_reading_studio/xtts_speakers/"
    )


def main() -> int:
    args = parse_args()

    if args.text is not None:
        text = args.text.strip()
    else:
        text = args.text_file.read_text(encoding="utf-8").strip()

    if not text:
        print("Empty text", file=sys.stderr)
        return 1

    speaker_wav = resolve_speaker_wav(args.voice, args.speakers_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)

    try:
        from TTS.api import TTS
    except ImportError:
        print(
            "Coqui TTS not installed in this venv. Run tts/xtts/setup.bat",
            file=sys.stderr,
        )
        return 1

    speed_value = max(0.5, min(2.0, float(args.speed)))
    language = LANG_MAP.get(args.lang, args.lang or "en")

    try:
        tts = TTS(args.model or DEFAULT_MODEL, gpu=False)
        tts.tts_to_file(
            text=text,
            speaker_wav=str(speaker_wav),
            language=language,
            file_path=str(args.output),
            speed=speed_value,
        )
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        args.output.unlink(missing_ok=True)
        return 1

    if not args.output.exists() or args.output.stat().st_size == 0:
        print("XTTS produced no audio", file=sys.stderr)
        args.output.unlink(missing_ok=True)
        return 1

    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
