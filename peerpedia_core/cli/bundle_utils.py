# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Auto-bundle helpers — push/pull all local articles after state changes.

Layer 1 of the CLI package.  Imports from ``helpers`` (Layer 1 sibling)
and ``bundle/`` (external).  Does NOT import from handlers or parser.
"""

from __future__ import annotations

import os

from peerpedia_core.cli.display import console
from peerpedia_core.cli.helpers import DEFAULT_ARTICLES_DIR, _die, _get_session_user
from peerpedia_core.exceptions import ConflictError, ProtocolError, TransportError
from peerpedia_core.bundle import count as pending_count, sync_article
from peerpedia_core.config.paths import DATA_ROOT
from peerpedia_core.transport import is_online
from peerpedia_core.transport.health import check_clock_skew
from peerpedia_core.social import discover_articles
from peerpedia_core.social.discovery import get_known_peers, record_peer_result
from peerpedia_core.transport import fetch_head
from peerpedia_core.transport.health import check_clock_skew


def _require_online_server(args) -> str:
    """Resolve server URL and die if unreachable.

    Replaces the duplicated 7-line guard in ``_cmd_sync_push`` and
    ``_cmd_sync_pull``.
    """
    server = _resolve_server_url(args)
    if not is_online(server):
        _die("Server unreachable",
             suggestion=f"Cannot connect to {server}. Check: (1) is the server "
                        "running? (2) is PEERPEDIA_SERVER set correctly? "
                        "(3) is your network up?",
             see_also=["sync status"])
    return server

def _sync_articles_to_peer(db, server: str, *, pre_check: bool = True) -> int:
    """Sync local articles to *server*.  Returns count of synced articles.

    When *pre_check* is True, calls ``fetch_head`` first and skips
    articles the peer doesn't have (avoids wasteful bundle push/pull).
    """
    synced = 0
    for article_dir in DEFAULT_ARTICLES_DIR.iterdir():
        if not (article_dir / ".git").is_dir():
            continue
        article_id = article_dir.name
        if pre_check:
            try:
                if fetch_head(server, article_id) is None:
                    continue
            except Exception:
                continue
        try:
            result = sync_article(db, server, article_id)
            if result["synced"]:
                db.commit()
                synced += 1
        except Exception:
            continue
    return synced


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
        _sync_articles_to_peer(db, srv, pre_check=False)

        # Discover new articles from followed users.
        user_id = _get_session_user()
        n = discover_articles(db, srv, user_id)
        if n:
            console.print(f"[dim]✓ Discovered {n} new article(s).[/]")
    except TransportError as e:
        console.print(f"[dim]⚠ Auto-sync failed (network): {e.detail}[/]")
    except ProtocolError as e:
        console.print(f"[dim]⚠ Auto-sync failed (protocol): {e.detail}[/]")
    except ConflictError:
        console.print("[dim]⚠ Auto-sync conflict — pull and retry.[/]")
    except ConnectionError as e:
        console.print(f"[dim]⚠ Auto-sync failed (connection): {e}[/]")


def _try_sync_all(db) -> None:
    """Sync all local articles with every known peer.  Best-effort.

    Iterates ``get_known_peers()`` (skipping backoff'd peers), checks
    each peer's HEAD for each local article via ``fetch_head``, and only
    syncs articles the peer actually has.  Records success/failure via
    ``record_peer_result`` for exponential backoff.

    Called after ``db.commit()`` in state-changing commands so local
    state is persisted before sync touches anything.
    """
    peers = get_known_peers()
    if not peers:
        console.print("[dim]No known peers — multi-peer sync skipped.[/]")
        return

    for server in peers:
        if not is_online(server):
            record_peer_result(server, success=False)
            continue

        # Check clock skew — skip if too far out of sync.
        skew = check_clock_skew(server)
        if skew is not None and abs(skew) > 30:
            console.print(
                f"[dim]⚠ Clock skew {skew}s with {server} — skipped.[/]"
            )
            record_peer_result(server, success=False)
            continue

        try:
            synced = _sync_articles_to_peer(db, server, pre_check=True)

            # Discover new articles from followed users on this peer.
            try:
                user_id = _get_session_user()
                n = discover_articles(db, server, user_id)
                if n:
                    console.print(
                        f"[dim]✓ {server}: discovered {n} article(s).[/]"
                    )
            except Exception:
                pass

            if synced:
                console.print(
                    f"[dim]✓ Synced {synced} article(s) with {server}.[/]"
                )
            record_peer_result(server, success=True)
        except Exception:
            record_peer_result(server, success=False)


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
