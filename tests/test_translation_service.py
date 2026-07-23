"""Tests for translation helpers."""

from src.core.translation_service import (
    TranslationService,
    WordTranslation,
    clean_lookup_word,
    extract_lookup_words,
    is_lookup_word,
)


def test_clean_lookup_word_strips_punctuation():
    assert clean_lookup_word("«Hello»,") == "hello"
    assert clean_lookup_word("слово.") == "слово"


def test_is_lookup_word_accepts_cyrillic():
    assert is_lookup_word("привіт") is True
    assert is_lookup_word("...") is False


def test_same_language_returns_source_text():
    service = TranslationService(source_lang="uk", target_lang="uk", provider="free")
    assert service.translate_sentence("Тестове речення") == "Тестове речення"


def test_provider_free_skips_ollama(monkeypatch):
    service = TranslationService(provider="free", ollama_model="llama3.2")

    def _should_not_run(text: str) -> str:
        raise AssertionError("Ollama should not be called in free mode")

    monkeypatch.setattr(service, "_translate_ollama_sentence", _should_not_run)
    monkeypatch.setattr(service, "_translate_google_free", lambda text: "translated")
    assert service.translate_sentence("hello") == "translated"


def test_can_use_ollama_respects_provider(monkeypatch):
    service = TranslationService(provider="ollama")
    monkeypatch.setattr(
        "src.core.translation_service.ollama_client.is_available", lambda url: True
    )
    assert service.can_use_ollama() is True

    service.set_providers("free", "free", "free")
    assert service.can_use_ollama() is False


def test_word_provider_chain_is_free_only():
    service = TranslationService(provider="auto", ollama_model="llama3.2")
    chain = service._word_provider_chain()
    assert chain == service._free_provider_chain()
    assert service._translate_google_free in chain
    assert service._translate_ollama_sentence not in chain


def test_extract_lookup_words_unique():
    text = "Hello hello world, and world again."
    words = extract_lookup_words(text)
    assert words == ["hello", "world", "and", "again"]


def test_translate_with_apify_uses_free_fallback(monkeypatch):
    service = TranslationService(
        source_lang="en",
        target_lang="uk",
        selection_provider="apify",
    )

    monkeypatch.setattr(service, "_translate_apify", lambda text: "")
    monkeypatch.setattr(service, "_translate_google_free", lambda text: f"uk:{text}")
    assert service.translate_selection("hello world") == "uk:hello world"


def test_translate_with_apify_prefers_api(monkeypatch):
    service = TranslationService(
        source_lang="en",
        target_lang="uk",
        selection_provider="apify",
        apify_api_token="apify_api_test",
    )
    monkeypatch.setattr(service, "_translate_apify", lambda text: f"api:{text}")
    monkeypatch.setattr(
        service,
        "_translate_google_free",
        lambda text: (_ for _ in ()).throw(AssertionError("free should not run")),
    )
    assert service.translate_selection("hello") == "api:hello"


def test_apify_block_provider_chain_uses_api_only():
    service = TranslationService(
        source_lang="en",
        target_lang="uk",
        block_provider="apify",
        apify_api_token="apify_api_test",
    )
    chain = service._provider_chain("apify")
    assert chain == [service._translate_apify]


def test_set_providers_updates_all():
    service = TranslationService(block_provider="auto")
    service.set_providers("openai", "free", "apify")
    assert service.block_provider == "openai"
    assert service.word_provider == "free"
    assert service.selection_provider == "apify"


def test_translate_with_google_uses_google_only(monkeypatch):
    service = TranslationService(
        source_lang="en",
        target_lang="uk",
        selection_provider="google",
        google_api_key="AIza-test",
    )
    monkeypatch.setattr(service, "_translate_google_api", lambda text: f"api:{text}")
    monkeypatch.setattr(
        service,
        "_translate_google_free",
        lambda text: (_ for _ in ()).throw(AssertionError("free should not run")),
    )
    assert service.translate_with_google("hello") == "api:hello"


