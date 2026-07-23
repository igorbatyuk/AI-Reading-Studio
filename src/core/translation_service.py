"""Translation for words and sentences (configurable source → target language)."""

from __future__ import annotations

import logging
import re
import threading
import time
from dataclasses import dataclass
from html import unescape
from urllib.parse import quote

import requests
from PySide6.QtCore import QObject, Signal

from . import apify_translate
from . import bergamot_translate
from . import deepl_translate
from . import ollama_client

logger = logging.getLogger(__name__)

LANG_NAMES: dict[str, str] = {
    "en": "English",
    "uk": "Ukrainian",
    "ru": "Russian",
    "de": "German",
    "fr": "French",
    "es": "Spanish",
    "pl": "Polish",
    "nb": "Norwegian",
    "it": "Italian",
    "pt": "Portuguese",
    "nl": "Dutch",
    "sv": "Swedish",
    "da": "Danish",
    "fi": "Finnish",
    "cs": "Czech",
    "ja": "Japanese",
    "ko": "Korean",
    "zh": "Chinese",
}


@dataclass
class WordTranslation:
    word: str
    translation: str
    contextual: str
    phonetic: str
    part_of_speech: str
    definition: str


class _TranslationBridge(QObject):
    word_ready = Signal(object, object)
    activity_changed = Signal()


