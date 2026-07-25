"""Tests for reading-focus prefetch cancellation."""

from src.core.tts_engine import TTSEngine


def test_set_reading_focus_cancels_queued_prefetch_for_skipped_blocks(qapp):
    tts = TTSEngine()
    tts.set_reading_book(7)
    texts = ["block zero", "block one", "block two"]
    tts.set_reading_focus(0, texts, ahead=1)
    key_old = tts._cache_key("block zero")
    tts._set_job(key_old, "queued")
    tts.set_reading_focus(2, texts, ahead=1)
    assert tts._jobs.get(key_old) is None


def test_prefetch_skips_blocks_before_reading_index(qapp, monkeypatch):
    tts = TTSEngine()
    tts.set_reading_book(3)
    tts.set_reading_focus(2, ["a", "b", "c"], ahead=1)
    calls: list[str] = []

    def fake_worker(text, key, for_word, generation, block_index):
        calls.append(text)

    monkeypatch.setattr(tts, "_prefetch_worker", fake_worker)
    tts.prefetch("a", block_index=0)
    assert calls == []


def test_clear_book_cache_removes_book_folder(qapp, tmp_path):
    tts = TTSEngine()
    tts.set_app_dir(tmp_path)
    book_dir = tmp_path / "audio" / "books" / "42"
    book_dir.mkdir(parents=True)
    (book_dir / "sample.mp3").write_bytes(b"mp3")
    removed = tts.clear_book_cache(42)
    assert removed == 1
    assert not book_dir.exists()
