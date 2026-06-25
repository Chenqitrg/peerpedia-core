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
from peerpedia_core.config.paths import DATA_ROOT
from peerpedia_core.transport import is_online
from peerpedia_core.transport.health import check_clock_skew

def _try_sync(db, server: str | None = None) -> None:
    """Sync all local articles with the server if online.  No-op otherwise.

    Called AFTER ``db.commit()`` in each state-changing command so the
    main operation is safely persisted before sync touches anything.
    Each synced article commits its own changes immediately.

    Best-effort: network and conflict errors are silent — local state
    is already persisted and manual push can retry later.  Warns on
    each invocation if the server is unreachable.

    TODO(P2P-sync): this pushes local articles but never pulls remote ones.
    After push, should also pull new articles from followed users and
    check for updates to existing articles.
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


def _resolve_server_url(args) -> str:
    """Return the peer server URL from --server flag, env var, or saved default.

    The last-used server URL is saved to ``~/.peerpedia/server_default`` so
    users don't need to pass ``--server`` on every command.
    """
    srv = getattr(args, "server", None) or os.environ.get("PEERPEDIA_SERVER")
    if not srv:
        default_file = DATA_ROOT / "server_default"
        try:
            if default_file.is_file():
                srv = default_file.read_text().strip()
        except OSError as e:
            _die(f"Cannot read default server from {default_file}: {e}")
    if not srv:
        _die("No peer server configured.  Set PEERPEDIA_SERVER or pass --server.")

    _save_default_server(srv)

    # Check clock sync before any network operation.
    skew = check_clock_skew(srv)
    if skew is not None and abs(skew) > 30:
        direction = "behind" if skew > 0 else "ahead"
        _die(
            f"Clock is {abs(skew)}s {direction} {srv}. "
            "Fix your system clock before syncing — "
            "commit timestamps would be unreliable for priority claims."
        )

    return srv


def _save_default_server(url: str) -> None:
    """Persist *url* as the default server for future commands."""
    try:
        DATA_ROOT.mkdir(parents=True, exist_ok=True)
        (DATA_ROOT / "server_default").write_text(url)
    except OSError as e:
        console.print(
            f"[dim]⚠ Cannot save default server to {DATA_ROOT}: {e}[/]"
        )
