# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

r"""Bundle commands — sync status, pull, discover."""

from __future__ import annotations

from peerpedia_core.app.context import AppContext
from peerpedia_core.exceptions import ProtocolError
from peerpedia_core.app.refs import require_user
from peerpedia_core.app.result import AppNotice, AppResult
from peerpedia_core.core import list_all_article_ids, list_articles, merge_article_meta
from peerpedia_core.exceptions import ConflictError, ProtocolError, TransportError


def sync_status(ctx: AppContext, *, server: str) -> AppResult:
    """Check connection to a peer server."""
    # ── Execute ──
    online = ctx.transport.is_online(server)
    return AppResult("", data={"server": server, "online": online})


def sync_pull(ctx: AppContext, *, server: str) -> AppResult:
    """Pull article updates from a peer server."""
    # ── Guard ──
    user_id = require_user(ctx)

    # ── Discover new articles ──
    server_articles = ctx.transport.fetch_search(
        server, user_id,
        private_key_bytes=ctx.signing_key_bytes, pubkey_hex=ctx.pubkey_hex,
    )
    from peerpedia_core.core.sync_article import pull_new_article
    if server_articles:
        local_ids = set(list_all_article_ids(ctx.db))
        for entry in server_articles:
            if entry["id"] not in local_ids:
                merge_article_meta(ctx.db, [entry])
                pull_new_article(ctx.db, ctx.transport, server, entry["id"])
    # ── Sync each article ──
    from peerpedia_core.core.sync_article import sync_article
    synced: list[str] = []
    failed: list[str] = []
    for aid in list_all_article_ids(ctx.db):
        try:
            result = sync_article(ctx.db, ctx.transport, server, aid)
            if result.get("synced"):
                ctx.db.commit()
                synced.append(aid[:8])
        except (TransportError, ProtocolError, ConflictError) as e:
            failed.append(f"{aid[:8]}: {getattr(e, 'detail', str(e))}")
    notices: list[AppNotice] = []
    if synced:
        notices.append(AppNotice("S_SYNCED_COUNT", params={"count": len(synced), "server": server}))
    return AppResult("OK", data={"synced": synced, "failed": failed}, notices=notices)


def sync_discover(ctx: AppContext, *, server: str, depth: int = 1, max_users: int = 100) -> AppResult:
    """Walk the follow graph to discover new users and articles."""
    # ── Guard ──
    user_id = require_user(ctx)

    # ── Execute ──
    from peerpedia_core.core.sync_social import discover_network
    result = discover_network(
        ctx.db, ctx.transport, server, user_id,
        depth=depth, max_users=max_users,
        signing_key_bytes=ctx.signing_key_bytes,
        pubkey_hex=ctx.pubkey_hex,
    )
    ctx.db.commit()
    return AppResult("", data=result)
