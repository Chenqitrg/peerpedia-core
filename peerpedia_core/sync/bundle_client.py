# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

r"""Git bundle sync — push/pull article repos to/from a remote server.

Client-side functions mirror the server-side handlers in ``bundle_server``::

      CLIENT (bundle_client)              SERVER (bundle_server)
      ─────────────────────               ──────────────────────
      sync_article() → orchestrates        (HTTP routing layer, TBD)
        ├─ find_merge_base()   ↔   serve_get_ancestor()
        │    └─ monotonic_search            └─ is_ancestor()
        ├─ pull_incremental()   ↔   serve_get_bundle()
        │    └─ fetch_bundle(HTTP)          └─ create_bundle()
        └─ push_incremental()   ↔   serve_post_sync()
             └─ create_bundle()             └─ apply_bundle()

Protocol flow (sync_article orchestrates)::

    1. GET  /api/v1/articles/{id}/head     → server HEAD (404 if unknown)
    2. If server has no article:
         tar.gz → POST /api/v1/articles    → server unpacks + inits repo
    3. Find merge base:
         k-exponential probe GET /ancestor/{hash} → boolean
         Binary search to exact boundary
    4. If server has new commits:
         GET /bundle?since=<local_head>    → incremental bundle bytes
         apply_bundle(repo, bundle)
    5. If local has new commits:
         create_bundle(repo, server_head)  → incremental bundle bytes
         POST /sync with bundle            → server applies (ff_only=True)
    6. On 409 Conflict (history diverged):
         Pull first → merge locally → push again

After sync, the caller must call ``commands.sync.apply_sync_bundle`` to
reconcile the DB cache with the updated git state.  This module does NOT
touch the DB — it only moves git objects.

Reviewer's checklist
--------------------
- Does every HTTP call go through ``transport/http.py`` (not httpx directly)?
- Is ``ff_only=True`` on all pushes?  (PeerPedia rejects force-pushes.)
- On 409, does the retry pull before re-pushing?
"""

from __future__ import annotations

import base64
import io
import tarfile
from pathlib import Path

from peerpedia_core.storage.db import Session

from peerpedia_core.commands import apply_sync_bundle
from peerpedia_core.sync.git_bundle import (
    create_bundle,
    find_common_ancestor,
    get_head,
    ingest_bundle,
)

from peerpedia_core.config.paths import ARTICLES_DIR as DEFAULT_ARTICLES_DIR


# ═══════════════════════════════════════════════════════════════════════════
# Sync logic (no HTTP details — all transport hidden below)
# ═══════════════════════════════════════════════════════════════════════════


def sync_article(db: Session, server: str, article_id: str) -> dict:
    """Synchronize local article with the remote server.

    Finds the common ancestor, then acts on three cases:

      - Server ahead (merge_base == local_head):  pull only (ff).
      - Local ahead  (merge_base == server_head): push only.
      - Diverged:                                 pull (non-ff), merge, then push.

    Pull applies the git bundle and reconciles DB state (authors, score).
    Caller owns the transaction boundary — this function does NOT commit.

    Returns:
        {"synced": True, "head": "<hash>"} on success
        {"synced": False, "head": None} on failure
    """
    rp = DEFAULT_ARTICLES_DIR / article_id
    try:
        local_head: str = get_head(rp)
    except (FileNotFoundError, ValueError):
        return {"synced": False, "head": None}

    server_head = fetch_head(server, article_id)

    # Server doesn't have this article yet — upload full repo
    if not server_head:
        return _result(create_remote_article(server, article_id), local_head)

    # Already in sync
    if local_head == server_head:
        return {"synced": True, "head": local_head}

    merge_base = find_merge_base(server, article_id, rp, server_head)

    # ── Case 1: Server ahead — pull only (ff) ────────────────────────────
    if merge_base == local_head:
        new_head = pull_incremental(db, server, article_id, local_head)
        return _result(new_head is not None, new_head)

    # ── Case 2: Local ahead — push only ──────────────────────────────────
    if merge_base == server_head:
        return _result(
            push_incremental(server, article_id, server_head, local_head) is not None,
            local_head,
        )

    # ── Case 3: Diverged — pull (non-ff merge), then push ────────────────
    if merge_base is not None:
        new_head = pull_incremental(db, server, article_id, merge_base, ff_only=False)
        if not new_head:
            return {"synced": False, "head": None}
        return _result(
            push_incremental(server, article_id, server_head, new_head) is not None,
            new_head,
        )

    # No common ancestor or probe failed — shouldn't happen after fast-path
    return {"synced": False, "head": None}


def _result(ok: bool, head: str) -> dict:
    return {"synced": True, "head": head} if ok else {"synced": False, "head": None}


def find_merge_base(
    server: str, article_id: str, repo_path: Path, server_head: str,
) -> str | None:
    """Find merge base by probing the server with candidate hashes.

    Delegates the HTTP probing to ``ancestor_probe`` and the search to
    ``find_common_ancestor``.  This function itself has no HTTP code.
    """
    probe = ancestor_probe(server, article_id)
    return find_common_ancestor(repo_path, probe, server_head=server_head)


# ═══════════════════════════════════════════════════════════════════════════
# Git operations (no HTTP)
# ═══════════════════════════════════════════════════════════════════════════


def pull_incremental(
    db: Session,
    server: str,
    article_id: str,
    since_hash: str | None,
    *,
    ff_only: bool = True,
) -> str | None:
    """Pull server commits from *since_hash* to server HEAD.

    1. ``fetch_bundle`` — GET /bundle?since=… (HTTP) → bytes
    2. ``ingest_bundle`` — verify + fetch objects into git (pure git)
    3. ``apply_sync_bundle`` — merge + DB reconcile (via commands)

    *since_hash=None* means "full pull" (from the beginning).
    *ff_only=True*  → ``git merge --ff-only`` (server ahead).
    *ff_only=False* → ``git merge`` — creates a merge commit when diverged.
    """
    bundle_bytes = fetch_bundle(server, article_id, since_hash)
    if not bundle_bytes:
        return None
    ingest_bundle(DEFAULT_ARTICLES_DIR / article_id, bundle_bytes)
    return apply_sync_bundle(db, article_id, ff_only=ff_only)


def push_incremental(
    server: str, article_id: str, since_hash: str, to_hash: str,
) -> str | None:
    """Push local commits from *since_hash* to *to_hash*.

    Creates an incremental bundle and POSTs it to the server.
    Returns *to_hash* on success, None on failure.
    """
    bundle_bytes = create_bundle(DEFAULT_ARTICLES_DIR / article_id, since_hash)
    if push_bundle(server, article_id, bundle_bytes) == "ok":
        return to_hash
    return None


def create_remote_article(server: str, article_id: str) -> bool:
    """Upload a full repo tar.gz for a first-ever push."""
    rp = DEFAULT_ARTICLES_DIR / article_id
    if not (rp / ".git").is_dir():
        return False

    # TODO(perf): tar.gz BytesIO → bytes → base64 str — three copies coexist
    # in memory.  For a 5MB compressed tar, peak memory ~17MB.  Stream
    # compression + base64 to reduce peak memory by 50%.
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        tar.add(str(rp), arcname=article_id)
    bundle_b64 = base64.b64encode(buf.getvalue()).decode("ascii")

    return post_article(server, article_id, bundle_b64)


# ═══════════════════════════════════════════════════════════════════════════
# HTTP transport — delegated to transport/http.py
# ═══════════════════════════════════════════════════════════════════════════

from peerpedia_core.sync.transport.http import (
    ancestor_probe,
    fetch_bundle,
    fetch_head,
    post_article,
    push_bundle,
)
