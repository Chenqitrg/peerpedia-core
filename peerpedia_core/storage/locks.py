# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Per-article locks for serializing concurrent git operations.

These locks prevent races when multiple threads operate on the same
article's git repository (e.g., accepting a merge while a review is
being committed).

Locks are tracked with a last-access timestamp and evicted via LRU
when the dict exceeds ``_MAX_LOCKS`` entries.  Only unlocked locks
(``not lk.locked()``) are eligible for eviction.
"""

import threading
import time

_MAX_LOCKS = 1000


class _TrackedLock:
    """A ``threading.Lock`` wrapper that records last-access time for LRU eviction."""

    __slots__ = ("_lock", "_last_access")

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._last_access = time.monotonic()

    def acquire(self, blocking: bool = True, timeout: float = -1) -> bool:
        result = self._lock.acquire(blocking, timeout)
        if result:
            self._last_access = time.monotonic()
        return result

    def release(self) -> None:
        self._lock.release()
        self._last_access = time.monotonic()

    def locked(self) -> bool:
        return self._lock.locked()

    def __enter__(self) -> "_TrackedLock":
        self.acquire()
        return self

    def __exit__(self, *args: object) -> None:
        self.release()


_locks_dict: dict[str, _TrackedLock] = {}
_locks_guard = threading.Lock()


def _maybe_evict() -> None:
    """Evict oldest unlocked locks when the dict exceeds ``_MAX_LOCKS``."""
    if len(_locks_dict) <= _MAX_LOCKS:
        return
    # Collect unlocked candidates sorted by last-access time (oldest first).
    candidates = sorted(
        ((aid, lk) for aid, lk in _locks_dict.items() if not lk.locked()),
        key=lambda item: item[1]._last_access,  # noqa: SLF001
    )
    if not candidates:
        return  # all locks are currently held — nothing to evict
    # Evict the oldest 10% (at least 1).
    evict_n = max(1, len(candidates) // 10)
    for aid, _ in candidates[:evict_n]:
        del _locks_dict[aid]


def get_article_lock(article_id: str) -> _TrackedLock:
    """Get or create a lock for *article_id*.

    Thread-safe: guards dict access with ``_locks_guard``.  The lock
    persists until evicted by LRU when the dict grows past
    ``_MAX_LOCKS`` entries and the lock is not currently held.
    """
    with _locks_guard:
        lock = _locks_dict.get(article_id)
        if lock is None:
            lock = _TrackedLock()
            _locks_dict[article_id] = lock
            _maybe_evict()
    return lock
