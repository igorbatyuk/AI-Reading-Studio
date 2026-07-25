# AI Reading Studio

Local desktop app for reading books with synchronized text-to-speech (Windows / macOS / Linux).

**Version:** 1.2.0 · **Tests:** 319 passed · **61 test files**  
**Docs:** [docs/USER_GUIDE.md](docs/USER_GUIDE.md) · [docs/PROJECT_ANALYSIS.md](docs/PROJECT_ANALYSIS.md)

---

## Features

### Books & reading

- **Formats:** EPUB, TXT, PDF (OCR for scans via Tesseract — Settings → Reading)
- **Blocks:** 35–280 words, jump to block, focus mode, line width up to 3600 px
- **Audio:** pause, restart, −5 s, **playback speed** 1×–2× (accelerate only; separate from **speech rate** in Settings)
- **Word highlight:** gradient (default), karaoke, liquid, marker, aurora + color palettes
- **Whisper alignment** (optional) — exact timestamps for offline Piper/Kokoro/XTTS (best for EN)
- **Block translation** · **word click** (popup + ▶ pronunciation) · **text selection**
- **Processing status** — Status button in the status bar: TTS engine, block, cache, translation, **generation queue** (cancel)

### Book audio (🎧)

- Dedicated sidebar page: progress, block list, **generate all**, cancel
- **Use saved audio when reading** — toggle without deleting files
- Queue also visible in the **Status** panel

### Text-to-speech (TTS)

| Mode | Engines |
|------|---------|
| **Online** | Edge (free), Azure Speech, Google Cloud TTS, ElevenLabs, Cartesia, Murf |
| **Offline** | System (pyttsx3), **Piper**, **Kokoro**, **XTTS v2**, **StyleTTS2** |
| **Auto** | Edge → Azure → Google → ElevenLabs → Cartesia → Murf → offline |

- Voices **sorted for book reading**; **Female / Male** labels (localized in UI)
- **Settings → Voice preferences:** preset (Audiobook / News / Fast / Custom), gender, EN region, hide unsuitable, drag-and-drop order per engine
- **Speech rate** — combo shows only the **current engine’s** allowed range (Kokoro/Edge from 0.5×; Cartesia up to 1.5×)
- **Separate word TTS profile** (e.g. Edge for words + ElevenLabs for blocks)
- Preview voice in Settings → Audio
- On-disk audio cache — instant replay
- **Playback sync** — pause/play race protection (Kokoro), engine offsets for highlight
- **Kokoro FIFO queue** — generation queue instead of global lock

### Translation

Separate engine for **block**, **word click**, and **selection**:

- **Apify**, **Google Cloud**, **DeepL**, **OpenAI**, **Bergamot**, **Ollama**, **free** (Google/Lingva/MyMemory)
- **Auto chain:** OpenAI → Apify → Google → DeepL → Bergamot → Ollama → free
- **Human-readable errors** — Apify 402 (memory limit), quotas, network, Piper/Kokoro (`humanize_error`)
- Usage counters with **color meters** (green / yellow / red) — Settings → API

| Service | Approx. limit (local counter) |
|---------|-------------------------------|
| Apify translate | ~500k chars/month |
| ElevenLabs TTS | ~10k credits/month |
| Cartesia TTS | ~20k credits/month |
| Murf TTS | ~100k chars trial |
| Azure / Google TTS | local hard cap (~500k chars/month est.) |

### Statistics & goals

- Blocks, words, **reading time** (active playback only)
- **Daily goal:** blocks **or** time (5 min … 8 h)
- Calendar, charts 7 days / 12 months / 5 years, CSV export

### Other

- **Library:** covers, tags, search, re-import
- **8 Settings tabs:** General, Reading, Highlight, Audio, **Voice preferences**, Translation, API, Data
- **6 UI languages:** en, uk (full), de, fr, es, pl (partial)
- **Backup v5** (voice sort prefs) + **clear library** (Settings → Data — API keys kept)
- Light / dark theme; API keys in OS keyring
- Settings → **Online** hides offline fields; **Offline** hides online fields

---

## Installation

```bash
pip install -r requirements.txt
```

Windows: double-click `run.bat`

## Run

```bash
python main.py
```

## Tests

```bash
python -m pytest -q
```

Offline TTS diagnostics: `python scripts/check_tts.py`

---

## Quick start

1. **Settings → General** — UI language, theme
2. **Settings → Reading** — book language, block size, **daily goal type** (blocks / time), PDF OCR
3. **Settings → Highlight** — highlight style; **Whisper word alignment** (Auto/On for offline EN)
4. **Settings → Audio** — voice; **speech rate** (range depends on engine); Auto / Online / Offline; **Word pronunciation**
5. **Settings → Voice preferences** — sort preset, gender, EN region, custom order
6. **Settings → Translation** — target language; engine for block / word / selection
7. **Settings → API** — keys; usage meters
8. **+ Add Book** — import (up to 80 MB)
9. **▶ Start** — reading; **🎧 Book audio** — bulk generation; **Status** — background jobs
10. **Statistics** — progress; **Settings → Data** — backup / restore / clear library