class TranslationService:
    DICT_API = "https://api.dictionaryapi.dev/api/v2/entries/en/{word}"
    PROVIDERS = ("auto", "free", "openai", "bergamot", "ollama", "apify", "google", "deepl")

    @classmethod
    def _normalize_provider(cls, provider: str | None, default: str = "auto") -> str:
        if not provider:
            return default
        return provider if provider in cls.PROVIDERS else default

    def __init__(
        self,
        api_key: str = "",
        source_lang: str = "en",
        target_lang: str = "uk",
        provider: str = "auto",
        ollama_url: str = ollama_client.DEFAULT_URL,
        ollama_model: str = "",
        apify_api_token: str = "",
        google_api_key: str = "",
        deepl_api_key: str = "",
        block_provider: str | None = None,
        word_provider: str | None = None,
        selection_provider: str | None = None,
        apify_usage: object | None = None,
        google_usage: object | None = None,
        deepl_usage: object | None = None,
    ) -> None:
        self.api_key = api_key
        self.apify_api_token = apify_api_token or ""
        self.google_api_key = google_api_key or ""
        self.deepl_api_key = deepl_api_key or ""
        self._apify_usage = apify_usage
        self._google_usage = google_usage
        self._deepl_usage = deepl_usage
        self.source_lang = source_lang or "en"
        self.target_lang = target_lang or "uk"
        legacy = self._normalize_provider(provider, "auto")
        self.block_provider = self._normalize_provider(block_provider, legacy)
        self.word_provider = self._normalize_provider(word_provider, "free")
        self.selection_provider = self._normalize_provider(
            selection_provider, "apify"
        )
        self.ollama_url = ollama_client.normalize_url(ollama_url)
        self.ollama_model = ollama_model or ""
        self.last_error = ""
        self._bridge = _TranslationBridge()
        self._bridge.word_ready.connect(self._deliver_word)
        self._sentence_cache: dict[str, str] = {}
        self._word_cache: dict[str, WordTranslation] = {}
        self._pending_words = 0
        self._pending_sentences = 0
        self._last_activity = ""
        self._word_prefetch_by_sentence: dict[int, int] = {}
        self._ollama_available: bool | None = None
        self._ollama_checked_at = 0.0
        self._bergamot_available: bool | None = None
        self._bergamot_checked_at = 0.0
        self._bergamot_pair: tuple[str, str] | None = None

    def pending_tasks(self) -> int:
        return self._pending_words + self._pending_sentences

    def cache_stats(self) -> tuple[int, int]:
        return len(self._word_cache), len(self._sentence_cache)

    def last_activity(self) -> str:
        return self._last_activity

    def provider_label(self, scope: str = "block") -> str:
        from .i18n import tr

        key = {
            "block": self.block_provider,
            "word": self.word_provider,
            "selection": self.selection_provider,
        }.get(scope, self.block_provider)
        return tr(f"settings.translation_engine.{key}")

    def is_sentence_cached(self, text: str) -> bool:
        text = text.strip()
        if not text:
            return True
        if self.source_lang == self.target_lang:
            return True
        cache_key = (
            f"block:{self.block_provider}:{self.source_lang}:"
            f"{self.target_lang}:{text}"
        )
        return cache_key in self._sentence_cache

    def prefetch_sentence(self, text: str) -> None:
        text = text.strip()
        if not text or self.is_sentence_cached(text):
            return
        threading.Thread(
            target=self._prefetch_sentence_worker,
            args=(text,),
            daemon=True,
        ).start()

    def _prefetch_sentence_worker(self, text: str) -> None:
        if self.is_sentence_cached(text):
            return
        self.translate_sentence(text)

    def _word_cache_key(self, word: str, sentence: str) -> str:
        clean = clean_lookup_word(word)
        return (
            f"word:{self.word_provider}:{self.source_lang}:{self.target_lang}:"
            f"{clean}:{hash(sentence.strip()) & 0xFFFF}"
        )

    def is_word_cached(self, word: str, sentence: str) -> bool:
        if not clean_lookup_word(word):
            return True
        return self._word_cache_key(word, sentence) in self._word_cache

    def prefetch_words(self, sentence: str, max_words: int = 25) -> None:
        sentence = sentence.strip()
        if not sentence or self.source_lang == self.target_lang:
            return
        words = extract_lookup_words(sentence)[:max_words]
        if not words:
            return
        sentence_id = hash(sentence)
        generation = self._word_prefetch_by_sentence.get(sentence_id, 0) + 1
        self._word_prefetch_by_sentence[sentence_id] = generation
        threading.Thread(
            target=self._prefetch_words_worker,
            args=(sentence, words, sentence_id, generation),
            daemon=True,
        ).start()

    def _prefetch_words_worker(
        self, sentence: str, words: list[str], sentence_id: int, generation: int
    ) -> None:
        pending = sum(
            1 for word in words if not self.is_word_cached(word, sentence)
        )
        if pending <= 0:
            return
        self._pending_words += pending
        self._bridge.activity_changed.emit()
        try:
            for word in words:
                if self._word_prefetch_by_sentence.get(sentence_id) != generation:
                    return
                if self.is_word_cached(word, sentence):
                    continue
                cache_key = self._word_cache_key(word, sentence)
                try:
                    clean = clean_lookup_word(word)
                    info = self._fetch_word(clean, sentence)
                    if self._word_prefetch_by_sentence.get(sentence_id) != generation:
                        return
                    if info.translation:
                        self._word_cache[cache_key] = info
                except Exception as exc:
                    logger.debug("Word prefetch failed for %r: %s", word, exc)
        finally:
            self._pending_words = max(0, self._pending_words - pending)
            self._bridge.activity_changed.emit()

    @property
    def activity_changed(self):
        return self._bridge.activity_changed

    def set_api_key(self, api_key: str) -> None:
        self.api_key = api_key

    def set_apify_api_token(self, token: str) -> None:
        self.apify_api_token = token or ""

    def set_google_api_key(self, google_api_key: str) -> None:
        self.google_api_key = google_api_key or ""

    def set_deepl_api_key(self, deepl_api_key: str) -> None:
        self.deepl_api_key = deepl_api_key or ""

    def set_apify_usage_tracker(self, tracker: object | None) -> None:
        self._apify_usage = tracker

    def set_google_usage_tracker(self, tracker: object | None) -> None:
        self._google_usage = tracker

    def set_deepl_usage_tracker(self, tracker: object | None) -> None:
        self._deepl_usage = tracker

    def set_languages(self, source_lang: str, target_lang: str) -> None:
        new_source = source_lang or "en"
        new_target = target_lang or "uk"
        if new_source != self.source_lang or new_target != self.target_lang:
            self._sentence_cache.clear()
            self._word_cache.clear()
            self._word_prefetch_by_sentence.clear()
            self.invalidate_bergamot_cache()
        self.source_lang = new_source
        self.target_lang = new_target

    @property
    def provider(self) -> str:
        return self.block_provider

    @provider.setter
    def provider(self, value: str) -> None:
        self.set_block_provider(value)

    def set_block_provider(self, provider: str) -> None:
        self._set_provider("block_provider", provider)

    def set_word_provider(self, provider: str) -> None:
        self._set_provider("word_provider", provider)

    def set_selection_provider(self, provider: str) -> None:
        self._set_provider("selection_provider", provider)

    def set_provider(self, provider: str) -> None:
        self.set_block_provider(provider)

    def set_providers(self, block: str, word: str, selection: str) -> None:
        changed = False
        for attr, value in (
            ("block_provider", block),
            ("word_provider", word),
            ("selection_provider", selection),
        ):
            cleaned = self._normalize_provider(value, getattr(self, attr))
            if cleaned != getattr(self, attr):
                setattr(self, attr, cleaned)
                changed = True
        if changed:
            self._clear_translation_cache()

    def _set_provider(self, attr: str, provider: str) -> None:
        value = self._normalize_provider(provider, getattr(self, attr))
        if value != getattr(self, attr):
            setattr(self, attr, value)
            self._clear_translation_cache()

    def _clear_translation_cache(self) -> None:
        self._sentence_cache.clear()
        self._word_cache.clear()
        self._word_prefetch_by_sentence.clear()
        self._ollama_available = None
        self.invalidate_bergamot_cache()

    def clear_cache(self) -> None:
        self._clear_translation_cache()

    def set_ollama(self, url: str, model: str) -> None:
        new_url = ollama_client.normalize_url(url)
        new_model = (model or "").strip()
        if new_url != self.ollama_url or new_model != self.ollama_model:
            self._sentence_cache.clear()
            self._word_cache.clear()
            self._word_prefetch_by_sentence.clear()
            self._ollama_available = None
        self.ollama_url = new_url
        self.ollama_model = new_model

    def can_use_bergamot(self, *, use_cache: bool = True) -> bool:
        pair = (self.source_lang, self.target_lang)
        now = time.monotonic()
        if (
            use_cache
            and self._bergamot_available is not None
            and self._bergamot_pair == pair
            and now - self._bergamot_checked_at < 60.0
        ):
            return self._bergamot_available
        self._bergamot_available = bergamot_translate.is_available(
            self.source_lang, self.target_lang
        )
        self._bergamot_pair = pair
        self._bergamot_checked_at = now
        return self._bergamot_available

    def invalidate_bergamot_cache(self) -> None:
        self._bergamot_available = None
        self._bergamot_checked_at = 0.0
        self._bergamot_pair = None

    def can_use_ollama(self, *, use_cache: bool = True) -> bool:
        if self.block_provider == "free" and self.word_provider == "free":
            if self.selection_provider == "free":
                return False
        now = time.monotonic()
        if (
            use_cache
            and self._ollama_available is not None
            and now - self._ollama_checked_at < 30.0
        ):
            return self._ollama_available
        self._ollama_available = ollama_client.is_available(self.ollama_url)
        self._ollama_checked_at = now
        return self._ollama_available

    def invalidate_network_cache(self) -> None:
        self._ollama_available = None
        self._ollama_checked_at = 0.0
        self._bergamot_available = None
        self._bergamot_checked_at = 0.0
        self._bergamot_pair = None

    def has_ai_backend(self) -> bool:
        providers = {
            self.block_provider,
            self.word_provider,
            self.selection_provider,
        }
        if providers == {"free"}:
            return False
        if "openai" in providers and self.api_key:
            return True
        if "apify" in providers and self.apify_api_token:
            return True
        if "google" in providers and self.google_api_key:
            return True
        if "deepl" in providers and self.deepl_api_key:
            return True
        if "bergamot" in providers and self.can_use_bergamot():
            return True
        if "ollama" in providers and self.can_use_ollama():
            return True
        if "auto" in providers:
            return (
                bool(self.api_key)
                or bool(self.apify_api_token)
                or bool(self.google_api_key)
                or bool(self.deepl_api_key)
                or self.can_use_bergamot()
                or self.can_use_ollama()
            )
        return False

    def translate_selection(self, text: str) -> str:
        return self._translate_with_provider(
            text, self.selection_provider, scope="selection"
        )

    def translate_with_apify(self, text: str) -> str:
        return self.translate_selection(text)

    def translate_with_google(self, text: str) -> str:
        return self._translate_with_provider(text, "google", scope="selection")

    def translate_with_deepl(self, text: str) -> str:
        return self._translate_with_provider(text, "deepl", scope="selection")

    def translate_sentence(self, text: str) -> str:
        return self._translate_with_provider(
            text, self.block_provider, scope="block"
        )

    def _translate_with_provider(
        self, text: str, provider: str, *, scope: str
    ) -> str:
        text = text.strip()
        if not text:
            return ""
        if self.source_lang == self.target_lang:
            return text

        cache_key = (
            f"{scope}:{provider}:{self.source_lang}:{self.target_lang}:{text}"
        )
        if cache_key in self._sentence_cache:
            return self._sentence_cache[cache_key]

        self.last_error = ""
        self._last_activity = f"{scope} ({len(text.split())} words)"
        self._pending_sentences += 1
        self._bridge.activity_changed.emit()
        result = ""
        try:
            for method in self._provider_chain(provider):
                result = method(text)
                if result:
                    break

            if result:
                self._sentence_cache[cache_key] = result
            elif not self.last_error:
                self.last_error = "All translation providers failed"
            return result
        finally:
            self._pending_sentences = max(0, self._pending_sentences - 1)
            self._bridge.activity_changed.emit()

    def lookup_word(self, word: str, sentence: str, callback: callable) -> None:
        clean = clean_lookup_word(word)
        if not clean:
            callback(None)
            return

        cache_key = self._word_cache_key(word, sentence)
        if cache_key in self._word_cache:
            self._last_activity = f"word: {clean} (cache)"
            self._bridge.activity_changed.emit()
            callback(self._word_cache[cache_key])
            return

        self._last_activity = f"word: {clean}"
        self._pending_words += 1
        self._bridge.activity_changed.emit()
        threading.Thread(
            target=self._lookup_worker,
            args=(clean, sentence, cache_key, callback),
            daemon=True,
        ).start()

    def _deliver_word(self, callback: callable, info: WordTranslation | None) -> None:
        callback(info)

    def _lookup_worker(
        self, word: str, sentence: str, cache_key: str, callback: callable
    ) -> None:
        try:
            info = self._fetch_word(word, sentence)
            self._word_cache[cache_key] = info
            self._bridge.word_ready.emit(callback, info)
        except Exception as exc:
            logger.warning("Word lookup failed for %r: %s", word, exc)
            self.last_error = str(exc)
            self._bridge.word_ready.emit(
                callback,
                WordTranslation(word, "", "", "", "", ""),
            )
        finally:
            self._pending_words = max(0, self._pending_words - 1)
            self._bridge.activity_changed.emit()

    def _provider_chain(self, provider: str) -> list:
        provider = self._normalize_provider(provider, "auto")
        chain: list = []
        if provider in ("auto", "openai") and self.api_key:
            chain.append(self._translate_openai_sentence)
        if provider in ("auto", "apify") and self.apify_api_token:
            chain.append(self._translate_apify)
        if provider in ("auto", "google") and self.google_api_key:
            chain.append(self._translate_google_api)
        if provider in ("auto", "deepl") and self.deepl_api_key:
            chain.append(self._translate_deepl)
        if provider == "bergamot":
            chain.append(self._translate_bergamot_sentence)
            chain.append(self._translate_ollama_sentence)
            return chain
        if provider == "auto":
            chain.append(self._translate_bergamot_sentence)
        if provider in ("auto", "ollama"):
            chain.append(self._translate_ollama_sentence)
        if provider == "apify":
            if not self.apify_api_token:
                chain.extend(self._free_provider_chain())
            return chain
        if provider == "google":
            if not self.google_api_key:
                chain.extend(self._free_provider_chain())
            return chain
        if provider == "deepl":
            if not self.deepl_api_key:
                chain.extend(self._free_provider_chain())
            return chain
        if provider in ("auto", "free", "openai", "ollama"):
            chain.extend(self._free_provider_chain())
        return chain

    def _sentence_provider_chain(self) -> list:
        return self._provider_chain(self.block_provider)

    def _free_provider_chain(self) -> list:
        if self.source_lang == self.target_lang:
            return []
        return [
            self._translate_google_free,
            self._translate_lingva,
            self._translate_mymemory,
        ]

    def _word_provider_chain(self) -> list:
        provider = self._normalize_provider(self.word_provider, "free")
        if provider == "apify" and self.apify_api_token:
            return [self._translate_apify, self._translate_google_free]
        if provider == "google" and self.google_api_key:
            return [self._translate_google_api, self._translate_google_free]
        if provider == "deepl" and self.deepl_api_key:
            return [self._translate_deepl, self._translate_google_free]
        if provider in ("auto", "openai", "bergamot", "ollama", "apify", "google", "deepl"):
            return self._provider_chain(provider)
        if provider == "apify" and not self.apify_api_token:
            return self._free_provider_chain()
        if provider == "google" and not self.google_api_key:
            return self._free_provider_chain()
        if provider == "deepl" and not self.deepl_api_key:
            return self._free_provider_chain()
        if provider == "free":
            return self._free_provider_chain()
        return self._provider_chain(provider)

    def _translate_free(self, text: str) -> str:
        for method in self._free_provider_chain():
            result = method(text)
            if result:
                return result
        return ""

    def _cached_sentence_translation(self, sentence: str) -> str:
        sentence = sentence.strip()
        if not sentence:
            return ""
        if self.source_lang == self.target_lang:
            return sentence
        cache_key = (
            f"block:{self.block_provider}:{self.source_lang}:"
            f"{self.target_lang}:{sentence}"
        )
        return self._sentence_cache.get(cache_key, "")

    def _fetch_word(self, word: str, sentence: str) -> WordTranslation:
        translation = ""
        for method in self._word_provider_chain():
            translation = method(word)
            if translation:
                break
        if not translation:
            for candidate in self._word_variants(word):
                if candidate == word:
                    continue
                for method in self._word_provider_chain():
                    translation = method(candidate)
                    if translation:
                        break
                if translation:
                    break

        return WordTranslation(
            word=word,
            translation=translation,
            contextual="",
            phonetic="",
            part_of_speech="",
            definition="",
        )

    def _lang_label(self, code: str) -> str:
        return LANG_NAMES.get(code, code)

    def _translate_word_in_context(self, word: str, sentence: str) -> str:
        provider = self.word_provider
        if provider in ("auto", "openai") and self.api_key:
            result = self._translate_openai_word_in_context(word, sentence)
            if result:
                return result
        if provider in ("auto", "ollama") and self.can_use_ollama():
            return self._translate_ollama_word_in_context(word, sentence)
        if provider in ("auto", "bergamot") and self.can_use_bergamot():
            return self._translate_bergamot_sentence(word)
        return ""

    def _translate_openai_word_in_context(self, word: str, sentence: str) -> str:
        src = self._lang_label(self.source_lang)
        tgt = self._lang_label(self.target_lang)
        try:
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "gpt-4o-mini",
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                f"You help language learners. Given a {src} word and "
                                f"the sentence it appears in, return ONLY the {tgt} "
                                "translation of that word as used in this sentence. "
                                "One short phrase, no explanation."
                            ),
                        },
                        {
                            "role": "user",
                            "content": f"Word: {word}\nSentence: {sentence}",
                        },
                    ],
                    "temperature": 0.2,
                },
                timeout=15,
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"].strip()
        except Exception as exc:
            logger.warning("OpenAI word context translation failed: %s", exc)
            self.last_error = str(exc)
            return ""

    def _translate_ollama_word_in_context(self, word: str, sentence: str) -> str:
        src = self._lang_label(self.source_lang)
        tgt = self._lang_label(self.target_lang)
        try:
            return ollama_client.chat(
                self.ollama_url,
                self.ollama_model,
                (
                    f"You help language learners. Given a {src} word and the sentence "
                    f"it appears in, return ONLY the {tgt} translation of that word as "
                    "used in this sentence. One short phrase, no explanation."
                ),
                f"Word: {word}\nSentence: {sentence}",
                timeout=45,
            )
        except Exception as exc:
            logger.warning("Ollama word context translation failed: %s", exc)
            self.last_error = str(exc)
            return ""

    def _translate_openai_word(self, text: str) -> str:
        return self._translate_openai_sentence(text)

    def _translate_ollama_word(self, text: str) -> str:
        return self._translate_ollama_sentence(text)

    def _translate_openai_gloss(self, word: str) -> str:
        src = self._lang_label(self.source_lang)
        tgt = self._lang_label(self.target_lang)
        try:
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "gpt-4o-mini",
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                f"Give a very short {tgt} gloss (one line) for the "
                                f"{src} word. No extra text."
                            ),
                        },
                        {"role": "user", "content": word},
                    ],
                    "temperature": 0.2,
                },
                timeout=15,
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"].strip()
        except Exception as exc:
            logger.debug("OpenAI gloss failed: %s", exc)
            return ""

    def _translate_ollama_gloss(self, word: str) -> str:
        src = self._lang_label(self.source_lang)
        tgt = self._lang_label(self.target_lang)
        try:
            return ollama_client.chat(
                self.ollama_url,
                self.ollama_model,
                (
                    f"Give a very short {tgt} gloss (one line) for the {src} word. "
                    "No extra text."
                ),
                word,
                timeout=45,
            )
        except Exception as exc:
            logger.debug("Ollama gloss failed: %s", exc)
            return ""

    def _translate_openai_sentence(self, text: str) -> str:
        src = self._lang_label(self.source_lang)
        tgt = self._lang_label(self.target_lang)
        try:
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "gpt-4o-mini",
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                f"Translate {src} to natural, fluent {tgt}. "
                                "Preserve tone and meaning of literary text. "
                                f"Return ONLY the {tgt} translation."
                            ),
                        },
                        {"role": "user", "content": text},
                    ],
                    "temperature": 0.2,
                },
                timeout=20,
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"].strip()
        except Exception as exc:
            logger.warning("OpenAI sentence translation failed: %s", exc)
            self.last_error = str(exc)
            return ""

    def _translate_bergamot_sentence(self, text: str) -> str:
        if not self.can_use_bergamot():
            return ""
        try:
            return bergamot_translate.translate(
                text, self.source_lang, self.target_lang
            )
        except Exception as exc:
            logger.warning("Bergamot translation failed: %s", exc)
            self.last_error = str(exc)
            return ""

    def _translate_ollama_sentence(self, text: str) -> str:
        if not self.can_use_ollama():
            return ""
        src = self._lang_label(self.source_lang)
        tgt = self._lang_label(self.target_lang)
        try:
            return ollama_client.chat(
                self.ollama_url,
                self.ollama_model,
                (
                    f"Translate {src} to natural, fluent {tgt}. Preserve tone and "
                    f"meaning of literary text. Return ONLY the {tgt} translation."
                ),
                text,
                timeout=90,
            )
        except Exception as exc:
            logger.warning("Ollama sentence translation failed: %s", exc)
            self.last_error = str(exc)
            return ""

    def _translate_apify(self, text: str) -> str:
        if not self.apify_api_token or self.source_lang == self.target_lang:
            return ""
        result, error = apify_translate.translate_text(
            text,
            token=self.apify_api_token,
            source_lang=self.source_lang,
            target_lang=self.target_lang,
        )
        if error:
            self.last_error = error
            return ""
        if result and self._is_valid_translation(text, result):
            if self._apify_usage is not None:
                try:
                    self._apify_usage.record(len(text))
                except Exception as exc:
                    logger.debug("Apify usage tracking failed: %s", exc)
            return result
        if not self.last_error:
            self.last_error = "Apify translation failed"
        return ""

    def _translate_google_api(self, text: str) -> str:
        if not self.google_api_key or self.source_lang == self.target_lang:
            return ""
        try:
            resp = requests.post(
                "https://translation.googleapis.com/language/translate/v2",
                params={"key": self.google_api_key},
                data={
                    "q": text,
                    "source": self.source_lang,
                    "target": self.target_lang,
                    "format": "text",
                },
                timeout=30,
            )
        except requests.RequestException as exc:
            logger.warning("Google Cloud translation request failed: %s", exc)
            self.last_error = str(exc)
            return ""

        if resp.status_code != 200:
            detail = resp.text[:300]
            try:
                payload = resp.json()
                detail = payload.get("error", {}).get("message", detail)
            except Exception:
                pass
            self.last_error = f"Google Cloud HTTP {resp.status_code}: {detail}"
            return ""

        try:
            payload = resp.json()
            result = unescape(
                payload["data"]["translations"][0]["translatedText"]
            ).strip()
        except (ValueError, KeyError, IndexError) as exc:
            self.last_error = f"Invalid Google Cloud response: {exc}"
            return ""

        if result and self._is_valid_translation(text, result):
            if self._google_usage is not None:
                try:
                    self._google_usage.record(len(text))
                except Exception as exc:
                    logger.debug("Google usage tracking failed: %s", exc)
            return result
        if not self.last_error:
            self.last_error = "Google Cloud translation failed"
        return ""

    def _translate_deepl(self, text: str) -> str:
        if not self.deepl_api_key or self.source_lang == self.target_lang:
            return ""
        result, error = deepl_translate.translate_text(
            text,
            api_key=self.deepl_api_key,
            source_lang=self.source_lang,
            target_lang=self.target_lang,
        )
        if error:
            self.last_error = error
            return ""
        if result and self._is_valid_translation(text, result):
            if self._deepl_usage is not None:
                try:
                    self._deepl_usage.record(len(text))
                except Exception as exc:
                    logger.debug("DeepL usage tracking failed: %s", exc)
            return result
        if not self.last_error:
            self.last_error = "DeepL translation failed"
        return ""

    def _translate_google_free(self, text: str) -> str:
        if self.source_lang == self.target_lang:
            return text
        try:
            from deep_translator import GoogleTranslator

            result = GoogleTranslator(
                source=self.source_lang, target=self.target_lang
            ).translate(text)
            if result and self._is_valid_translation(text, result):
                return result
        except Exception as exc:
            logger.debug("Google translation failed: %s", exc)
            self.last_error = str(exc)
        return ""

    def _translate_lingva(self, text: str) -> str:
        if self.source_lang == self.target_lang:
            return text
        try:
            url = (
                f"https://lingva.ml/api/v1/{self.source_lang}/"
                f"{self.target_lang}/{quote(text, safe='')}"
            )
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                result = resp.json().get("translation", "")
                if result and self._is_valid_translation(text, result):
                    return result
        except Exception as exc:
            logger.debug("Lingva translation failed: %s", exc)
            self.last_error = str(exc)
        return ""

    def _translate_mymemory(self, text: str) -> str:
        if self.source_lang == self.target_lang:
            return text
        try:
            pair = f"{self.source_lang}|{self.target_lang}"
            url = (
                "https://api.mymemory.translated.net/get"
                f"?q={quote(text)}&langpair={pair}"
            )
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                result = resp.json().get("responseData", {}).get("translatedText", "")
                if result and self._is_valid_translation(text, result):
                    return result
        except Exception as exc:
            logger.debug("MyMemory translation failed: %s", exc)
            self.last_error = str(exc)
        return ""

    @staticmethod
    def _is_valid_translation(source: str, result: str) -> bool:
        if not result:
            return False
        if source.strip().lower() == result.strip().lower():
            return False
        return True

    @staticmethod
    def _word_variants(word: str) -> list[str]:
        variants = [word]
        if word.endswith("'s"):
            variants.append(word[:-2])
        if word.endswith("ed") and len(word) > 4:
            base = word[:-2]
            variants.append(base)
            if len(word) > 3 and word[-3] == word[-4]:
                variants.append(word[:-3])
        if word.endswith("ing") and len(word) > 5:
            base = word[:-3]
            variants.append(base)
            variants.append(base + "e")
        if word.endswith("s") and len(word) > 3 and not word.endswith("ss"):
            variants.append(word[:-1])
        if word.endswith("ies"):
            variants.append(word[:-3] + "y")
        seen: set[str] = set()
        result: list[str] = []
        for v in variants:
            if v not in seen:
                seen.add(v)
                result.append(v)
        return result


