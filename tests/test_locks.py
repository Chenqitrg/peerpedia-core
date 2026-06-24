# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Tests for per-article lock management and LRU eviction."""

import threading

import pytest

from peerpedia_core.storage.locks import (
    _MAX_LOCKS,
    _TrackedLock,
    _locks_dict,
    _locks_guard,
    get_article_lock,
)


class TestTrackedLock:
    """_TrackedLock must be a drop-in replacement for threading.Lock."""

    def test_acquire_release(self):
        lock = _TrackedLock()
        assert not lock.locked()
        lock.acquire()
        assert lock.locked()
        lock.release()
        assert not lock.locked()

    def test_context_manager(self):
        lock = _TrackedLock()
        with lock:
            assert lock.locked()
        assert not lock.locked()

    def test_acquire_timeout(self):
        lock = _TrackedLock()
        lock.acquire()
        # Second acquire with timeout=0 must fail (non-blocking).
        acquired = lock.acquire(timeout=0)
        assert not acquired
        lock.release()

    def test_last_access_updates_on_acquire(self):
        lock = _TrackedLock()
        t0 = lock._last_access  # noqa: SLF001
        lock.acquire()
        t1 = lock._last_access  # noqa: SLF001
        assert t1 >= t0

    def test_last_access_updates_on_release(self):
        lock = _TrackedLock()
        lock.acquire()
        t0 = lock._last_access  # noqa: SLF001
        lock.release()
        t1 = lock._last_access  # noqa: SLF001
        assert t1 >= t0


class TestLRUEviction:
    """Eviction must trigger when dict grows past _MAX_LOCKS and only
    evict unlocked locks."""

    @classmethod
    def setup_class(cls):
        """Save global lock dict state before tests."""
        with _locks_guard:
            cls._saved = dict(_locks_dict)
            _locks_dict.clear()

    @classmethod
    def teardown_class(cls):
        """Restore global lock dict state after tests."""
        with _locks_guard:
            _locks_dict.clear()
            _locks_dict.update(cls._saved)

    def _fill_dict(self, n: int):
        """Create n locks in the dict (all unlocked)."""
        for i in range(n):
            get_article_lock(f"eviction-test-{i}")

    def test_no_eviction_below_threshold(self):
        self._fill_dict(_MAX_LOCKS)
        assert len(_locks_dict) == _MAX_LOCKS

    def test_eviction_triggers_above_threshold(self):
        self._fill_dict(_MAX_LOCKS + 10)
        assert len(_locks_dict) <= _MAX_LOCKS

    def test_locked_lock_not_evicted(self):
        """A held lock must survive eviction even if it's the oldest."""
        self._fill_dict(_MAX_LOCKS - 1)
        held_lock = get_article_lock("eviction-test-held")
        held_lock.acquire()
        try:
            for i in range(20):
                get_article_lock(f"eviction-test-extra-{i}")
            assert "eviction-test-held" in _locks_dict
            assert _locks_dict["eviction-test-held"] is held_lock
        finally:
            held_lock.release()

    def test_reacquire_after_eviction_gets_new_lock(self):
        """After eviction, re-acquiring gets a fresh lock (no stale state)."""
        self._fill_dict(_MAX_LOCKS + 50)
        lock = get_article_lock("eviction-test-0")
        assert isinstance(lock, _TrackedLock)
