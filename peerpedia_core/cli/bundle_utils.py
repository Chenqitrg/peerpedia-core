# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Auto-bundle helpers — push/pull all local articles after state changes.

Layer 1 of the CLI package.  Imports from ``helpers`` (Layer 1 sibling)
and ``bundle/`` (external).  Does NOT import from handlers or parser.
"""

from __future__ import annotations

import os

from peerpedia_core.cli.display import console
from peerpedia_core.cli.helpers import DEFAULT_ARTICLES_DIR, _die
from peerpedia_core.exceptions import ConflictError, ProtocolError, TransportError
from peerpedia_core.bundle import count as pending_count, sync_article
from peerpedia_core.transport import is_online

def _try_sync(db, server: str | None = None) -> None:
    """Sync all local articles with the server if online.  No-op otherwise.

    Called AFTER ``db.commit()`` in each state-changing command so the
    main operation is safely persisted before sync touches anything.
    Each synced article commits its own changes immediately.

    Best-effort: network and conflict errors are silent — local state
    is already persisted and manual push can retry later.  Warns on
    each invocation if the server is unreachable.
    """
    srv = server or os.environ.get("PEERPEDIA_SERVER")
    if not srv:
        console.print("[dim]⚠ No PEERPEDIA_SERVER set — auto-sync skipped.[/]")
        return
    if not is_online(srv):
        console.print(f"[dim]⚠ Server {srv} is offline — auto-sync skipped.[/]")
        return
    try:
        for article_dir in DEFAULT_ARTICLES_DIR.iterdir():
            if not (article_dir / ".git").is_dir():
                raise FileNotFoundError(
                    f"Article directory without .git repo: {article_dir}"
                )
            result = sync_article(db, srv, article_dir.name)
            if result["synced"]:
                db.commit()
    except TransportError as e:
        console.print(f"[dim]⚠ Auto-sync failed (network): {e.detail}[/]")
    except ProtocolError as e:
        console.print(f"[dim]⚠ Auto-sync failed (protocol): {e.detail}[/]")
    except ConflictError:
        console.print("[dim]⚠ Auto-sync conflict — pull and retry.[/]")


def _sync_server(args) -> str:
    """Return the peer server URL from --server flag or PEERPEDIA_SERVER env var.

    Raises SystemExit if neither is set — no default, no fallback.
    """
    srv = args.server if getattr(args, "server", None) else os.environ.get("PEERPEDIA_SERVER")
    if not srv:
        _die(
            "No peer server configured.  Set PEERPEDIA_SERVER or pass --server."
        )
    return srv
