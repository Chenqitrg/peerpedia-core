# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

r"""Offline operation queue -- file-based, no dependencies.

When the network is unavailable, push and delete operations are queued to
``~/.peerpedia/pending_ops.json``.  When the network returns, the queue is
flushed -- each operation is replayed against the remote server.

Storage: a JSON array of ``{"id": article_id, "op_type": "push"|"delete",
"created_at": epoch}`` objects in a flat file.  No database, no locking --
concurrent access is not expected (single-user CLI).

Functions
---------
add(op_type, article_id)    Append to queue (dedup by id+type)
list_all() -> list          Read all pending ops
count() -> int              Number of pending ops
remove(article_id)          Remove all ops for an article
clear()                     Empty the queue

Status: wired — ``_queue_if_offline`` in cli/handlers/articles.py calls
``pending.add("push", article_id)`` after create/publish/edit when the
server is unreachable.  ``_cmd_sync_push`` drains the queue.

Reviewer's checklist
--------------------
- Is dedup working correctly?  (Same article_id + op_type should not appear
  twice.)
- Are file read/write errors handled gracefully?  (_read returns [] on any
  error.)
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Literal

from peerpedia_core.config.paths import PENDING_OPS_FILE as PENDING_FILE

OpType = Literal["push", "delete"]
PendingOp = dict  # {"id": str, "op_type": OpType, "created_at": float}

_cache: list[PendingOp] | None = None


def _load() -> list[PendingOp]:
    """Load pending ops from disk (once).  Returns empty list if file missing."""
    global _cache
    if _cache is not None:
        return _cache
    if not PENDING_FILE.exists():
        _cache = []
        return _cache
    try:
        data = json.loads(PENDING_FILE.read_text())
        if isinstance(data, list):
            _cache = data
            return _cache
        raise ValueError(f"Pending queue is not a JSON array: {PENDING_FILE}")
    except json.JSONDecodeError as e:
        raise ValueError(f"Corrupted pending queue at {PENDING_FILE}: {e}") from e
    except OSError as e:
        raise ValueError(f"Cannot read pending queue at {PENDING_FILE}: {e}") from e


def _flush() -> None:
    """Write cache to disk."""
    if _cache is None:
        return
    PENDING_FILE.parent.mkdir(parents=True, exist_ok=True)
    PENDING_FILE.write_text(json.dumps(_cache, indent=2))


def add(op_type: OpType, article_id: str) -> None:
    """Add an operation to the pending queue (cached, write-through)."""
    ops = _load()
    for op in ops:
        if op.get("id") == article_id and op.get("op_type") == op_type:
            return
    ops.append({"id": article_id, "op_type": op_type, "created_at": time.time()})
    _flush()


def list_all() -> list[PendingOp]:
    """Return all pending operations (from cache)."""
    return _load()


def count() -> int:
    """Return number of pending operations."""
    return len(_load())


def remove(article_id: str) -> None:
    """Remove all pending ops for an article (cached, write-through)."""
    global _cache
    ops = _load()
    _cache = [op for op in ops if op.get("id") != article_id]
    _flush()


def clear() -> None:
    """Remove all pending operations."""
    global _cache
    _cache = []
    _flush()
