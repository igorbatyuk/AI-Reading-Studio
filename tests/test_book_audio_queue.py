"""Tests for TTS queue management and book audio overview."""

from src.core.tts_engine import TTSEngine


def test_cancel_queued_jobs(qapp):
    tts = TTSEngine()
    key = tts._cache_key("queued block")
    tts._set_job(key, "queued", text="queued block", block_index=3)
    key2 = tts._cache_key("generating block")
    tts._set_job(key2, "generating", text="generating block")
    removed = tts.cancel_queued_jobs()
    assert removed == 1
    assert tts._jobs.get(key) is None
    assert tts._jobs.get(key2) == "generating"


def test_list_queue_jobs_sorted(qapp):
    tts = TTSEngine()
    tts._set_job(tts._cache_key("b"), "queued", text="b", block_index=5)
    tts._set_job(tts._cache_key("a"), "generating", text="a", block_index=1)
    jobs = tts.list_queue_jobs()
    assert len(jobs) == 2
    assert jobs[0]["state"] == "generating"


def test_use_saved_audio_skips_disk_cache(qapp, tmp_path):
    tts = TTSEngine()
    tts.set_app_dir(tmp_path)
    tts.set_reading_book(9)
    text = "cached paragraph"
    key = tts._cache_key(text)
    book_dir = tmp_path / "audio" / "books" / "9"
    book_dir.mkdir(parents=True)
    path = book_dir / f"{tts._cache_digest(key)}.mp3"
    path.write_bytes(b"mp3")
    assert tts.is_on_disk(text) is True
    assert tts.is_cached(text) is True
    tts.set_use_saved_audio(False)
    assert tts.is_cached(text) is False
    assert tts.is_on_disk(text) is True


def test_stop_background_generation_clears_queue(qapp):
    tts = TTSEngine()
    key = tts._cache_key("x")
    tts._set_job(key, "queued", text="x")
    removed = tts.stop_background_generation()
    assert removed == 1
    assert tts._jobs.get(key) is None


def test_book_audio_overview_counts(qapp, tmp_path):
    tts = TTSEngine()
    tts.set_app_dir(tmp_path)
    tts.set_reading_book(1)
    texts = ["one", "two"]
    key = tts._cache_key("one")
    book_dir = tmp_path / "audio" / "books" / "1"
    book_dir.mkdir(parents=True)
    (book_dir / f"{tts._cache_digest(key)}.mp3").write_bytes(b"mp3")
    overview = tts.book_audio_overview(texts)
    assert overview["total"] == 2
    assert overview["ready"] == 1
    assert overview["missing"] == 1
