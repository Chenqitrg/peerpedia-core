# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Batch article sync — iterate local articles, sync each to a peer.

Thin orchestration over ``core/sync_article.py``.  Notifies progress
via callbacks so the CLI layer can report to the user without this
module knowing how to display.
"""

from __future__ import annotations

from typing import Callable, TYPE_CHECKING

from peerpedia_core.config.paths import ARTICLES_DIR
from peerpedia_core.core.sync_article import sync_article
from peerpedia_core.core.sync_social import discover_articles
from peerpedia_core.exceptions import ConflictError, ProtocolError, TransportError
from peerpedia_core.storage.db import Session
from peerpedia_core.storage.peers import get_known_peers, record_peer_result
from peerpedia_core.time import validate_clock_skew

if TYPE_CHECKING:
    from peerpedia_core.transport import Transport


# Shared network-error tuple — centralize the list of "safe to skip" exceptions.
_NETWORK_ERRORS = (TransportError, ProtocolError, ConflictError, ConnectionError, OSError)


def _iter_local_syncable() -> list[str]:
    """Return article IDs that have a local git repo."""
    return [
        d.name for d in ARTICLES_DIR.iterdir()
        if (d / ".git").is_dir()
    ]


def _skip_if_unknown(transport: Transport, server: str, article_id: str) -> bool:
    """Return True if server doesn't know this article (safe to skip)."""
    try:
        return transport.fetch_head(server, article_id) is None
    except _NETWORK_ERRORS:
        return True


def sync_one(db: Session, transport: Transport, server: str, article_id: str) -> bool:
    """Sync one article.  Commit + return True on success.  Silently eat errors."""
    try:
        result = sync_article(db, transport, server, article_id)
        if result["synced"]:
            db.commit()
            return True
    except _NETWORK_ERRORS:
        pass
    return False


def sync_all(
    db: Session, transport: Transport, server: str, *,
    pre_check: bool = True,
    on_synced: Callable[[int], None] | None = None,
) -> int:
    """Sync all local articles to *server*.  Returns count of synced articles."""
    synced = 0
    for aid in _iter_local_syncable():
        if pre_check and _skip_if_unknown(transport, server, aid):
            continue
        if sync_one(db, transport, server, aid):
            synced += 1
            if on_synced:
                on_synced(synced)
    return synced


def sync_and_discover(
    db: Session, transport: Transport, server: str, *,
    user_id: str,
    pre_check: bool = True,
    on_synced: Callable[[int], None] | None = None,
    on_discovered: Callable[[int], None] | None = None,
    on_error: Callable[[Exception], None] | None = None,
) -> None:
    """Sync articles to *server*, then discover new ones from followed users.

    All errors are caught and reported via *on_error* — callers decide how to
    display (log, console, ignore).  CLI layer typically maps exception types
    to ``_out`` codes.
    """
    try:
        synced = sync_all(db, transport, server, pre_check=pre_check,
                          on_synced=on_synced)
        n = discover_articles(db, transport, server, user_id)
        if n and on_discovered:
            on_discovered(n)
    except _NETWORK_ERRORS as e:
        if on_error:
            on_error(e)


def sync_all_peers(
    db: Session, transport: Transport, *,
    user_id: str | None = None,
    on_peer_start: Callable[[str], None] | None = None,
    on_peer_done: Callable[[str, int], None] | None = None,
    on_peer_skip: Callable[[str, str], None] | None = None,
    on_peer_discover: Callable[[int], None] | None = None,
    on_peer_error: Callable[[Exception], None] | None = None,
) -> None:
    """Sync articles + discover from every known peer.  Best-effort.

    All callbacks are optional — omitted means silent.  CLI layer wires
    ``_out`` codes in each callback.
    """
    peers = get_known_peers()
    for server in peers:
        try:
            if not transport.is_online(server):
                if on_peer_skip:
                    on_peer_skip(server, "offline")
                record_peer_result(server, success=False)
                continue
            if validate_clock_skew(transport.check_clock_skew(server)):
                if on_peer_skip:
                    on_peer_skip(server, "clock_skew")
                record_peer_result(server, success=False)
                continue

            if on_peer_start:
                on_peer_start(server)
            synced = sync_all(db, transport, server, pre_check=True)
            if user_id:
                try:
                    n = discover_articles(db, transport, server, user_id)
                    if n and on_peer_discover:
                        on_peer_discover(n)
                except _NETWORK_ERRORS:
                    pass
            if on_peer_done:
                on_peer_done(server, synced)
            record_peer_result(server, success=True)
        except _NETWORK_ERRORS as e:
            if on_peer_error:
                on_peer_error(e)
            record_peer_result(server, success=False)
