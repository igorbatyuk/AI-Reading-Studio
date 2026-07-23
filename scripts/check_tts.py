"""Check offline TTS engine setup."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.database import Database
from src.core import kokoro_tts, offline_tts, piper_tts, styletts2_tts, xtts_tts


def main() -> None:
    db = Database()
    settings = db.get_all_settings()
    app_dir = db.app_dir
    lang = settings.get("book_language", "en")

    print("=== AI Reading Studio — TTS diagnostics ===\n")
    print(f"TTS mode:        {settings.get('tts_mode', 'auto')}")
    print(f"Offline engine:  {settings.get('offline_engine', 'system')}")
    print(f"Online engine:   {settings.get('online_engine', 'edge')}")
    print(f"Voice:           {settings.get('tts_voice', '')}")
    print()

    if settings.get("tts_mode", "auto") == "online":
        print(
            "NOTE: TTS mode is Online - Piper/XTTS/System offline engines are NOT used "
            "for reading. Set Settings -> Audio -> TTS mode -> Offline (or Auto).\n"
        )

    checks = [
        (
            "System (pyttsx3)",
            offline_tts.is_available(),
            "pip install pyttsx3",
        ),
        (
            "Piper",
            piper_tts.is_available(
                lang, settings.get("piper_model_path", ""), app_dir
            ),
            "Run tts/piper/setup.bat; add .onnx models to tts/piper/",
        ),
        (
            "Kokoro worker",
            kokoro_tts.is_available(app_dir),
            "Run tts/kokoro/setup.bat; add models to tts/kokoro/models/",
        ),
        (
            "XTTS worker",
            xtts_tts.is_available(app_dir),
            "Run tts/xtts/setup.bat; add .wav to tts/xtts/speakers/",
        ),
        (
            "StyleTTS2",
            styletts2_tts.is_available(
                app_dir, settings.get("styletts2_model_path", "")
            ),
            "Install styletts2 CLI + .pth models (see README)",
        ),
    ]

    for name, ok, fix in checks:
        status = "OK" if ok else "NOT READY"
        print(f"[{status:9}] {name}")
        if not ok:
            print(f"           -> {fix}")
    print()
    print(f"Piper binary:  {piper_tts.find_piper_binary() or '(missing)'}")
    print(f"Piper model:   {piper_tts.resolve_model(lang, settings.get('piper_model_path', ''), app_dir)}")
    print(f"XTTS speakers: {xtts_tts.speaker_directories(app_dir) or '(none)'}")
    print(f"Kokoro worker: {kokoro_tts.find_kokoro_python() or '(missing)'}")
    print(f"Kokoro script: {kokoro_tts.find_kokoro_worker() or '(missing)'}")
    print(f"Kokoro models: {kokoro_tts.resolve_model_dir(app_dir) or '(missing)'}")
    print(f"Kokoro CLI:    {kokoro_tts.find_kokoro_binary() or '(missing)'}")


if __name__ == "__main__":
    main()