### Language recommendations

Choose TTS for **book language** (Settings → Reading → Book language), not UI language.

| Book language | Recommended TTS | Translation | Notes |
|---------------|-----------------|-------------|-------|
| **English** | **Edge** Jenny/Aria (online) or **Kokoro** `af_bella`, `af_sarah`, `af_heart` | free / DeepL | Whisper alignment works well for EN offline |
| **Ukrainian** | **Edge/Azure Polina** or **Piper** (`uk_UA-ukrainian_tts-medium`) | free / DeepL / Bergamot | Kokoro does **not** support uk |
| **De / Fr / Es / Pl** | Edge / Azure / **Piper** `*-medium` | DeepL / free | |
| **Ja / Zh / Ko** | Edge / Azure / Google Cloud | DeepL / Google | Offline neural limited |
| **Privacy / offline** | **Piper** or Kokoro (en) | **Bergamot** / **Ollama** | `tts/bergamot/setup.bat` |
| **Best quality** | ElevenLabs / Azure | DeepL | API keys + meters |
| **Budget / no keys** | **Edge** + free translate | free | Works out of the box |

**Two “speed” controls — by design:**

| Where | What it does |
|-------|----------------|
| **Settings → Audio → Speech rate** | Voice tempo **in the audio file**. Available values depend on the TTS engine. Requires **block regeneration**. |
| **1× / 1.25× / … button near ▶** | **Playback** of cached audio — accelerate only (1×–2×), instant. |

---

## Offline TTS setup

### Piper

1. `tts/piper/setup.bat`
2. `.onnx` models → `tts/piper/` ([Hugging Face](https://huggingface.co/rhasspy/piper-voices/tree/main))
3. Settings → Audio → Offline → **Neural (Piper CLI)**
4. Prefer `*-medium` models for books, not `x_low`

### Kokoro

Requires **Python 3.11–3.12** (separate worker):

```
AI Reading Studio  →  subprocess  →  tts/kokoro/kokoro_worker.py  →  audio.wav
```

1. `tts/kokoro/setup.bat`
2. Models in `tts/kokoro/models/`: `kokoro-v1.0.onnx`, `voices-v1.0.bin`
3. Settings → Offline voice → **Neural (Kokoro CLI)**
4. Recommended EN voices: `af_bella`, `af_sarah`, `af_heart`, `bf_emma`

Generation uses a **FIFO queue**; the first block may take 1–3 min. Minimum speech rate — **0.5×**.

### XTTS v2 / StyleTTS2

See `tts/xtts/setup.bat`, `tts/styletts2/setup.bat` — reference `.wav` or `.pth` model.

### Bergamot (offline translation)

Python **3.10** worker: `tts/bergamot/setup.bat` → `enuk` model and others.

### Whisper (better offline highlight)

1. `tts/whisper/setup.bat`
2. Settings → Highlight → **Whisper word alignment** → Auto or On
3. Best for **English**; limited for uk Piper

---

## Online TTS

| Service | Key | Settings |
|---------|-----|----------|
| **Edge** | none | Audio → Online → Edge |
| **Azure Speech** | portal.azure.com | API tab |
| **Google Cloud TTS** | console.cloud.google.com | API tab |
| **ElevenLabs** | elevenlabs.io | API tab |
| **Cartesia** | play.cartesia.ai/keys | API tab |
| **Murf** | murf.ai | API tab |

**Block and word prefetch** disabled for ElevenLabs, Cartesia, Murf — saves quota.

---

## Translation API

| Service | Where to get a key |
|---------|-------------------|
| **Apify** | console.apify.com |
| **Google Cloud** | console.cloud.google.com |
| **DeepL** | deepl.com/pro-api |
| **OpenAI** | platform.openai.com |
| **Bergamot** | local, `tts/bergamot/setup.bat` |
| **Ollama** | local, no key |

---

## Data locations

| What | Where |
|------|-------|
| Database | `%USERPROFILE%\.ai_reading_studio\reading_studio.db` |
| Audio cache | `%USERPROFILE%\.ai_reading_studio\audio\` |
| Log | `%USERPROFILE%\.ai_reading_studio\app.log` |

**Clear library** removes books, stats, audio/covers; **settings and API keys are kept**.

---

## Project structure

```
src/core/     DB, TTS (11 engines), voice ranking/prefs/gender, translation, highlight,
              whisper_align, user_errors, stats, backup
src/ui/       reading_view, book_audio_view, highlight controller, library, stats,
              settings, api_usage_meter, status panel
tests/        319 tests · 61 files
tts/          Piper, Kokoro, XTTS, StyleTTS2, Bergamot, Whisper — separate venv/workers
scripts/      check_tts.py
docs/         USER_GUIDE.md, PROJECT_ANALYSIS.md
```

---

## Build

Windows: `build_exe.bat`

---

## Documentation

- [docs/USER_GUIDE.md](docs/USER_GUIDE.md) — user guide
- [docs/PROJECT_ANALYSIS.md](docs/PROJECT_ANALYSIS.md) — architecture, metrics, roadmap