def extract_lookup_words(text: str) -> list[str]:
    """Unique clickable words from block text, in reading order."""
    seen: set[str] = set()
    result: list[str] = []
    pattern = (
        r"[\u3040-\u30ff\u31f0-\u31ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff"
        r"\uac00-\ud7af\u0e00-\u0e7f]+"
        r"|[\w'-]+"
    )
    for match in re.finditer(pattern, text, flags=re.UNICODE):
        raw = match.group(0)
        if not is_lookup_word(raw):
            continue
        clean = clean_lookup_word(raw)
        if clean in seen:
            continue
        seen.add(clean)
        result.append(clean)
    return result


def clean_lookup_word(word: str) -> str:
    if _contains_cjk_or_thai(word):
        return word.strip()
    cleaned = re.sub(r"[^\w'-]", "", word, flags=re.UNICODE)
    return cleaned.strip("'").lower()


def is_lookup_word(word: str) -> bool:
    if _contains_cjk_or_thai(word):
        return len(word.strip()) >= 1
    cleaned = clean_lookup_word(word)
    if len(cleaned) < 1:
        return False
    return bool(re.search(r"[\w]", cleaned, flags=re.UNICODE))


def _contains_cjk_or_thai(word: str) -> bool:
    return bool(
        re.search(
            r"[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff"
            r"\uac00-\ud7af\u0e00-\u0e7f]",
            word,
        )
    )
