# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Offline operation queue.

When the network is unavailable, operations (push, delete) are queued as
pending.  When the network returns, the queue is flushed — each operation
is replayed against the remote server.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Literal

PENDING_FILE = Path.home() / ".peerpedia" / "pending_ops.json"

OpType = Literal["push", "delete"]
PendingOp = dict  # {"id": str, "op_type": OpType, "created_at": float}


def _read() -> list[PendingOp]:
    """Read pending ops from disk. Returns empty list if file doesn't exist."""
    if not PENDING_FILE.exists():
        return []
    try:
        data = json.loads(PENDING_FILE.read_text())
        if isinstance(data, list):
            return data
    except (json.JSONDecodeError, OSError):
        pass
    return []


def _write(ops: list[PendingOp]) -> None:
    """Write pending ops to disk."""
    PENDING_FILE.parent.mkdir(parents=True, exist_ok=True)
    PENDING_FILE.write_text(json.dumps(ops, indent=2))


def add(op_type: OpType, article_id: str) -> None:
    """Add an operation to the pending queue."""
    ops = _read()
    # Don't duplicate — if same article_id + op_type already pending, skip
    for op in ops:
        if op.get("id") == article_id and op.get("op_type") == op_type:
            return
    ops.append({"id": article_id, "op_type": op_type, "created_at": time.time()})
    _write(ops)


def list_all() -> list[PendingOp]:
    """Return all pending operations."""
    return _read()


def count() -> int:
    """Return number of pending operations."""
    return len(_read())


def remove(article_id: str) -> None:
    """Remove all pending ops for an article."""
    ops = [op for op in _read() if op.get("id") != article_id]
    _write(ops)


def clear() -> None:
    """Remove all pending operations."""
    _write([])
