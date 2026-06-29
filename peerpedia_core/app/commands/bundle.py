# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

r"""Bundle commands — sync status, pull, discover."""

from __future__ import annotations

from peerpedia_core.app.context import AppContext
from peerpedia_core.app.refs import require_user
from peerpedia_core.app.result import AppNotice, AppResult
from peerpedia_core.core import list_all_article_ids, merge_article_meta
from peerpedia_core.core.sync_article import pull_new_article, sync_article
from peerpedia_core.core.sync_social import discover_network
from peerpedia_core.exceptions import ConflictError, ProtocolError, TransportError


def sync_status(ctx: AppContext, *, server: str) -> AppResult:
    """Check connection to a peer server."""
    online = ctx.transport.is_online(server)
    return AppResult("", data={"server": server, "online": online})


def sync_pull(ctx: AppContext, *, server: str) -> AppResult:
    """Pull article updates from a peer server."""
    # ── Guard ──
    user_id = require_user(ctx)

    # ── Discover new articles ──
    _discover_new_articles(ctx, server, user_id)

    # ── Sync existing articles ──
    synced, failed = _sync_all_articles(ctx, server)
    if synced:
        ctx.db.commit()

    # ── Result ──
    notices: list[AppNotice] = []
    if synced:
        notices.append(AppNotice("S_SYNCED_COUNT",
            params={"count": len(synced), "server": server}))
    return AppResult("OK", data={"synced": synced, "failed": failed},
                     notices=notices)


def sync_discover(ctx: AppContext, *, server: str, depth: int = 1,
                  max_users: int = 100) -> AppResult:
    """Walk the follow graph to discover new users and articles."""
    # ── Guard ──
    user_id = require_user(ctx)

    # ── Execute ──
    result = discover_network(
        ctx.db, ctx.transport, server, user_id,
        depth=depth, max_users=max_users,
        signing_key_bytes=ctx.signing_key_bytes,
        pubkey_hex=ctx.pubkey_hex,
    )
    ctx.db.commit()
    return AppResult("", data=result)


# ── Internal ─────────────────────────────────────────────────────────────

def _discover_new_articles(ctx: AppContext, server: str, user_id: str) -> None:
    """Fetch server article list and pull any not already in local DB."""
    server_articles = ctx.transport.fetch_search(
        server, user_id,
        private_key_bytes=ctx.signing_key_bytes, pubkey_hex=ctx.pubkey_hex,
    )
    if not server_articles:
        return
    local_ids = set(list_all_article_ids(ctx.db))
    for entry in server_articles:
        if entry["id"] not in local_ids:
            merge_article_meta(ctx.db, [entry])
            pull_new_article(ctx.db, ctx.transport, server, entry["id"])


def _sync_all_articles(ctx: AppContext, server: str) -> tuple[list[str], list[str]]:
    """Sync every local article with *server*.  Returns (synced, failed)."""
    synced: list[str] = []
    failed: list[str] = []
    for aid in list_all_article_ids(ctx.db):
        try:
            result = sync_article(ctx.db, ctx.transport, server, aid)
            if result.get("synced"):
                synced.append(aid[:8])
        except (TransportError, ProtocolError, ConflictError) as e:
            failed.append(f"{aid[:8]}: {e.detail}")
    return synced, failed
