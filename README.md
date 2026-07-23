# AI Reading Studio

Локальна програма для читання книг із синхронним озвученням (Windows / macOS / Linux).

**Версія:** 1.2.0 · **Тести:** 279 passed · **55 test files**  
**Повний аналіз проєкту:** [PROJECT_ANALYSIS.md](PROJECT_ANALYSIS.md) — архітектура, слабкі сторони, roadmap (у т.ч. майбутнє меню сортування голосів)

---

## Можливості

### Книги та читання

- **Формати:** EPUB, TXT, PDF (OCR для сканів через Tesseract — Settings → Reading)
- **Блоки:** 35–280 слів, jump до блоку, focus mode, ширина рядка до 3600 px
- **Аудіо:** пауза, restart, −5 с, **швидкість відтворення** 1×–2× (лише прискорення; окремо від **швидкості мовлення** в Settings)
- **Підсвітка слів:** gradient (за замовч.), karaoke, liquid, marker, aurora + палітри кольорів
- **Whisper alignment** (опційно) — точні timestamps для offline Piper/Kokoro/XTTS (EN найкраще)
- **Переклад блоку** · **клік по слову** (popup + ▶ вимова) · **виділення тексту**
- **Статус обробки** — кнопка «Статус» у рядку стану: TTS engine, блок, кеш, переклад

### Озвучення (TTS)

| Режим | Движки |
|-------|--------|
| **Online** | Edge (free), Azure Speech, Google Cloud TTS, ElevenLabs, Cartesia, Murf |
| **Offline** | System (pyttsx3), **Piper**, **Kokoro**, **XTTS v2**, **StyleTTS2** |
| **Auto** | Edge → Azure → Google → ElevenLabs → Cartesia → Murf → offline |

- Список голосів оновлюється при зміні движка / мови книги
- **Окремий профіль TTS для слів** (напр. Edge для слів + ElevenLabs для блоків)
- Preview voice у Settings → Audio
- Кеш аудіо на диску — повторне відтворення миттєве
- **Playback sync** — захист pause/play race (Kokoro), engine offsets для підсвітки
- **Kokoro FIFO queue** — черга генерації замість глобального блокування

