"""Tests for Kokoro FIFO generation queue."""

import threading
import time

from src.core import kokoro_tts


def test_generation_queue_serializes_access():
    order: list[str] = []

    def worker(name: str) -> None:
        with kokoro_tts._GENERATION_QUEUE:
            order.append(f"{name}-start")
            time.sleep(0.05)
            order.append(f"{name}-end")

    threads = [
        threading.Thread(target=worker, args=(label,))
        for label in ("a", "b", "c")
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=2.0)

    assert order.index("a-start") < order.index("a-end")
    assert order.index("b-start") < order.index("b-end")
    assert order.index("a-end") <= order.index("b-start")
    assert order.index("b-end") <= order.index("c-start")


def test_generation_queue_tracks_waiting_count():
    entered = threading.Event()
    release = threading.Event()

    def holder() -> None:
        with kokoro_tts._GENERATION_QUEUE:
            entered.set()
            release.wait(timeout=2.0)

    holder_thread = threading.Thread(target=holder, daemon=True)
    holder_thread.start()
    assert entered.wait(timeout=2.0)

    waiting_count: list[int] = []

    def waiter() -> None:
        with kokoro_tts._GENERATION_QUEUE:
            waiting_count.append(1)

    waiter_thread = threading.Thread(target=waiter, daemon=True)
    waiter_thread.start()
    time.sleep(0.05)
    assert kokoro_tts._GENERATION_QUEUE.waiting_count >= 1
    release.set()
    waiter_thread.join(timeout=2.0)
    holder_thread.join(timeout=2.0)
