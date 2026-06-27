# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

r"""Git bundle sync — push/pull article repos to/from a remote server.

Client-side and server-side of the sync protocol, symmetric with
``core/sync_social.py`` (both take a ``Transport`` instance).

Client::

    sync_article(transport) → orchestrates
      ├─ _find_merge_base()   ↔  k-exponential ancestor probe
      ├─ pull_incremental()   ↔  fetch bundle → ingest → reconcile
      └─ push_incremental()   ↔  create bundle → push

Server::

    apply_sync() → ingest bundle → reconcile DB → process sink timers
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from peerpedia_core.config.paths import ARTICLES_DIR as DEFAULT_ARTICLES_DIR
from peerpedia_core.core import publish_ready_articles
from peerpedia_core.core.reconcile import reconcile_after_sync
from peerpedia_core.exceptions import MergeConflictError, ProtocolError, TransportError
from peerpedia_core.storage.db import Session
from peerpedia_core.storage.git import (
    create_bundle, find_common_ancestor, get_head,
    ingest_article, ingest_bundle, pack_article_repo,
)
from peerpedia_core.storage.pending import add, clear, count, list_all, remove
from peerpedia_core.time import validate_clock_skew

if TYPE_CHECKING:
    from peerpedia_core.transport import Transport


# ═══════════════════════════════════════════════════════════════════════════
# Client — sync orchestration
# ═══════════════════════════════════════════════════════════════════════════


def sync_article(db: Session, transport: Transport, server: str, article_id: str) -> dict:
    """Sync article with *server*.  Returns ``{"synced": True/False, "head": ...}``."""
    rp = DEFAULT_ARTICLES_DIR / article_id
    try:
        local_head: str = get_head(rp)
    except (FileNotFoundError, ValueError):
        return {"synced": False, "head": None}

    # ── Pre-flight checks ──────────────────────────────────────────────────
    if not transport.is_online(server):
        raise TransportError(
            f"Server {server} unreachable. "
            "Check that the server is running and your network is up.")
    err = validate_clock_skew(transport.check_clock_skew(server))
    if err:
        raise ProtocolError(
            f"{err} with {server}. "
            "Fix your system clock before syncing — "
            "commit timestamps would be unreliable for priority claims.")

    # ── Fetch server state ─────────────────────────────────────────────────
    server_head = transport.fetch_head(server, article_id)
    if not server_head:
        ok = _upload_article(transport, server, article_id)
        return {"synced": True, "head": local_head} if ok else {"synced": False, "head": None}
    if local_head == server_head:
        return {"synced": True, "head": local_head}

    # ── Three-way sync ─────────────────────────────────────────────────────
    merge_base = _find_merge_base(transport, server, article_id, rp, server_head)
    head = _sync_three_way(db, transport, server, article_id, merge_base, local_head, server_head)
    if head is None:
        raise ProtocolError(
            f"sync_article: no common ancestor found for {article_id} at {server}")
    return {"synced": True, "head": head}


def _sync_three_way(
    db: Session, transport: Transport,
    server: str, article_id: str,
    merge_base: str | None, local_head: str, server_head: str,
) -> str | None:
    """Execute the three-way sync decision.  Returns new HEAD or None."""
    if merge_base == local_head:
        return pull_incremental(db, transport, server, article_id, local_head)
    if merge_base == server_head:
        push_incremental(transport, server, article_id, server_head, local_head)
        return local_head
    if merge_base is not None:
        new_head = pull_incremental(db, transport, server, article_id, merge_base, ff_only=False)
        push_incremental(transport, server, article_id, server_head, new_head)
        return new_head
    return None


def _find_merge_base(
    transport: Transport,
    server: str, article_id: str, repo_path: Path, server_head: str,
) -> str | None:
    """Find merge base by probing the server with candidate hashes."""

    def probe(hash: str) -> bool | None:
        return transport.ancestor_probe(server, article_id, hash)

    return find_common_ancestor(repo_path, probe, server_head=server_head)


# ── Git operations ────────────────────────────────────────────────────────


def pull_incremental(
    db: Session, transport: Transport,
    server: str, article_id: str, since_hash: str | None, *,
    ff_only: bool = True,
) -> str:
    """Pull server commits and reconcile DB."""
    bundle_bytes = transport.fetch_bundle(server, article_id, since_hash)
    if not bundle_bytes:
        raise ProtocolError(
            f"pull_incremental: server returned empty bundle for article {article_id}")
    ingest_bundle(DEFAULT_ARTICLES_DIR / article_id, bundle_bytes)
    new_head = reconcile_after_sync(db, article_id, ff_only=ff_only)
    publish_ready_articles(db)
    return new_head


def pull_new_article(db: Session, transport: Transport, server: str, article_id: str) -> str | None:
    """Download a full repo when the article is new locally."""
    repo_b64 = transport.fetch_repo(server, article_id)
    if not repo_b64:
        return None
    return ingest_article(DEFAULT_ARTICLES_DIR / article_id,
                          {"id": article_id, "repo_bundle": repo_b64})


def push_incremental(
    transport: Transport,
    server: str, article_id: str, since_hash: str, to_hash: str,
) -> str:
    """Push local commits."""
    bundle_bytes = create_bundle(DEFAULT_ARTICLES_DIR / article_id, since_hash)
    transport.push_bundle(server, article_id, bundle_bytes)
    return to_hash


def _upload_article(transport: Transport, server: str, article_id: str) -> bool:
    """Upload full repo when server has no such article."""
    rp = DEFAULT_ARTICLES_DIR / article_id
    if not (rp / ".git").is_dir():
        raise FileNotFoundError(f"Repo not found: {rp}")
    get_head(rp)
    return transport.push_repo(server, article_id, pack_article_repo(rp))


# ═══════════════════════════════════════════════════════════════════════════
# Server — apply incoming sync
# ═══════════════════════════════════════════════════════════════════════════


def apply_sync(db: Session, article_id: str, bundle_bytes: bytes) -> str:
    """Apply an incoming git bundle and reconcile DB state.

    Ingest bundle → reconcile DB from git → process sink timers.
    Returns the new HEAD hash.
    """
    rp = DEFAULT_ARTICLES_DIR / article_id
    ingest_bundle(rp, bundle_bytes)
    new_head = reconcile_after_sync(db, article_id, ff_only=True)
    publish_ready_articles(db)
    return new_head
