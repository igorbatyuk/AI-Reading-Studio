# AI Reading Studio — Project Analysis

**Version:** 1.2.0 (`src/core/version.py`)  
**Updated:** July 25, 2026 (analysis revision)  
**Tests:** 319 passed · 61 files (`pytest -q`, ~70 s)  
**CI:** GitHub Actions — Python 3.12 (Ubuntu), `pytest --cov=src --cov-fail-under=54`, Ruff on `src/core`, `src/ui`, `tests`  
**Stack:** Python 3.12+ (main app), PySide6, SQLite, edge-tts, requests; subprocess workers for neural offline TTS / Bergamot / Whisper

---

## Contents

1. [Overview](#1-overview)
2. [Architecture](#2-architecture)
3. [Features (as implemented)](#3-features-as-implemented)
4. [Codebase metrics](#4-codebase-metrics)
5. [Strengths](#5-strengths)
6. [Weaknesses & open issues](#6-weaknesses--open-issues)
7. [TTS voices](#7-tts-voices)
8. [Security & privacy](#8-security--privacy)
9. [Roadmap & development options](#9-roadmap--development-options)
10. [Recommended stacks](#10-recommended-stacks)
11. [Maturity assessment](#11-maturity-assessment)
12. [Development & run](#12-development--run)

---

## 1. Overview

**AI Reading Studio** is a local desktop app for immersive reading: on-screen book + synchronized TTS + translation + reading statistics. Target platforms: **Windows / macOS / Linux** (primary development and testing on Windows).

User data is stored locally:

| Component | Path |
|-----------|------|
| SQLite DB | `%USERPROFILE%\.ai_reading_studio\reading_studio.db` |
| Audio cache | `audio/` |
| Covers | `covers/` |
| Log | `app.log` |
| Legacy / user models | `piper_models/`, `kokoro_models/`, `xtts_speakers/`, `styletts2_models/` |

**Not a commercial product** — a hobby project with broad functionality and deliberate trade-offs (6 separate Python venvs for workers, merged i18n for de/fr/es/pl, plain-text backup).

**Typical user:** English fiction/non-fiction with online Edge or offline Kokoro/Piper; Ukrainian — translation + Piper TTS; long sessions with word highlight and daily goals.

---

## 2. Architecture

### 2.1 Module tree

```
main.py
  └── src/app.py                    — QApplication, theme, i18n, logging
        └── src/ui/main_window.py   — navigation, service wiring
              ├── reading_view.py              — reading, audio controls, jump, focus
              ├── reading_highlight_controller.py — highlight sync ↔ QMediaPlayer, stale guard
              ├── highlight_overlay.py         — gradient / liquid / aurora paint
              ├── library (QStackedWidget)       — book list, tags, re-import
              ├── stats_view.py + stats_chart.py — calendar, charts, CSV
              ├── book_audio_view.py             — 🎧 book audio, bulk gen, use_saved_audio
              ├── settings_dialog.py + settings_options.py — 8 tabs (+ Voice preferences)
              ├── processing_status_panel.py     — background TTS / translate / import + meters
              ├── api_usage_meter.py             — green/yellow/red API quota progress
              ├── word_popup.py, block_translation_popup.py
              └── continue_dialog.py, jump_dialog.py, tags_dialog.py

src/core/  (~51 Python modules in core/, ~72 under src/)
  database.py, book_parser.py, text_splitter.py, book_import_worker.py
  tts_engine.py, tts_voices.py, tts_speed.py, tts_policy.py, tts_voice_ranking.py, voice_sort_prefs.py, voice_gender.py, offline_tts.py
  edge (edge-tts) · azure_tts · google_cloud_tts · elevenlabs_tts · cartesia_tts · murf_tts
  piper_tts · kokoro_tts · xtts_tts · styletts2_tts
  whisper_align.py — optional faster-whisper alignment for offline timings
  user_errors.py — humanize_error() for readable messages (Apify 402, quotas, Piper/Kokoro…)
  *_usage.py — local quota counters (Apify, Google Translate, DeepL, Azure/Google/ElevenLabs/Cartesia/Murf TTS)
  translation_service.py, bergamot_translate.py, deepl_translate.py, apify_translate.py, ollama_client.py
  word_highlight.py, media_duration.py, reading_stats.py, processing_status.py
  backup_service.py, cover_service.py, pdf_ocr.py, secrets.py, i18n.py, network_status.py

tts/  (separate venvs — not in pip requirements)
  piper/       — piper.exe + .onnx models
  kokoro/      — Python 3.11–3.12, kokoro_worker.py, FIFO _GenerationQueue
  xtts/        — Python 3.11, xtts_worker.py
  styletts2/   — styletts2_worker.py (bundled) or external CLI
  bergamot/    — Python 3.10, bergamot_worker.py (Mozilla NMT)
  whisper/     — faster-whisper worker for word alignment

tests/  — 61 files, 319 tests (core + cloud mocks + pytest-qt smoke)
scripts/check_tts.py — offline TTS diagnostics
.github/workflows/ci.yml — pytest + coverage + ruff
```

### 2.2 Reading flow

```
Import (EPUB/TXT/PDF[+OCR])
  → book_parser → text_splitter (35–280 words) → blocks in SQLite
  → reading_view.load_block
  → tts.prefetch(current + next block, respecting metered online)
  → translator.prefetch_sentence / prefetch_words (when allowed)
  → tts.speak → QMediaPlayer (playback_rate 1×–2×)
  → highlight overlay / karaoke QTextCharFormat
  → reading_stats.record_block + daily goal
  → playback_finished → next block
```

### 2.3 TTS flow

**Auto mode** (`tts_engine._auto_generators`):

```
Edge TTS (free)
  → Azure Speech (key + region)
  → Google Cloud TTS (key)
  → ElevenLabs (key)
  → Cartesia (key)
  → Murf (key)
  → offline engine (system | piper | kokoro | xtts | styletts2)
```

On each step failure — `logger.warning` + next engine. UI errors go through `humanize_error()`.

**Offline (explicit mode):** no silent fallback to `system` on neural engine failure — user sees a clear error.

**Playback sync (July 2026):**

- `playback_intent` — pause/play race protection (Kokoro, prefetch).
- Whisper alignment in background → `timings_ready` signal → highlight update without blocking UI.
- Engine-specific offsets: Piper 320 ms, Kokoro 200 ms, Edge exact ~45 ms.
- `reading_highlight_controller` — stale position guard on block change; scroll only on word change.

**Two “speed” controls (intentional):**

| Parameter | Where | Range | Effect |
|-----------|-------|-------|--------|
| `speech_rate` / `tts_speed` | Settings → Audio | **Engine-dependent** (e.g. Kokoro/Edge from 0.5×; Cartesia up to 1.5×) | **Generation** tempo; combo shows allowed values only |
| `playback_rate` | Button near ▶ | 1×–2× | `QMediaPlayer.setPlaybackRate`; instant, no new TTS |

### 2.4 Translation flow

**Auto chain** (`translation_service._provider_chain`, provider=`auto`):

```
OpenAI (key) → Apify (token) → Google Cloud (key) → DeepL (key)
  → Bergamot (local, if model exists) → Ollama (local)
  → free chain: Google free → Lingva → MyMemory
```

Separate providers for **block**, **word click**, and **selection**.

### 2.5 TTS cache & timings

- Cache key: hash(text + voice + speed + engine context + word/main profile).
- Edge: MP3 + `.timings.json` with exact word boundaries from stream.
- Murf: `wordDurations` → exact timings (when API returns them).
- Offline / other cloud: estimated timings + optional Whisper (Settings → Highlight → Whisper word alignment).
- `highlight_sync_offset_ms()` — UI/audio lag compensation; engine-specific lead for offline.

---

## 3. Features (as implemented)

### 3.1 Books & import

| Format | Module | Notes |
|--------|--------|-------|
| EPUB | `book_parser` + ebooklib | chapters, cover |
| TXT | UTF-8 | newline normalization |
| PDF | PyMuPDF | hyphenation, soft line breaks |
| PDF scans | `pdf_ocr` + Tesseract | `pdf_ocr_mode`: auto / always / off |

Re-import without losing `current_block`. Import worker with progress in status panel. File limit ~80 MB.

### 3.2 TTS — full matrix

| Class | Engine | Timings | Quota in UI |
|-------|--------|---------|-------------|
| Online free | **Edge** | exact (WordBoundary) | — |
| Online cloud | **Azure** | estimated | local est. + `can_spend()` hard cap |
| Online cloud | **Google Cloud TTS** | estimated | local est. + `can_spend()` hard cap |
| Online cloud | **ElevenLabs** | estimated | ~10k credits/mo |
| Online cloud | **Cartesia** | estimated | ~20k credits/mo |
| Online cloud | **Murf** | exact (wordDurations) | ~100k chars trial |
| Offline | **system** (pyttsx3) | estimated | — |
| Offline | **Piper** | estimated / Whisper | — |
| Offline | **Kokoro** | estimated / Whisper | FIFO queue, chunking |
| Offline | **XTTS v2** | estimated / Whisper | reference speaker |
| Offline | **StyleTTS2** | estimated / Whisper | bundled worker |

Additionally:

- **Word TTS profile** — separate engine/voice for word pronunciation.
- **Block prefetch** — disabled for metered online (ElevenLabs, Cartesia, Murf).
- **Word prefetch** — also disabled for metered online.
- **Preview voice** in Settings → Audio (fixed race with `_playback_active`).
- Settings → Online: offline fields hidden; Settings → Offline: online fields hidden (symmetric).

### 3.3 Word highlight

| Style | Timings |
|-------|---------|
| **Gradient** (default) | Edge/Murf exact; offline estimated or Whisper |
| Karaoke, Liquid, Marker, Aurora | estimated / Whisper |

Whisper: good for **English + Piper/Kokoro**; weaker for **uk_UA Piper + tiny model**.

### 3.4 Translation

8 providers + Auto chain; Bergamot (Py 3.10 worker) for offline NMT; Apify with humanized 402 memory limit.

### 3.5 Statistics

Blocks, words, **reading time** (active playback only). Daily goal: blocks or time. Calendar, charts, CSV.

### 3.6 UI / UX

- 6 UI languages: **en, uk** — 557 keys (full parity); **de, fr, es, pl** — merge with en (~400 keys remain EN).
- **8 Settings tabs** (900×740): Audio + **Voice preferences** + API meters.
- **Speech rate combo** — range depends on TTS engine (`ENGINE_UI_SPEECH_RATE_LIMITS`).
- **Gender tags** in voice combo (en/uk; de/fr/es/pl partially EN).
- Processing status panel — TTS engine, cache, translate queue, **cancel queued jobs**.
- **Book audio** — 🎧 page: bulk generation, queue, cancel, `use_saved_audio` per book.
- Backup **v5** (voice sort prefs), clear library (books/stats/audio; settings + keys kept).

---

## 4. Codebase metrics

| Metric | Value |
|--------|-------|
| Python modules `src/core/` | ~51 |
| Python modules `src/` (total) | ~72 |
| Test files | 61 |
| Tests | **319** |
| i18n keys en / uk | **557** (full parity) |
| i18n de / fr / es / pl | ~160 translated + merge with en (~400 keys remain EN) |
| Runtime deps (`requirements.txt`) | PySide6, edge-tts, pytest-qt… |
| Neural / Bergamot / Whisper workers | 6 separate venvs |
| Largest modules | `tts_engine.py` (~1900), `settings_dialog.py` (~2000), `database.py`, `i18n.py`, `reading_view.py`, `translation_service.py` |

### Test coverage (categories)

| Category | Examples |
|----------|----------|
| TTS core + sync | `test_tts_engine.py`, `test_playback_intent.py`, `test_word_highlight_sync.py`, `test_whisper_align.py` |
| Cloud TTS + quotas | `test_azure_tts.py`, `test_tts_cloud_usage.py`, `test_*_credit_saving.py` |
| Offline TTS | `test_piper_tts.py`, `test_kokoro_tts.py`, `test_kokoro_queue.py` |
| TTS / voices | `test_tts_voice_ranking.py`, `test_voice_sort_prefs.py`, `test_voice_gender.py`, `test_speech_rate_change.py`, `test_book_audio_queue.py` |
| UX / errors | `test_user_errors.py`, `test_api_usage_meter.py`, `test_voice_preview*.py` |
| Translation | `test_translation_service.py`, `test_bergamot_translate.py` |
| Data / backup | `test_backup_sync.py`, `test_clear_user_data.py` |
| UI smoke | `test_ui_smoke.py` |

---

## 5. Strengths

1. **Widest TTS stack in its class** — 6 online + 5 offline + Auto fallback chain.
2. **Two speed levels** — generation vs playback; correct mapping per provider.
3. **Flexible translation** — 8 providers, separate block/word/selection profiles, Bergamot for offline NMT.
4. **Highlight UX** — 5 styles, engine offsets, Whisper for offline EN, exact Edge/Murf.
5. **Cloud credit economy** — word/block prefetch off for metered TTS; hard caps for Azure/Google/ElevenLabs/Cartesia/Murf.
6. **Keyring + backup without keys** — `BACKUP_STRIPPED_SETTINGS` in export/import.
7. **319 tests + CI** — voice prefs, book audio queue, gender labels, speech-rate limits.
8. **Readable errors** — `humanize_error()` instead of raw HTTP text.
9. **Modular highlight layer** — `reading_highlight_controller` separate from `reading_view`.
10. **Book audio + status queue** — bulk generation with cancel; transparent background work.
11. **Voice UX** — curated sort, presets, gender tags, engine-limited speech rate, backup v5 prefs.
12. **API usage meters** — green / yellow / red in Settings → API and status panel.

---

## 6. Weaknesses & open issues

> Fixed items (voice prefs, book audio, speech rate, backup v5) moved to [§6.4](#64-fix-history-july-2026) — tables below list **current** risks only.

### 6.1 Product / UX

| Issue | Details | Impact | Priority |
|-------|---------|--------|----------|
| **Kokoro first generation** | 1–3 min per block on weak CPU; FIFO queue does not speed up the first block | Long wait before reading starts | High |
| **Ukrainian offline TTS** | Kokoro does **not** support uk; Piper — `ukrainian_tts-medium` vs `lada-x_low` | Offline uk worse than Edge/Azure Polina | High |
| **Offline onboarding** | 6× `setup.bat`, Python 3.10–3.12 depending on worker | High barrier for non-technical users | High |
| **Settings monolith** | `settings_dialog.py` ~2000 lines, 8 tabs in one class | Hard to maintain; voice prefs added ~400 lines | Medium |
| **i18n de/fr/es/pl** | ~400 keys remain EN; **40 new** (book audio, voice prefs, gender) untranslated | Partial UI in English in “localized” languages | Medium |
| **Single `tts_speed` for two profiles** | Block TTS and word TTS may use different engines but one speed in DB | Custom word profile may get wrong combo limits | Low |
| **Auto TTS opaque fallback** | `provider_skipped` in status bar without chain details | User does not understand why it fell back to offline | Medium |
| **No recommended-stack wizard** | New user must configure Edge + book lang + voice manually | Extra steps on first run | Low |

### 6.2 Technical

| Issue | Details | Impact | Priority |
|-------|---------|--------|----------|
| **Offline highlight drift** | Estimated timings + fixed offsets (Piper 320 ms, Kokoro 200 ms); Whisper weak for uk | Highlight “drifts” on long offline blocks | High |
| **Local quota counters** | Azure/Google/Cartesia — estimate; billing portal sync partial (ElevenLabs/Murf better) | Shown vs actual quota may diverge | Medium |
| **EPUB3 SMIL / media overlay** | Import text only (`book_parser.py`); EPUB timings ignored | Lost exact sync for some EPUB audiobooks | Medium |
| **Plain-text backup** | JSON with full book text; keys stripped but content open | Risk when syncing to cloud / another PC | Medium |
| **UI tests for book audio** | `book_audio_view.py` — engine-level tests only; no DnD voice order / speech combo UI tests | Settings regressions may pass CI | Low |
| **XTTS / StyleTTS2** | Complex setup; CI — mock/subprocess without real GPU | Rarely used; little field feedback | Low |
| **CI coverage 54%** | `.github/workflows/ci.yml` — low threshold for codebase size | Large modules (`tts_engine`, `reading_view`) under-tested | Low |

### 6.3 Architectural trade-offs (intentional, not bugs)

| Topic | Why | When to change |
|-------|-----|----------------|
| 6 separate worker venvs | Python incompatibility Kokoro / Bergamot / Whisper / XTTS | If unified worker or Docker image appears |
| Unencrypted backup | Simple restore; hobby scope | User request / cloud sync |
| No air-gap toggle | Offline + Bergamot + no keys is enough | If enterprise privacy mode needed |
| Two “speed” (generation vs playback) | Different QMediaPlayer vs TTS API semantics | Do not merge — worse confusion |
| Metered word prefetch off | Saves ElevenLabs/Cartesia/Murf credits | Optional “prefetch words” toggle possible |

### 6.4 Fix history (July 2026)

| Area | Status |
|------|--------|
| Curated voice sort + Settings → Voice preferences (preset, gender, region, DnD, backup v5) | ✅ |
| Gender labels (Female/Male) in all voice combos | ✅ |
| Speech rate: API mapping (Cartesia/Murf/Edge/…) + engine-limited combo + live apply | ✅ |
| Book audio 🎧: bulk generation, queue cancel, `use_saved_audio` | ✅ |
| Per-book audio cache `audio/books/{id}/`, `clear_book_cache()` | ✅ |
| Prefetch skip on jump; metered ahead=1 | ✅ |
| Wider Settings dialog (900×740) | ✅ |
| Playback intent / pause+speed race | ✅ (earlier) |

---

## 7. TTS voices

### 7.1 Current implementation

Single sort point — **`get_voices_for_tts_context()`**:

```
get_voices_for_tts_context()
  → apply_gender_labels()          // voice_gender.py
  → sort_voices_for_reading(prefs) // tts_voice_ranking.py + voice_sort_prefs.py
```

| Component | Module | Role |
|-----------|--------|------|
| Curated order | `tts_voice_ranking.py` | Recommended narrators, hide unsuitable, ★ badge |
| User prefs | `voice_sort_prefs.py` | preset, gender, EN region, custom order JSON → SQLite + backup v5 |
| Gender tags | `voice_gender.py` | Female/Male/Neutral → localized suffix in label |
| UI | Settings → **Voice preferences** | Preset combo, DnD list per engine |

**Default voice:** `voices[0]` after sort — first in list = recommended for new picks; saved `tts_voice` is not reset.

### 7.2 Recommended voices (Audiobook preset guide)

| Language | Online | Offline |
|----------|--------|---------|
| **English** | Jenny, Aria, Guy, Sonia (UK) | Kokoro `af_bella`, `af_sarah`; Piper `*-lessac-medium`, `*-amy-medium` |
| **Ukrainian** | Polina (Edge/Azure) | Piper `uk_UA-ukrainian_tts-medium` |
| **De/Fr/Es/Pl** | Katja, Denise, Elvira, Zofia… | Piper `*-medium` |

### 7.3 Possible next steps (voices)

| Option | Description | Effort |
|--------|-------------|--------|
| **7.3a Engine priority in Auto** | User-defined online/offline order in Voice prefs | Medium |
| **7.3b Preset per book language** | Auto preset “uk → Polina-first” when book lang changes | Low |
| **7.3c Cloud voice cache refresh** | “Refresh voices” button for ElevenLabs/Murf/Cartesia API | Low |
| **7.3d Piper model metadata** | JSON sidecar with gender/quality instead of substring heuristics | Medium |

---

## 8. Security & privacy

| Aspect | Status |
|--------|--------|
| API keys in OS keyring | ✅ 10 accounts in `secrets.py` |
| Keys cleared from DB on keyring save | ✅ |
| Keys excluded from backup export/import | ✅ `BACKUP_STRIPPED_SETTINGS` |
| Book text | SQLite local |
| Cloud TTS / translate | Block text sent over network with online providers |
| Bergamot / Ollama / Whisper | Local ✅ |
| Telemetry | None ✅ |
| Backup JSON | Plain text of all books — do not publish ⚠️ |

---

## 9. Roadmap & development options

### 9.1 Priority A — Ukrainian & offline quality

| Option | What it does | Effort | Recommendation |
|--------|--------------|--------|----------------|
| **A1. Whisper uk** | Model picker (tiny/base/small), uk hints in Settings → Highlight | Medium | Better offline highlight; TTS unchanged |
| **A2. Online-first uk preset** | When book lang=uk: Edge Polina + hint “not Kokoro” | Low | **Quick win** for TTS quality |
| **A3. Piper uk bundle** | Promote `ukrainian_tts-medium`, hide x_low by default | Low | Improves offline uk |

### 9.2 Priority B — Highlight & EPUB

| Option | What it does | Effort |
|--------|--------------|--------|
| **B1. EPUB3 SMIL import** | Timings/media overlay from EPUB → exact highlight | High |
| **B2. Offset slider** | Settings → Highlight: ±ms per engine | Low |
| **B3. Whisper re-align** | “Re-align block” button in reading view | Medium |

### 9.3 Priority C — Settings & i18n

| Option | What it does | Effort |
|--------|--------------|--------|
| **C1. Split settings_dialog** | `settings_panels/audio.py`, `voice_prefs.py`, `api.py` | Medium |
| **C2. i18n 40 new keys** | book_audio + voice_prefs → de/fr/es/pl | Low |
| **C3. CI key parity** | Test: every en key exists in uk | Low |

### 9.4 Priority D — Backup, privacy, quota

| Option | What it does | Effort |
|--------|--------------|--------|
| **D1. Encrypted backup** | Optional password → AES JSON export | Medium |
| **D2. Settings-only export** | Voice prefs + reading without book text | Low |
| **D3. Auto-chain tooltip** | Status: “Azure skipped (quota) → Edge” | Low |
| **D4. Book audio estimate** | Before bulk gen: “~N chars / credits” | Medium |

### 9.5 Priority E — Offline onboarding

| Option | What it does | Effort |
|--------|--------------|--------|
| **E1. setup_all.bat** | Sequential check of all workers | Medium |
| **E2. In-app setup wizard** | Detect missing venv/model → links | High |
| **E3. First-run profile** | “English online” / “Ukrainian offline” one-click | Low |

### 9.6 Long-term

1. On-device LLM translation (llama.cpp) without Ollama server.
2. In-app XTTS voice cloning UX.
3. Optional encrypted cloud sync folder (instead of plain JSON in Dropbox).
4. Raise CI coverage threshold (54% → 65%+).

### 9.7 Recommended queue (Q3 2026)

1. **A2 + A3** — uk quality without large refactor.
2. **D3 + C2** — Auto transparency + i18n for new features.
3. **B2 or A1** — highlight drift.
4. **C1** — when Settings grows again.

---

## 10. Recommended stacks

| Scenario | TTS | Block translation | Highlight |
|----------|-----|-------------------|-----------|
| English fiction, online | **Edge** (Jenny/Aria) | DeepL / free | Gradient + Edge exact |
| English, offline | **Kokoro** (`af_bella`, `af_sarah`) + Whisper | Bergamot / free | Whisper On for EN |
| Ukrainian | **Edge/Azure Polina** or Piper medium | DeepL / Bergamot `enuk` | Estimated; Whisper limited |
| Offline privacy | Piper + Bergamot | Bergamot / Ollama | Estimated |
| Best quality | ElevenLabs / Azure | DeepL | Edge/Murf exact |
| Budget | Edge + free translate | free | Gradient |

---

## 11. Maturity assessment

| Criterion | Rating | Comment |
|-----------|--------|---------|
| Core reading loop | ⭐⭐⭐⭐⭐ | Prefetch, pause, focus, jump, playback intent |
| TTS breadth | ⭐⭐⭐⭐⭐ | 11 engines + Auto — rare for hobby app |
| TTS reliability offline | ⭐⭐⭐☆☆ | Kokoro/XTTS slow; queue better than lock |
| Cloud TTS economy | ⭐⭐⭐⭐☆ | Metered prefetch off; local hard caps |
| Translation | ⭐⭐⭐⭐☆ | Bergamot + 7 cloud; humanized Apify errors |
| Highlight sync | ⭐⭐⭐⭐☆ | Edge/Murf/Whisper EN good; uk offline weaker |
| Voice UX | ⭐⭐⭐⭐☆ | Voice preferences, gender tags, engine-limited speech rate |
| i18n | ⭐⭐⭐☆☆ | en/uk full; others merged |
| Security / backup | ⭐⭐⭐⭐☆ | Keyring + stripped backup; backup v5 |
| Test / CI | ⭐⭐⭐⭐☆ | 319 tests; full ruff scope |
| Docs | ⭐⭐⭐⭐☆ | README + USER_GUIDE + this document |

**Overall maturity: 4.6 / 5** — daily driver for **English**; for **uk** — online TTS is solid; offline TTS + highlight are main growth areas (§9.1, §9.2).

---

## 12. Development & run

```bash
pip install -r requirements.txt
python main.py
python -m pytest -q          # 319 passed
python scripts/check_tts.py  # offline TTS diagnostics
```

**Workers (separate):**

```bat
tts\piper\setup.bat
tts\kokoro\setup.bat      REM Python 3.11–3.12
tts\xtts\setup.bat        REM Python 3.11
tts\styletts2\setup.bat
tts\bergamot\setup.bat    REM Python 3.10
tts\whisper\setup.bat     REM faster-whisper alignment
```

Windows exe: `build_exe.bat` / `AIReadingStudio.spec`

---

*User guide: [USER_GUIDE.md](USER_GUIDE.md)*  
*Overview: [README.md](../README.md)*
