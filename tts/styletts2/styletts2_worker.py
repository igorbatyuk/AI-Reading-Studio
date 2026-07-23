"""StyleTTS2 TTS worker — run under Python 3.10 venv."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="StyleTTS2 worker for AI Reading Studio")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--model", required=True, type=Path)
    parser.add_argument("--speed", type=float, default=1.0)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--text")
    group.add_argument("--text-file", type=Path)
    return parser.parse_args()


def resolve_config(model_path: Path) -> Path:
    candidates = (
        model_path.with_name("config.yml"),
        model_path.parent / "config.yml",
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise SystemExit(f"config.yml not found next to {model_path}")


def main() -> int:
    args = parse_args()
    if args.text is not None:
        text = args.text.strip()
    else:
        text = args.text_file.read_text(encoding="utf-8").strip()
    if not text:
        print("Empty text", file=sys.stderr)
        return 1

    model_path = args.model
    if not model_path.is_file():
        print(f"Model not found: {model_path}", file=sys.stderr)
        return 1

    config_path = resolve_config(model_path)
    args.output.parent.mkdir(parents=True, exist_ok=True)

    try:
        from styletts2 import tts
    except ImportError as exc:
        print(
            "styletts2 package not installed. Run tts/styletts2/setup.bat",
            file=sys.stderr,
        )
        return 1

    try:
        engine = tts.StyleTTS2(
            model_checkpoint_path=str(model_path),
            config_path=str(config_path),
        )
        engine.inference(text, output_wav_file=str(args.output))
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        args.output.unlink(missing_ok=True)
        return 1

    if not args.output.exists() or args.output.stat().st_size == 0:
        print("StyleTTS2 produced no audio", file=sys.stderr)
        args.output.unlink(missing_ok=True)
        return 1

    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