def test_google_block_provider_chain_uses_api_only():
    service = TranslationService(
        source_lang="en",
        target_lang="uk",
        block_provider="google",
        google_api_key="AIza-test",
    )
    chain = service._provider_chain("google")
    assert chain == [service._translate_google_api]


def test_auto_chain_includes_apify_and_google(monkeypatch):
    service = TranslationService(
        source_lang="en",
        target_lang="uk",
        apify_api_token="apify_api_test",
        google_api_key="AIza-test",
        deepl_api_key="deepl-test:fx",
    )
    chain = service._provider_chain("auto")
    assert service._translate_apify in chain
    assert service._translate_google_api in chain
    assert service._translate_deepl in chain
    assert chain.index(service._translate_apify) < chain.index(
        service._translate_google_api
    )
    assert chain.index(service._translate_google_api) < chain.index(
        service._translate_deepl
    )


def test_deepl_block_provider_chain_uses_api_only():
    service = TranslationService(
        source_lang="en",
        target_lang="uk",
        block_provider="deepl",
        deepl_api_key="deepl-test:fx",
    )
    chain = service._provider_chain("deepl")
    assert chain == [service._translate_deepl]


def test_translate_with_google_caches_result(monkeypatch):
    service = TranslationService(
        source_lang="en",
        target_lang="uk",
        selection_provider="google",
        google_api_key="AIza-test",
    )
    calls = {"n": 0}

    def _google(_text: str) -> str:
        calls["n"] += 1
        return "cached translation"

    monkeypatch.setattr(service, "_translate_google_api", _google)
    assert service.translate_with_google("test") == "cached translation"
    assert service.translate_with_google("test") == "cached translation"
    assert calls["n"] == 1


def test_prefetch_words_skips_cached(monkeypatch):
    service = TranslationService(source_lang="en", target_lang="uk", provider="free")
    sentence = "Hello world"
    service._word_cache[service._word_cache_key("hello", sentence)] = WordTranslation(
        "hello", "привіт", "", "", "noun", "greeting"
    )

    fetched: list[str] = []

    def _fetch_word(word: str, _sentence: str):
        fetched.append(word)
        return WordTranslation(word, "x", "", "", "", "")

    monkeypatch.setattr(service, "_fetch_word", _fetch_word)
    service.prefetch_words(sentence)
    import time

    time.sleep(0.3)
    assert "hello" not in fetched
    assert "world" in fetched


def test_auto_chain_includes_bergamot_before_ollama():
    service = TranslationService(source_lang="en", target_lang="uk")
    chain = service._provider_chain("auto")
    assert service._translate_bergamot_sentence in chain
    assert service._translate_ollama_sentence in chain
    assert chain.index(service._translate_bergamot_sentence) < chain.index(
        service._translate_ollama_sentence
    )


def test_bergamot_provider_falls_back_to_ollama(monkeypatch):
    service = TranslationService(
        source_lang="en",
        target_lang="uk",
        block_provider="bergamot",
    )
    chain = service._provider_chain("bergamot")
    assert chain == [
        service._translate_bergamot_sentence,
        service._translate_ollama_sentence,
    ]


def test_translate_bergamot_when_available(monkeypatch):
    service = TranslationService(
        source_lang="en",
        target_lang="uk",
        block_provider="bergamot",
    )
    monkeypatch.setattr(service, "can_use_bergamot", lambda **_: True)
    monkeypatch.setattr(
        "src.core.translation_service.bergamot_translate.translate",
        lambda text, src, tgt: f"bg:{text}",
    )
    assert service.translate_sentence("hello") == "bg:hello"


def test_set_languages_invalidates_bergamot_cache(monkeypatch):
    service = TranslationService(source_lang="en", target_lang="uk")
    service._bergamot_available = True
    service._bergamot_pair = ("en", "uk")
    service.set_languages("de", "uk")
    assert service._bergamot_available is None
    assert service._bergamot_pair is None
