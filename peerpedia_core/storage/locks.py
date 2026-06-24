# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Per-article locks for serializing concurrent git operations.

These locks prevent races when multiple threads operate on the same
article's git repository (e.g., accepting a merge while a review is
being committed).

Locks are tracked with a last-access timestamp and evicted via LRU
when the dict exceeds ``_MAX_LOCKS`` entries.  Only unlocked locks
(``not lk.locked()``) are eligible for eviction.

Design decisions
----------------
- **LRU, not refcount**: A refcount approach would require callers to
  explicitly "release" their reference to the lock.  Since callers use
  ``with get_article_lock(id):`` or ``lock.acquire()/release()``, we
  track liveness via ``locked()`` — a lock is evictable if no thread
  currently holds it AND it's among the oldest.
- **10% eviction, not 1**: Evicting one lock at a time triggers
  ``_maybe_evict`` on every subsequent ``get_article_lock`` until the
  dict shrinks below threshold.  Batch-evicting 10% amortizes the cost.
- **Timestamps via ``time.monotonic()``**: Not wall-clock time — immune
  to system clock changes.  Only used for relative ordering, never
  exposed to callers.
"""

import threading
import time

_MAX_LOCKS = 1000


class _TrackedLock:
    """A ``threading.Lock`` wrapper that records last-access time for LRU eviction.

    Drop-in compatible with ``threading.Lock`` — supports ``acquire()``,
    ``release()``, ``locked()``, and the context-manager protocol.
    """

    __slots__ = ("_lock", "_last_access")

    def __init__(self) -> None:
        """Create a new lock with the current monotonic time."""
        self._lock = threading.Lock()
        self._last_access = time.monotonic()

    def acquire(self, blocking: bool = True, timeout: float = -1) -> bool:
        """Acquire the lock, updating the last-access timestamp on success.

        Returns ``True`` if the lock was acquired, ``False`` if *blocking*
        is ``False`` and the lock could not be acquired immediately.
        """
        result = self._lock.acquire(blocking, timeout)
        if result:
            self._last_access = time.monotonic()
        return result

    def release(self) -> None:
        """Release the lock, updating the last-access timestamp."""
        self._lock.release()
        self._last_access = time.monotonic()

    def locked(self) -> bool:
        """Return ``True`` if the lock is currently held by any thread."""
        return self._lock.locked()

    def __enter__(self) -> "_TrackedLock":
        """Acquire the lock and return self for use as a context manager."""
        self.acquire()
        return self

    def __exit__(self, *args: object) -> None:
        """Release the lock on context manager exit."""
        self.release()


_locks_dict: dict[str, _TrackedLock] = {}
"""All active per-article locks.  Guarded by ``_locks_guard``."""

_locks_guard = threading.Lock()
"""Protects ``_locks_dict`` during get-or-create and eviction."""


def _maybe_evict() -> None:
    """Evict oldest unlocked locks when the dict exceeds ``_MAX_LOCKS``.

    Must be called while holding ``_locks_guard``.  Evicts the oldest
    10% of unlocked locks (at least 1).  If all locks are held, does
    nothing — eviction never preempts active operations.
    """
    if len(_locks_dict) <= _MAX_LOCKS:
        return
    candidates = sorted(
        ((aid, lk) for aid, lk in _locks_dict.items() if not lk.locked()),
        key=lambda item: item[1]._last_access,  # noqa: SLF001
    )
    if not candidates:
        return
    evict_n = max(1, len(candidates) // 10)
    for aid, _ in candidates[:evict_n]:
        del _locks_dict[aid]


def get_article_lock(article_id: str) -> _TrackedLock:
    """Get or create a lock for *article_id*.

    Thread-safe: guards dict access with ``_locks_guard``.  The lock
    persists until evicted by LRU when the dict grows past
    ``_MAX_LOCKS`` entries and the lock is not currently held.

    Callers should use ``with get_article_lock(id):`` or explicit
    ``acquire()`` / ``release()``.
    """
    with _locks_guard:
        lock = _locks_dict.get(article_id)
        if lock is None:
            lock = _TrackedLock()
            _locks_dict[article_id] = lock
            _maybe_evict()
    return lock
