# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Per-article locks for serializing concurrent git operations.

These locks prevent races when multiple threads operate on the same
article's git repository (e.g., accepting a merge while a review is
being committed).
"""

import threading

_locks_dict: dict[str, threading.Lock] = {}
_locks_guard = threading.Lock()


def get_article_lock(article_id: str) -> threading.Lock:
    """Get or create a threading.Lock for the given article_id.

    Thread-safe: guards dict access with _locks_guard to prevent races
    during lock creation. The lock persists indefinitely.
    """
    # TODO(perf): locks never evicted — in a long-running server process,
    # _locks_dict grows unboundedly with every unique article_id.  Add LRU
    # eviction or weakref-based cleanup when articles are deleted.
    with _locks_guard:
        lock = _locks_dict.get(article_id)
        if lock is None:
            lock = threading.Lock()
            _locks_dict[article_id] = lock
    return lock
