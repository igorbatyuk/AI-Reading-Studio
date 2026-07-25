# AI Reading Studio — User Guide

## Requirements

- Python 3.12+ (main app)
- Internet for online TTS / translation (optional if using offline stack)
- Neural offline workers: separate venvs — see [README.md](../README.md)

## Quick start

```bash
pip install -r requirements.txt
python main.py
```

## Settings overview

| Tab | Options |
|-----|---------|
| **General** | UI language (en, uk, de, fr, es, pl), theme |
| **Reading** | Book language, block size, daily goal (blocks or time), PDF OCR |
| **Highlight** | Style (gradient recommended), colours, **Whisper alignment** (offline exact timings) |
| **Audio** | TTS mode, voice (with **gender** tag), **speech rate** (range depends on engine), word pronunciation profile |
| **Voice preferences** | Sort preset (Audiobook / News / Fast / Custom), gender priority, EN region, hide unsuitable voices, ★ badge, drag-and-drop order per engine |
| **Translation** | Target language; engines for block / word / selection |
| **API** | Keys + usage counters (Apify, Google, DeepL, Azure/Google/ElevenLabs/Cartesia/Murf TTS) |
| **Data** | Backup v5, restore, clear library |

### Two speed controls

| Control | Where | Effect |
|---------|-------|--------|
| **Speech rate** | Settings → Audio | How fast the **generated audio file** reads. The combo shows only values supported by the **current TTS engine** (e.g. Kokoro/Edge from 0.5×; Cartesia up to 1.5×). Regenerate block to apply. |
| **Playback speed** | Button near ▶ (1×–2×) | Speeds up **playback** of cached audio instantly (accelerate only) |

### Voice list

- Voices are sorted for **book reading** (recommended narrators first).
- Each voice shows **Female / Male** (or **Жіночий / Чоловічий** in Ukrainian UI).
- Customize order in **Settings → Voice preferences** (Голоси).
- First voice in the Audio list = recommended default for new selections.

### TTS engines

| Mode | Chain |
|------|-------|
| **Auto** | Edge → Azure → Google → ElevenLabs → Cartesia → Murf → offline |
| **Online** | Edge, Azure, Google, ElevenLabs, Cartesia, or Murf (pick one) |
| **Offline** | System, Piper, Kokoro, XTTS v2, StyleTTS2 |

- **Edge** — free, exact word highlight timings  
- **ElevenLabs / Cartesia / Murf** — API keys in Settings → API; word prefetch disabled to save quota  
- **Kokoro** — English-focused offline neural; **not for Ukrainian books** (use Piper `uk_UA-*`)  
- **Bergamot** — offline translation (`tts/bergamot/setup.bat`, Python 3.10)

### Translation

Separate provider for **block**, **word click**, and **selection**:

Auto chain: OpenAI → Apify → Google → DeepL → Bergamot → Ollama → free (Google/Lingva/MyMemory)

### Ollama (local)

1. Install [Ollama](https://ollama.com) and pull a model (`ollama pull llama3.2`)  
2. Settings → API — URL and model  
3. Settings → Translation — Ollama or Auto

## Library

- Search, sort, tags, covers, re-import blocks  
- **Remove** — deletes book progress; settings and API keys stay  
- **Clear library** (Settings → Data) — removes books/stats/audio; keeps settings  

### Book audio (🎧)

Sidebar page below **Library**:

- Pick a book, see block list and generation progress  
- **Generate all** or per-block; **cancel** queued jobs (also in **Status** panel)  
- Toggle **use saved audio when reading** — keeps files on disk but skips them during playback if off  

### PDF OCR

Settings → Reading → PDF OCR: Auto / Always / Off. Requires Tesseract.

## Backup (v5)

Export JSON includes books (full text + cover base64), daily stats, settings (including **voice sort preferences**), and non-secret options.

**API keys are never included** (stored in OS keyring). Restore on another PC; re-enter API keys if needed.

## Statistics

- Blocks, words, reading time (active playback only)  
- Daily goal: blocks or time  
- Charts: 7 days / 12 months / 5 years; CSV export  

## Troubleshooting

| Issue | Check |
|-------|-------|
| No audio | Settings → Audio; Status panel for generation errors |
| Slow first block (Kokoro) | Normal 1–3 min; queue serializes jobs fairly |
| Speech rate option missing | Engine limit — switch TTS engine or mode; combo adapts automatically |
| Imprecise offline highlight | Settings → Highlight → Whisper alignment → Auto; run `tts/whisper/setup.bat` |
| Quota message in status | Auto switched to next engine; check Settings → API counters |
| Ukrainian TTS | Piper offline or Edge/Azure online — not Kokoro |

See also [README.md](../README.md) and [PROJECT_ANALYSIS.md](PROJECT_ANALYSIS.md).
