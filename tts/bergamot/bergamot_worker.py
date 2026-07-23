#!/usr/bin/env python3
"""Bergamot offline translation worker (Python 3.10 venv)."""

from __future__ import annotations

import argparse
import json
import sys


def model_code(source: str, target: str) -> str:
    return f"{source[:2]}{target[:2]}".lower()


def _translate(text: str, source: str, target: str) -> str:
    import bergamot

    code = model_code(source, target)
    bergamot.REPOSITORY.update()
    models = bergamot.REPOSITORY.models()
    if code not in models:
        raise RuntimeError(
            f"Model '{code}' not installed. Run: bergamot download -m {code}"
        )

    config_path = bergamot.REPOSITORY.modelConfigPath(code)
    service = bergamot.Service(bergamot.ServiceConfig(numWorkers=1))
    model = service.modelFromConfigPath(config_path)
    options = bergamot.ResponseOptions(
        alignment=False,
        qualityScores=False,
        HTML=False,
    )
    batch = bergamot.VectorString([text])
    responses = service.translate(model, batch, options)
    if not responses:
        raise RuntimeError("Bergamot returned no translation")
    result = (responses[0].target.text or "").strip()
    if not result:
        raise RuntimeError("Bergamot returned empty translation")
    return result


def _list_models() -> list[str]:
    import bergamot

    bergamot.REPOSITORY.update()
    return list(bergamot.REPOSITORY.models())


def main() -> int:
    parser = argparse.ArgumentParser(description="Bergamot worker for AI Reading Studio")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("ping", help="Check bergamot import")

    sub.add_parser("list-models", help="List downloaded model codes")

    translate_p = sub.add_parser("translate", help="Translate one text")
    translate_p.add_argument("--source", required=True)
    translate_p.add_argument("--target", required=True)
    translate_p.add_argument("--text", required=True)

    args = parser.parse_args()

    try:
        if args.command == "ping":
            import bergamot  # noqa: F401

            print(json.dumps({"ok": True}))
            return 0

        if args.command == "list-models":
            print(json.dumps({"models": _list_models()}))
            return 0

        if args.command == "translate":
            text = _translate(args.text, args.source, args.target)
            print(json.dumps({"text": text}))
            return 0
    except Exception as exc:
        print(json.dumps({"error": str(exc)}))
        return 1

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
