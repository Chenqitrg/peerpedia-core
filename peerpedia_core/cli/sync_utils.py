# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Auto-sync helpers — push/pull all local articles after state changes.

Layer 1 of the CLI package.  Imports from ``helpers`` (Layer 1 sibling)
and ``sync/`` (external).  Does NOT import from handlers or parser.
"""

from __future__ import annotations

import os

from peerpedia_core.cli.helpers import DEFAULT_ARTICLES_DIR
from peerpedia_core.sync import is_online, count as pending_count, client_sync as sync_push


def _try_sync(db, server: str | None = None) -> None:
    """Sync all local articles with the server if online.  No-op otherwise.

    Called AFTER ``db.commit()`` in each state-changing command so the
    main operation is safely persisted before sync touches anything.
    Each synced article commits its own changes immediately.
    """
    srv = server or os.environ.get("PEERPEDIA_SERVER", "http://localhost:8080")
    if not is_online(srv):
        return
    try:
        for article_dir in DEFAULT_ARTICLES_DIR.iterdir():
            if not (article_dir / ".git").is_dir():
                continue
            result = sync_push(db, srv, article_dir.name)
            if result["synced"]:
                db.commit()
    except Exception:
        pass  # local state is already persisted; manual push can retry later


def _sync_server(args) -> str:
    # TODO(sync): ``localhost:8080`` is a dev convenience — remove once
    # peer discovery exists.  In production, servers are dynamic peers.
    return args.server or os.environ.get("PEERPEDIA_SERVER", "http://localhost:8080")
