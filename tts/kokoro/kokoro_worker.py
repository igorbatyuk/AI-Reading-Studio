#!/usr/bin/env python3
"""Kokoro TTS worker — run under Python 3.11–3.12 (not the main app interpreter)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import soundfile as sf
from kokoro_onnx import Kokoro

from kokoro_text import prepare_text_for_kokoro, split_text_for_kokoro

MODEL_ONNX = "kokoro-v1.0.onnx"
MODEL_VOICES = "voices-v1.0.bin"
MIN_SPLIT_CHARS = 24


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Kokoro TTS worker for AI Reading Studio")
    parser.add_argument("--output", required=True, type=Path, help="Output .wav path")
    parser.add_argument("--voice", default="af_heart")
    parser.add_argument("--lang", default="en-us")
    parser.add_argument("--speed", type=float, default=1.0)
    parser.add_argument(
        "--models-dir",
        required=True,
        type=Path,
        help=f"Directory with {MODEL_ONNX} and {MODEL_VOICES}",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--text", help="Text to synthesize")
    group.add_argument("--text-file", type=Path, help="UTF-8 text file")
    return parser.parse_args()


def ensure_models(models_dir: Path) -> tuple[Path, Path]:
    model_path = models_dir / MODEL_ONNX
    voices_path = models_dir / MODEL_VOICES
    if not model_path.exists() or not voices_path.exists():
        raise SystemExit(
            f"Missing Kokoro models in {models_dir}. "
            f"Download {MODEL_ONNX} and {MODEL_VOICES} into that folder."
        )
    return model_path, voices_path


def _is_phoneme_overflow(exc: Exception) -> bool:
    msg = str(exc).lower()
    return (
        "510" in msg
        or "phoneme" in msg
        or "out of bounds" in msg
        or "too long" in msg
    )


def _split_near_middle(text: str) -> tuple[str, str]:
    text = text.strip()
    if len(text) <= MIN_SPLIT_CHARS:
        return text, ""

    mid = len(text) // 2
    split_at = text.rfind(" ", max(0, mid - 40), min(len(text), mid + 40))
    if split_at <= 0:
        split_at = mid
    left = text[:split_at].strip()
    right = text[split_at:].strip()
    if not left or not right:
        split_at = mid
        left = text[:split_at].strip()
        right = text[split_at:].strip()
    return left, right


def _create_samples(
    kokoro: Kokoro,
    chunk: str,
    *,
    voice: str,
    lang: str,
    speed: float,
) -> tuple[np.ndarray, int]:
    samples, rate = kokoro.create(
        chunk,
        voice=voice,
        speed=speed,
        lang=lang,
    )
    if samples is None or len(samples) == 0:
        raise RuntimeError("Kokoro returned no audio")
    return samples, rate


def synthesize_chunk(
    kokoro: Kokoro,
    chunk: str,
    *,
    voice: str,
    lang: str,
    speed: float,
    depth: int = 0,
) -> tuple[np.ndarray, int]:
    chunk = chunk.strip()
    if not chunk:
        raise RuntimeError("Empty chunk")

    try:
        return _create_samples(kokoro, chunk, voice=voice, lang=lang, speed=speed)
    except Exception as exc:
        if depth >= 4 or len(chunk) <= MIN_SPLIT_CHARS or not _is_phoneme_overflow(exc):
            raise RuntimeError(
                f"Kokoro failed on {len(chunk)}-char segment: {exc}"
            ) from exc

        left, right = _split_near_middle(chunk)
        if not left or not right:
            raise RuntimeError(
                f"Kokoro failed on {len(chunk)}-char segment: {exc}"
            ) from exc

        left_samples, rate = synthesize_chunk(
            kokoro,
            left,
            voice=voice,
            lang=lang,
            speed=speed,
            depth=depth + 1,
        )
        right_samples, right_rate = synthesize_chunk(
            kokoro,
            right,
            voice=voice,
            lang=lang,
            speed=speed,
            depth=depth + 1,
        )
        if right_rate != rate:
            raise RuntimeError("Kokoro sample rate mismatch between split parts")
        return np.concatenate([left_samples, right_samples]), rate


def synthesize_text(
    kokoro: Kokoro,
    text: str,
    *,
    voice: str,
    lang: str,
    speed: float,
) -> tuple[np.ndarray, int]:
    chunks = split_text_for_kokoro(text)
    if not chunks:
        raise RuntimeError("Empty text after cleanup")

    all_samples: list[np.ndarray] = []
    sample_rate: int | None = None

    for index, chunk in enumerate(chunks, start=1):
        try:
            samples, rate = synthesize_chunk(
                kokoro,
                chunk,
                voice=voice,
                lang=lang,
                speed=speed,
            )
        except Exception as exc:
            raise RuntimeError(
                f"Kokoro failed on segment {index}/{len(chunks)} "
                f"({len(chunk)} chars): {exc}"
            ) from exc

        all_samples.append(samples)
        sample_rate = rate

    if sample_rate is None or not all_samples:
        raise RuntimeError("Kokoro produced no audio")

    return np.concatenate(all_samples), sample_rate


def main() -> int:
    args = parse_args()
    model_path, voices_path = ensure_models(args.models_dir)

    if args.text is not None:
        text = args.text
    else:
        text = args.text_file.read_text(encoding="utf-8")

    text = prepare_text_for_kokoro(text)
    if not text:
        print("Empty text", file=sys.stderr)
        return 1

    speed_value = max(0.5, min(2.0, float(args.speed)))
    args.output.parent.mkdir(parents=True, exist_ok=True)

    try:
        kokoro = Kokoro(str(model_path), str(voices_path))
        samples, sample_rate = synthesize_text(
            kokoro,
            text,
            voice=args.voice or "af_heart",
            lang=args.lang,
            speed=speed_value,
        )
        sf.write(str(args.output), samples, sample_rate)
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        args.output.unlink(missing_ok=True)
        return 1

    if not args.output.exists() or args.output.stat().st_size == 0:
        print("Kokoro produced no audio", file=sys.stderr)
        args.output.unlink(missing_ok=True)
        return 1

    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