> **Голоси:** порядок у списку поки **не оптимізований** під читання книг (Piper — за датою файлу, Edge — порядок у коді). У [PROJECT_ANALYSIS.md §7](PROJECT_ANALYSIS.md#7-голоси-tts-поточний-стан-і-розвиток) — план **окремого меню Voice preferences** (пріоритети, статть, регіон, custom order).

### Переклад

Окремий движок для **блоку**, **кліку по слову**, **виділеного тексту**:

- **Apify**, **Google Cloud**, **DeepL**, **OpenAI**, **Bergamot**, **Ollama**, **free** (Google/Lingva/MyMemory)
- **Auto chain:** OpenAI → Apify → Google → DeepL → Bergamot → Ollama → free
- **Зрозумілі помилки** — Apify 402 (memory limit), квоти, мережа, Piper/Kokoro (`humanize_error`)
- Лічильники використання з **кольоровими meters** (зелений / жовтий / червоний) — Settings → API

| Сервіс | Орієнтовний ліміт (local counter) |
|--------|-----------------------------------|
| Apify translate | ~500k символів/міс. |
| ElevenLabs TTS | ~10k credits/міс. |
| Cartesia TTS | ~20k credits/міс. |
| Murf TTS | ~100k символів trial |
| Azure / Google TTS | local hard cap (~500k chars/міс. est.) |

### Статистика та цілі

- Блоки, слова, **час читання** (лічиться лише під час активного playback)
- **Денна ціль:** блоки **або** час (5 хв … 8 год)
- Календар, графіки 7 днів / 12 місяців / 5 років, експорт CSV

### Інше

- **Бібліотека:** обкладинки, теги, пошук, re-import
- **6 мов UI:** en, uk (повні), de, fr, es, pl (частково)
- **Backup v4** + **очистка бібліотеки** (Settings → Data — без API ключів)
- Світла / темна тема; ключі API в OS keyring
- Settings → **Online** приховує offline-поля; **Offline** — online-поля

---

## Встановлення

```bash
pip install -r requirements.txt
```

Windows: подвійний клік `run.bat`

## Запуск

```bash
python main.py
```

## Тести

```bash
python -m pytest -q
```

Діагностика offline TTS: `python scripts/check_tts.py`

---

## Швидкий старт

1. **Settings → General** — мова інтерфейсу, тема
2. **Settings → Reading** — мова книги, розмір блоку, **тип денної цілі** (блоки / час), PDF OCR
3. **Settings → Highlight** — стиль підсвітки; **Whisper word alignment** (Auto/On для offline EN)
4. **Settings → Audio** — голос; **швидкість мовлення**; **швидкість відтворення** (1×–2× біля ▶); Auto / Online / Offline; **Word pronunciation**
5. **Settings → Translation** — мова перекладу; движок для блоку / слова / виділення
6. **Settings → API** — ключі; лічильники з кольоровими meters
7. **+ Add Book** — імпорт (до 80 МБ)
8. **▶ Start** — читання; **Статус** — фонова генерація аудіо
9. **Statistics** — прогрес; **Settings → Data** — backup / restore / clear library

### Рекомендації по мовах

Обирайте TTS під **мову книги** (Settings → Reading → Book language), не під мову інтерфейсу.

| Мова книги | Рекомендований TTS | Переклад | Примітка |
|------------|-------------------|----------|----------|
| **English** | **Edge** Jenny/Aria (online) або **Kokoro** `af_bella`, `af_sarah`, `af_heart` | free / DeepL | Whisper alignment — добре для EN offline |
| **Українська** | **Edge/Azure Polina** або **Piper** (`uk_UA-ukrainian_tts-medium`) | free / DeepL / Bergamot | Kokoro **не** підтримує uk |
| **Deutsch / Français / Español / Polski** | Edge / Azure / **Piper** `*-medium` | DeepL / free | |
| **日本語 / 中文 / 한국어** | Edge / Azure / Google Cloud | DeepL / Google | Offline neural обмежено |
| **Приватність / offline** | **Piper** або Kokoro (en) | **Bergamot** / **Ollama** | `tts/bergamot/setup.bat` |
| **Максимальна якість** | ElevenLabs / Azure | DeepL | API keys + meters |
| **Бюджет / без ключів** | **Edge** + free translate | free | Працює «з коробки» |

**Два «speed» — це навмисно:**

| Де | Що робить |
|----|-----------|
| **Settings → Audio → Швидкість мовлення** | Темп голосу **в аудіофайлі** (0.25×–2×). Потрібна **перегенерація** блоку. |
| **Кнопка 1× / 1.25× / … біля ▶** | **Відтворення** готового файлу — лише прискорення (1×–2×), миттєво. |

---

## Offline TTS — налаштування

### Piper

1. `tts/piper/setup.bat`
2. Моделі `.onnx` → `tts/piper/` ([Hugging Face](https://huggingface.co/rhasspy/piper-voices/tree/main))
3. Settings → Audio → Offline → **Neural (Piper CLI)**
4. Для книг краще `*-medium`, не `x_low`

### Kokoro

Потребує **Python 3.11–3.12** (окремий worker):

```
AI Reading Studio  →  subprocess  →  tts/kokoro/kokoro_worker.py  →  audio.wav
```

1. `tts/kokoro/setup.bat`
2. Моделі в `tts/kokoro/models/`: `kokoro-v1.0.onnx`, `voices-v1.0.bin`
3. Settings → Offline voice → **Neural (Kokoro CLI)**
4. Рекомендовані en-голоси: `af_bella`, `af_sarah`, `af_heart`, `bf_emma`

Генерація через **FIFO queue**; перший блок може зайняти 1–3 хв.

### XTTS v2 / StyleTTS2

Див. `tts/xtts/setup.bat`, `tts/styletts2/setup.bat` — reference `.wav` або `.pth` модель.

### Bergamot (offline переклад)

Python **3.10** worker: `tts/bergamot/setup.bat` → модель `enuk` та ін.

### Whisper (точніша підсвітка offline)

1. `tts/whisper/setup.bat`
2. Settings → Highlight → **Whisper word alignment** → Auto або On
3. Найкраще для **English**; для uk Piper — обмежено

---

## Online TTS

| Сервіс | Ключ | Settings |
|--------|------|----------|
| **Edge** | без ключа | Audio → Online → Edge |
| **Azure Speech** | portal.azure.com | API → Audio |
| **Google Cloud TTS** | console.cloud.google.com | API → Audio |
| **ElevenLabs** | elevenlabs.io | API → Audio |
| **Cartesia** | play.cartesia.ai/keys | API → Audio |
| **Murf** | murf.ai | API → Audio |

**Prefetch блоків і слів** вимкнено для ElevenLabs, Cartesia, Murf — економія квоти.

---

## API для перекладу

| Сервіс | Де взяти ключ |
|--------|---------------|
| **Apify** | console.apify.com |
| **Google Cloud** | console.cloud.google.com |
| **DeepL** | deepl.com/pro-api |
| **OpenAI** | platform.openai.com |
| **Bergamot** | локально, `tts/bergamot/setup.bat` |
| **Ollama** | локально, без ключа |

---

## Дані

| Що | Де |
|----|-----|
| База | `%USERPROFILE%\.ai_reading_studio\reading_studio.db` |
| Аудіо-кеш | `%USERPROFILE%\.ai_reading_studio\audio\` |
| Лог | `%USERPROFILE%\.ai_reading_studio\app.log` |

**Clear library** видаляє книги, статистику, audio/covers; **налаштування та API keys зберігаються**.

---

## Структура проєкту

```
src/core/     БД, TTS (11 engines), переклад, highlight, whisper_align,
              user_errors, stats, backup, secrets
src/ui/       reading_view, highlight controller, library, stats,
              settings, api_usage_meter, status panel
tests/        279 тестів · 55 файлів
tts/          Piper, Kokoro, XTTS, StyleTTS2, Bergamot, Whisper — окремі venv/workers
scripts/      check_tts.py
docs/         USER_GUIDE.md
```

---

## Збірка

Windows: `build_exe.bat`

---

## Документація

- [docs/USER_GUIDE.md](docs/USER_GUIDE.md) — користувацька інструкція
- [PROJECT_ANALYSIS.md](PROJECT_ANALYSIS.md) — глибокий аналіз, слабкі сторони, roadmap (Voice preferences §7)
