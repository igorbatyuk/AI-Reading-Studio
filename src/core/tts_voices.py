"""Edge TTS voices grouped by book language."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class VoiceOption:
    voice_id: str
    locale: str
    name: str
    gender: str

    @property
    def label(self) -> str:
        region = LOCALE_REGION.get(self.locale, self.locale)
        gender = "Female" if self.gender == "Female" else "Male"
        return f"{region} — {self.name} ({gender})"


LOCALE_REGION = {
    "en-US": "US",
    "en-GB": "UK",
    "en-AU": "AU",
    "en-CA": "CA",
    "en-IN": "IN",
    "uk-UA": "UA",
    "ru-RU": "RU",
    "nb-NO": "NO",
    "de-DE": "DE",
    "fr-FR": "FR",
    "fr-CA": "CA",
    "es-ES": "ES",
    "es-MX": "MX",
    "it-IT": "IT",
    "pt-BR": "BR",
    "pt-PT": "PT",
    "pl-PL": "PL",
    "nl-NL": "NL",
    "sv-SE": "SE",
    "da-DK": "DK",
    "fi-FI": "FI",
    "cs-CZ": "CZ",
    "ja-JP": "JP",
    "ko-KR": "KR",
    "tr-TR": "TR",
    "zh-CN": "CN",
}


def filter_voices_for_book_language(
    voices: list[tuple[str, str]],
    lang_code: str,
    iso_map: dict[str, str],
) -> list[tuple[str, str]]:
    """Keep voices whose label matches the book language (e.g. '(UK)' or '(EN)')."""
    if not voices:
        return []
    target = iso_map.get(lang_code, lang_code).lower()
    short = target.split("-")[0]
    matched: list[tuple[str, str]] = []
    for voice_id, label in voices:
        blob = label.lower()
        if (
            f"({target})" in blob
            or f"({short})" in blob
            or f" {target})" in blob
            or f" {short})" in blob
        ):
            matched.append((voice_id, label))
    return matched

# (code, display name)
BOOK_LANGUAGES: list[tuple[str, str]] = [
    ("en", "English"),
    ("uk", "Ukrainian / Українська"),
    ("ru", "Russian / Русский"),
    ("nb", "Norwegian / Norsk"),
    ("de", "German / Deutsch"),
    ("fr", "French / Français"),
    ("es", "Spanish / Español"),
    ("it", "Italian / Italiano"),
    ("pt", "Portuguese / Português"),
    ("pl", "Polish / Polski"),
    ("nl", "Dutch / Nederlands"),
    ("sv", "Swedish / Svenska"),
    ("da", "Danish / Dansk"),
    ("fi", "Finnish / Suomi"),
    ("cs", "Czech / Čeština"),
    ("ja", "Japanese / 日本語"),
    ("ko", "Korean / 한국어"),
    ("tr", "Turkish / Türkçe"),
    ("zh", "Chinese / 中文"),
]

LANGUAGE_LOCALES: dict[str, list[str]] = {
    "en": ["en-US", "en-GB", "en-AU", "en-CA", "en-IN"],
    "uk": ["uk-UA"],
    "ru": ["ru-RU"],
    "nb": ["nb-NO"],
    "de": ["de-DE"],
    "fr": ["fr-FR", "fr-CA"],
    "es": ["es-ES", "es-MX"],
    "it": ["it-IT"],
    "pt": ["pt-BR", "pt-PT"],
    "pl": ["pl-PL"],
    "nl": ["nl-NL"],
    "sv": ["sv-SE"],
    "da": ["da-DK"],
    "fi": ["fi-FI"],
    "cs": ["cs-CZ"],
    "ja": ["ja-JP"],
    "ko": ["ko-KR"],
    "tr": ["tr-TR"],
    "zh": ["zh-CN"],
}

DEFAULT_VOICE: dict[str, str] = {
    "en": "en-US-AriaNeural",
    "uk": "uk-UA-PolinaNeural",
    "ru": "ru-RU-SvetlanaNeural",
    "nb": "nb-NO-PernilleNeural",
    "de": "de-DE-KatjaNeural",
    "fr": "fr-FR-DeniseNeural",
    "es": "es-ES-ElviraNeural",
    "it": "it-IT-ElsaNeural",
    "pt": "pt-BR-FranciscaNeural",
    "pl": "pl-PL-ZofiaNeural",
    "nl": "nl-NL-ColetteNeural",
    "sv": "sv-SE-SofieNeural",
    "da": "da-DK-ChristelNeural",
    "fi": "fi-FI-NooraNeural",
    "cs": "cs-CZ-VlastaNeural",
    "ja": "ja-JP-NanamiNeural",
    "ko": "ko-KR-SunHiNeural",
    "tr": "tr-TR-EmelNeural",
    "zh": "zh-CN-XiaoxiaoNeural",
}

VOICES: list[VoiceOption] = [
    # English — US
    VoiceOption("en-US-AriaNeural", "en-US", "Aria", "Female"),
    VoiceOption("en-US-JennyNeural", "en-US", "Jenny", "Female"),
    VoiceOption("en-US-AvaNeural", "en-US", "Ava", "Female"),
    VoiceOption("en-US-EmmaNeural", "en-US", "Emma", "Female"),
    VoiceOption("en-US-MichelleNeural", "en-US", "Michelle", "Female"),
    VoiceOption("en-US-AnaNeural", "en-US", "Ana", "Female"),
    VoiceOption("en-US-AvaMultilingualNeural", "en-US", "Ava Multilingual", "Female"),
    VoiceOption("en-US-EmmaMultilingualNeural", "en-US", "Emma Multilingual", "Female"),
    VoiceOption("en-US-GuyNeural", "en-US", "Guy", "Male"),
    VoiceOption("en-US-AndrewNeural", "en-US", "Andrew", "Male"),
    VoiceOption("en-US-BrianNeural", "en-US", "Brian", "Male"),
    VoiceOption("en-US-ChristopherNeural", "en-US", "Christopher", "Male"),
    VoiceOption("en-US-EricNeural", "en-US", "Eric", "Male"),
    VoiceOption("en-US-RogerNeural", "en-US", "Roger", "Male"),
    VoiceOption("en-US-SteffanNeural", "en-US", "Steffan", "Male"),
    VoiceOption("en-US-AndrewMultilingualNeural", "en-US", "Andrew Multilingual", "Male"),
    VoiceOption("en-US-BrianMultilingualNeural", "en-US", "Brian Multilingual", "Male"),
    # English — UK
    VoiceOption("en-GB-SoniaNeural", "en-GB", "Sonia", "Female"),
    VoiceOption("en-GB-LibbyNeural", "en-GB", "Libby", "Female"),
    VoiceOption("en-GB-MaisieNeural", "en-GB", "Maisie", "Female"),
    VoiceOption("en-GB-RyanNeural", "en-GB", "Ryan", "Male"),
    VoiceOption("en-GB-ThomasNeural", "en-GB", "Thomas", "Male"),
    # English — AU / CA / IN
    VoiceOption("en-AU-NatashaNeural", "en-AU", "Natasha", "Female"),
    VoiceOption("en-AU-WilliamMultilingualNeural", "en-AU", "William", "Male"),
    VoiceOption("en-CA-ClaraNeural", "en-CA", "Clara", "Female"),
    VoiceOption("en-CA-LiamNeural", "en-CA", "Liam", "Male"),
    VoiceOption("en-IN-NeerjaNeural", "en-IN", "Neerja", "Female"),
    VoiceOption("en-IN-NeerjaExpressiveNeural", "en-IN", "Neerja Expressive", "Female"),
    VoiceOption("en-IN-PrabhatNeural", "en-IN", "Prabhat", "Male"),
    # Ukrainian
    VoiceOption("uk-UA-PolinaNeural", "uk-UA", "Polina", "Female"),
    VoiceOption("uk-UA-OstapNeural", "uk-UA", "Ostap", "Male"),
    # Russian
    VoiceOption("ru-RU-SvetlanaNeural", "ru-RU", "Svetlana", "Female"),
    VoiceOption("ru-RU-DmitryNeural", "ru-RU", "Dmitry", "Male"),
    # Norwegian
    VoiceOption("nb-NO-PernilleNeural", "nb-NO", "Pernille", "Female"),
    VoiceOption("nb-NO-FinnNeural", "nb-NO", "Finn", "Male"),
    # German
    VoiceOption("de-DE-KatjaNeural", "de-DE", "Katja", "Female"),
    VoiceOption("de-DE-AmalaNeural", "de-DE", "Amala", "Female"),
    VoiceOption("de-DE-SeraphinaMultilingualNeural", "de-DE", "Seraphina", "Female"),
    VoiceOption("de-DE-ConradNeural", "de-DE", "Conrad", "Male"),
    VoiceOption("de-DE-KillianNeural", "de-DE", "Killian", "Male"),
    VoiceOption("de-DE-FlorianMultilingualNeural", "de-DE", "Florian", "Male"),
    # French
    VoiceOption("fr-FR-DeniseNeural", "fr-FR", "Denise", "Female"),
    VoiceOption("fr-FR-EloiseNeural", "fr-FR", "Eloise", "Female"),
    VoiceOption("fr-FR-VivienneMultilingualNeural", "fr-FR", "Vivienne", "Female"),
    VoiceOption("fr-FR-HenriNeural", "fr-FR", "Henri", "Male"),
    VoiceOption("fr-FR-RemyMultilingualNeural", "fr-FR", "Remy", "Male"),
    VoiceOption("fr-CA-SylvieNeural", "fr-CA", "Sylvie", "Female"),
    VoiceOption("fr-CA-AntoineNeural", "fr-CA", "Antoine", "Male"),
    VoiceOption("fr-CA-JeanNeural", "fr-CA", "Jean", "Male"),
    VoiceOption("fr-CA-ThierryNeural", "fr-CA", "Thierry", "Male"),
    # Spanish
    VoiceOption("es-ES-ElviraNeural", "es-ES", "Elvira", "Female"),
    VoiceOption("es-ES-XimenaNeural", "es-ES", "Ximena", "Female"),
    VoiceOption("es-ES-AlvaroNeural", "es-ES", "Alvaro", "Male"),
    VoiceOption("es-MX-DaliaNeural", "es-MX", "Dalia", "Female"),
    VoiceOption("es-MX-JorgeNeural", "es-MX", "Jorge", "Male"),
    # Italian
    VoiceOption("it-IT-ElsaNeural", "it-IT", "Elsa", "Female"),
    VoiceOption("it-IT-IsabellaNeural", "it-IT", "Isabella", "Female"),
    VoiceOption("it-IT-DiegoNeural", "it-IT", "Diego", "Male"),
    VoiceOption("it-IT-GiuseppeMultilingualNeural", "it-IT", "Giuseppe", "Male"),
    # Portuguese
    VoiceOption("pt-BR-FranciscaNeural", "pt-BR", "Francisca", "Female"),
    VoiceOption("pt-BR-ThalitaMultilingualNeural", "pt-BR", "Thalita", "Female"),
    VoiceOption("pt-BR-AntonioNeural", "pt-BR", "Antonio", "Male"),
    VoiceOption("pt-PT-RaquelNeural", "pt-PT", "Raquel", "Female"),
    VoiceOption("pt-PT-DuarteNeural", "pt-PT", "Duarte", "Male"),
    # Polish
    VoiceOption("pl-PL-ZofiaNeural", "pl-PL", "Zofia", "Female"),
    VoiceOption("pl-PL-MarekNeural", "pl-PL", "Marek", "Male"),
    # Dutch
    VoiceOption("nl-NL-ColetteNeural", "nl-NL", "Colette", "Female"),
    VoiceOption("nl-NL-FennaNeural", "nl-NL", "Fenna", "Female"),
    VoiceOption("nl-NL-MaartenNeural", "nl-NL", "Maarten", "Male"),
    # Swedish
    VoiceOption("sv-SE-SofieNeural", "sv-SE", "Sofie", "Female"),
    VoiceOption("sv-SE-MattiasNeural", "sv-SE", "Mattias", "Male"),
    # Danish
    VoiceOption("da-DK-ChristelNeural", "da-DK", "Christel", "Female"),
    VoiceOption("da-DK-JeppeNeural", "da-DK", "Jeppe", "Male"),
    # Finnish
    VoiceOption("fi-FI-NooraNeural", "fi-FI", "Noora", "Female"),
    VoiceOption("fi-FI-HarriNeural", "fi-FI", "Harri", "Male"),
    # Czech
    VoiceOption("cs-CZ-VlastaNeural", "cs-CZ", "Vlasta", "Female"),
    VoiceOption("cs-CZ-AntoninNeural", "cs-CZ", "Antonin", "Male"),
    # Japanese
    VoiceOption("ja-JP-NanamiNeural", "ja-JP", "Nanami", "Female"),
    VoiceOption("ja-JP-KeitaNeural", "ja-JP", "Keita", "Male"),
    # Korean
    VoiceOption("ko-KR-SunHiNeural", "ko-KR", "Sun-Hi", "Female"),
    VoiceOption("ko-KR-InJoonNeural", "ko-KR", "InJoon", "Male"),
    VoiceOption("ko-KR-HyunsuMultilingualNeural", "ko-KR", "Hyunsu", "Male"),
    # Turkish
    VoiceOption("tr-TR-EmelNeural", "tr-TR", "Emel", "Female"),
    VoiceOption("tr-TR-AhmetNeural", "tr-TR", "Ahmet", "Male"),
    # Chinese
    VoiceOption("zh-CN-XiaoxiaoNeural", "zh-CN", "Xiaoxiao", "Female"),
    VoiceOption("zh-CN-XiaoyiNeural", "zh-CN", "Xiaoyi", "Female"),
    VoiceOption("zh-CN-YunxiNeural", "zh-CN", "Yunxi", "Male"),
    VoiceOption("zh-CN-YunjianNeural", "zh-CN", "Yunjian", "Male"),
    VoiceOption("zh-CN-YunxiaNeural", "zh-CN", "Yunxia", "Male"),
    VoiceOption("zh-CN-YunyangNeural", "zh-CN", "Yunyang", "Male"),
]

_VOICES_BY_ID = {v.voice_id: v for v in VOICES}


def get_languages() -> list[tuple[str, str]]:
    return BOOK_LANGUAGES


def get_voices_for_language(lang_code: str) -> list[tuple[str, str]]:
    locales = set(LANGUAGE_LOCALES.get(lang_code, []))
    return [
        (v.voice_id, v.label)
        for v in VOICES
        if v.locale in locales
    ]


def default_voice_for_language(lang_code: str) -> str:
    return DEFAULT_VOICE.get(lang_code, "en-US-AriaNeural")


def language_for_voice(voice_id: str) -> str:
    voice = _VOICES_BY_ID.get(voice_id)
    if not voice:
        return "en"
    for lang_code, locales in LANGUAGE_LOCALES.items():
        if voice.locale in locales:
            return lang_code
    return "en"


def is_voice_valid_for_language(voice_id: str, lang_code: str) -> bool:
    voice = _VOICES_BY_ID.get(voice_id)
    if not voice:
        return False
    return voice.locale in LANGUAGE_LOCALES.get(lang_code, [])


VOICE_PREVIEW_SAMPLES: dict[str, str] = {
    "en": (
        "Hello! This is a speech rate preview. "
        "One, two, three, four, five — listen how fast the voice reads."
    ),
    "uk": (
        "Привіт! Це перевірка швидкості мовлення. "
        "Раз, два, три, чотири, п'ять — послухайте, як швидко читає голос."
    ),
    "ru": (
        "Привет! Это проверка скорости речи. "
        "Раз, два, три, четыре, пять — послушайте, как быстро читает голос."
    ),
    "nb": (
        "Hei! Dette er en test av talehastighet. "
        "En, to, tre, fire, fem — hør hvor raskt stemmen leser."
    ),
    "de": "Hallo! Das ist eine Hörprobe der gewählten Lesestimme.",
    "fr": "Bonjour ! Voici un échantillon de la voix de lecture choisie.",
    "es": "¡Hola! Esta es una muestra de la voz de lectura seleccionada.",
    "it": "Ciao! Questo è un campione della voce di lettura selezionata.",
    "pt": "Olá! Esta é uma amostra da voz de leitura selecionada.",
    "pl": "Cześć! To próbka wybranego głosu do czytania.",
    "nl": "Hallo! Dit is een voorbeeld van de gekozen leesstem.",
    "sv": "Hej! Det här är ett exempel på den valda läsrösten.",
    "da": "Hej! Dette er et eksempel på den valgte læsestemme.",
    "fi": "Hei! Tämä on valitun lukuäänen esimerkki.",
    "cs": "Ahoj! Toto je ukázka zvoleného hlasu pro čtení.",
    "ja": "こんにちは。選択した読み上げ音声のサンプルです。",
    "ko": "안녕하세요. 선택한 읽기 음성의 샘플입니다.",
    "tr": "Merhaba! Bu, seçilen okuma sesinin bir örneğidir.",
    "zh": "你好！这是所选朗读语音的示例。",
}


def voice_preview_sample(lang_code: str) -> str:
    return VOICE_PREVIEW_SAMPLES.get(lang_code, VOICE_PREVIEW_SAMPLES["en"])


def parse_stored_voice(voice_id: str) -> tuple[str, str]:
    cleaned = (voice_id or "").strip()
    if ":" in cleaned:
        engine, raw = cleaned.split(":", 1)
        return engine, raw
    return "edge", cleaned or default_voice_for_language("en")


def format_stored_voice(engine: str, voice_id: str) -> str:
    return f"{engine}:{voice_id}"


def active_tts_engine(
    tts_mode: str, offline_engine: str, online_engine: str = "edge"
) -> str:
    if tts_mode == "online":
        return online_engine or "edge"
    if tts_mode == "offline":
        return offline_engine or "system"
    return "edge"


def _edge_voices_prefixed(lang_code: str) -> list[tuple[str, str]]:
    return [
        (format_stored_voice("edge", voice_id), f"Edge — {label}")
        for voice_id, label in get_voices_for_language(lang_code)
    ]


def _system_voices(lang_code: str) -> list[tuple[str, str]]:
    name = dict(BOOK_LANGUAGES).get(lang_code, lang_code)
    return [(format_stored_voice("system", lang_code), f"System — {name}")]


def _piper_voices(
    lang_code: str, app_dir: Path | None, piper_model_path: str
) -> list[tuple[str, str]]:
    from . import piper_tts

    if app_dir is None:
        app_dir = Path.home() / ".ai_reading_studio"
    return [
        (format_stored_voice("piper", voice_id), label)
        for voice_id, label in piper_tts.list_voices_for_language(lang_code, app_dir)
    ]


def _kokoro_voices(lang_code: str) -> list[tuple[str, str]]:
    from . import kokoro_tts

    return [
        (format_stored_voice("kokoro", voice_id), label)
        for voice_id, label in kokoro_tts.list_voices_for_language(lang_code)
    ]


def _azure_voices(lang_code: str) -> list[tuple[str, str]]:
    from . import azure_tts

    return [
        (format_stored_voice("azure", voice_id), f"Azure — {label}")
        for voice_id, label in azure_tts.list_voices_for_language(lang_code)
    ]


def _google_tts_voices(lang_code: str) -> list[tuple[str, str]]:
    from . import google_cloud_tts

    return [
        (format_stored_voice("google", voice_id), f"Google — {label}")
        for voice_id, label in google_cloud_tts.list_voices_for_language(lang_code)
    ]


def _murf_voices(lang_code: str, murf_api_key: str = "") -> list[tuple[str, str]]:
    from . import murf_tts

    return [
        (format_stored_voice("murf", voice_id), f"Murf — {label}")
        for voice_id, label in murf_tts.list_voices_for_language(
            lang_code, murf_api_key
        )
    ]


def _cartesia_voices(lang_code: str, cartesia_api_key: str = "") -> list[tuple[str, str]]:
    from . import cartesia_tts

    return [
        (format_stored_voice("cartesia", voice_id), f"Cartesia — {label}")
        for voice_id, label in cartesia_tts.list_voices_for_language(
            lang_code, cartesia_api_key
        )
    ]


def _elevenlabs_voices(lang_code: str, elevenlabs_api_key: str = "") -> list[tuple[str, str]]:
    from . import elevenlabs_tts

    return [
        (format_stored_voice("elevenlabs", voice_id), f"ElevenLabs — {label}")
        for voice_id, label in elevenlabs_tts.list_voices_for_language(
            lang_code, elevenlabs_api_key
        )
    ]


def _xtts_voices(lang_code: str, app_dir: Path | None) -> list[tuple[str, str]]:
    from . import xtts_tts

    if app_dir is None:
        app_dir = Path.home() / ".ai_reading_studio"
    return [
        (format_stored_voice("xtts", voice_id), label)
        for voice_id, label in xtts_tts.list_voices_for_language(lang_code, app_dir)
    ]


def _styletts2_voices(
    lang_code: str, app_dir: Path | None, styletts2_model_path: str
) -> list[tuple[str, str]]:
    from . import styletts2_tts

    if app_dir is None:
        app_dir = Path.home() / ".ai_reading_studio"
    return [
        (format_stored_voice("styletts2", voice_id), label)
        for voice_id, label in styletts2_tts.list_voices_for_language(
            lang_code, app_dir, styletts2_model_path
        )
    ]


def get_voices_for_tts_context(
    lang_code: str,
    tts_mode: str,
    offline_engine: str,
    *,
    online_engine: str = "edge",
    app_dir: Path | None = None,
    piper_model_path: str = "",
    styletts2_model_path: str = "",
    elevenlabs_api_key: str = "",
    cartesia_api_key: str = "",
    murf_api_key: str = "",
) -> list[tuple[str, str]]:
    engine = active_tts_engine(tts_mode, offline_engine, online_engine)
    if engine == "edge":
        return _edge_voices_prefixed(lang_code)
    if engine == "azure":
        return _azure_voices(lang_code)
    if engine == "google":
        return _google_tts_voices(lang_code)
    if engine == "elevenlabs":
        return _elevenlabs_voices(lang_code, elevenlabs_api_key)
    if engine == "cartesia":
        return _cartesia_voices(lang_code, cartesia_api_key)
    if engine == "murf":
        return _murf_voices(lang_code, murf_api_key)
    if engine == "system":
        return _system_voices(lang_code)
    if engine == "piper":
        return _piper_voices(lang_code, app_dir, piper_model_path)
    if engine == "kokoro":
        return _kokoro_voices(lang_code)
    if engine == "xtts":
        return _xtts_voices(lang_code, app_dir)
    if engine == "styletts2":
        return _styletts2_voices(lang_code, app_dir, styletts2_model_path)
    return _edge_voices_prefixed(lang_code)


def default_voice_for_tts_context(
    lang_code: str,
    tts_mode: str,
    offline_engine: str,
    *,
    online_engine: str = "edge",
    app_dir: Path | None = None,
    piper_model_path: str = "",
    styletts2_model_path: str = "",
    elevenlabs_api_key: str = "",
    cartesia_api_key: str = "",
    murf_api_key: str = "",
) -> str:
    voices = get_voices_for_tts_context(
        lang_code,
        tts_mode,
        offline_engine,
        online_engine=online_engine,
        app_dir=app_dir,
        piper_model_path=piper_model_path,
        styletts2_model_path=styletts2_model_path,
        elevenlabs_api_key=elevenlabs_api_key,
        cartesia_api_key=cartesia_api_key,
        murf_api_key=murf_api_key,
    )
    if voices:
        return voices[0][0]
    return format_stored_voice("edge", default_voice_for_language(lang_code))


def is_voice_valid_for_tts_context(
    voice_id: str,
    lang_code: str,
    tts_mode: str,
    offline_engine: str,
    *,
    online_engine: str = "edge",
    app_dir: Path | None = None,
    piper_model_path: str = "",
    styletts2_model_path: str = "",
    elevenlabs_api_key: str = "",
    cartesia_api_key: str = "",
    murf_api_key: str = "",
) -> bool:
    engine, _raw = parse_stored_voice(voice_id)
    expected = active_tts_engine(tts_mode, offline_engine, online_engine)
    if engine != expected:
        return False
    valid_ids = {
        stored
        for stored, _label in get_voices_for_tts_context(
            lang_code,
            tts_mode,
            offline_engine,
            online_engine=online_engine,
            app_dir=app_dir,
            piper_model_path=piper_model_path,
            styletts2_model_path=styletts2_model_path,
            elevenlabs_api_key=elevenlabs_api_key,
            cartesia_api_key=cartesia_api_key,
            murf_api_key=murf_api_key,
        )
    }
    return voice_id in valid_ids


def language_for_stored_voice(voice_id: str) -> str:
    engine, raw = parse_stored_voice(voice_id)
    if engine == "edge":
        return language_for_voice(raw)
    if engine == "system":
        return raw or "en"
    if engine == "piper":
        from . import piper_tts

        if raw:
            for model_stem, _path in piper_tts.list_models(
                Path.home() / ".ai_reading_studio"
            ):
                if model_stem == raw:
                    if raw.startswith("en_"):
                        return "en"
                    prefix = raw.split("_", 1)[0]
                    if len(prefix) == 2:
                        return prefix
        for lang, hint in piper_tts.MODEL_HINTS.items():
            if hint.startswith(raw) or raw in hint:
                return lang
        return "en"
    if engine == "kokoro":
        from . import kokoro_tts

        for voice_id_def, _lang, _name, langs in kokoro_tts.KOKORO_VOICE_DEFS:
            if voice_id_def == raw and langs:
                return langs[0]
        return "en"
    if engine == "azure":
        from . import azure_tts

        for lang, voices in azure_tts.VOICES_BY_LANG.items():
            if any(v[0] == raw for v in voices):
                return lang
        return "en"
    if engine == "google":
        from . import google_cloud_tts

        for lang, voices in google_cloud_tts.VOICES_BY_LANG.items():
            if any(v[0] == raw for v in voices):
                return lang
        return "en"
    if engine == "elevenlabs":
        return "en"
    if engine == "cartesia":
        from . import cartesia_tts

        return cartesia_tts.iso_language(raw) or "en"
    if engine == "murf":
        from . import murf_tts

        locale = murf_tts.locale_for_lang(raw if raw in murf_tts.BOOK_TO_LOCALE else "en")
        return locale.split("-")[0] if locale else "en"
    if engine == "xtts":
        return raw if raw in dict(BOOK_LANGUAGES) else "en"
    if engine == "styletts2":
        return "en"
    return "en"
