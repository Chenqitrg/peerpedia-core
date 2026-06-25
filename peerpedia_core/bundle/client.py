# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

r"""Git bundle sync — push/pull article repos to/from a remote server.

Client-side functions mirror the server-side handlers in ``bundle_server``::

      CLIENT (bundle_client)              SERVER (bundle_server)
      ─────────────────────               ──────────────────────
      sync_article() → orchestrates        transport/http_server.py (ASGI routing)
        ├─ find_merge_base()   ↔   check_ancestor()
        │    └─ monotonic_search            └─ is_ancestor()
        ├─ pull_incremental()   ↔   get_bundle()
        │    └─ fetch_incremental_bundle(HTTP)          └─ create_bundle()
        └─ push_incremental()   ↔   apply_sync()
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
- Does every HTTP call go through ``transport/http_client.py`` (not httpx directly)?
- Is ``ff_only=True`` on all pushes?  (PeerPedia rejects force-pushes.)
- On 409, does the retry pull before re-pushing?
"""

from __future__ import annotations

from pathlib import Path

from peerpedia_core.exceptions import ProtocolError
from peerpedia_core.storage.db import Session

from peerpedia_core.commands import apply_sync_bundle
from peerpedia_core.bundle.git_bundle import (
    create_bundle,
    find_common_ancestor,
    get_head,
    ingest_bundle,
    pack_article_repo,
)
from peerpedia_core.bundle.server import ingest_article

from peerpedia_core.config.paths import ARTICLES_DIR as DEFAULT_ARTICLES_DIR
from peerpedia_core.transport import (
    ancestor_probe,
    fetch_article_repo,
    fetch_incremental_bundle,
    fetch_head,
    push_article_repo,
    push_bundle,
)
from peerpedia_core.transport.health import check_clock_skew


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
    Raises ProtocolError on unexpected server response.
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

    # Check clock sync before any sync operations — if the local clock is
    # far from the server, commit timestamps are untrustworthy for priority
    # claims.  Refuse to sync until the user fixes their system clock.
    skew = check_clock_skew(server)
    if skew is not None and abs(skew) > 30:
        direction = "behind" if skew > 0 else "ahead"
        raise ProtocolError(
            f"Clock skew with {server}: {abs(skew)}s {direction}. "
            "Fix your system clock before syncing — "
            "commit timestamps would be unreliable for priority claims."
        )

    server_head = fetch_head(server, article_id)

    # Server doesn't have this article yet — upload full repo
    if not server_head:
        if upload_article(server, article_id):
            return {"synced": True, "head": local_head}
        return {"synced": False, "head": None}

    # Already in sync
    if local_head == server_head:
        return {"synced": True, "head": local_head}

    merge_base = find_merge_base(server, article_id, rp, server_head)

    # ── Case 1: Server ahead — pull only (ff) ────────────────────────────
    if merge_base == local_head:
        return {"synced": True, "head": pull_incremental(db, server, article_id, local_head)}

    # ── Case 2: Local ahead — push only ──────────────────────────────────
    if merge_base == server_head:
        push_incremental(server, article_id, server_head, local_head)
        return {"synced": True, "head": local_head}

    # ── Case 3: Diverged — pull (non-ff merge), then push ────────────────
    if merge_base is not None:
        new_head = pull_incremental(db, server, article_id, merge_base, ff_only=False)
        push_incremental(server, article_id, server_head, new_head)
        return {"synced": True, "head": new_head}

    # No common ancestor or probe failed — shouldn't happen after fast-path
    raise ProtocolError(
        f"sync_article: no common ancestor found for {article_id} at {server}"
    )


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
) -> str:
    """Pull server commits from *since_hash* to server HEAD.

    1. ``fetch_incremental_bundle`` — GET /bundle?since=… (HTTP) → bytes
    2. ``ingest_bundle`` — verify + fetch objects into git (pure git)
    3. ``apply_sync_bundle`` — merge + DB reconcile (via commands)

    *since_hash=None* means "full pull" (from the beginning).
    *ff_only=True*  → ``git merge --ff-only`` (server ahead).
    *ff_only=False* → ``git merge`` — creates a merge commit when diverged.

    Raises ``ProtocolError`` on transport failure or empty bundle.
    """
    bundle_bytes = fetch_incremental_bundle(server, article_id, since_hash)
    if not bundle_bytes:
        raise ProtocolError(
            f"pull_incremental: server returned empty bundle for article {article_id}"
        )
    ingest_bundle(DEFAULT_ARTICLES_DIR / article_id, bundle_bytes)
    return apply_sync_bundle(db, article_id, ff_only=ff_only)


def pull_new_article(db: Session, server: str, article_id: str) -> str | None:
    """Pull an article that doesn't exist locally.

    Downloads the full repo as base64 tar.gz via ``fetch_article_repo`` and
    unpacks it — the mirror of ``upload_article`` → ``push_article_repo``.

    TODO(v1-content-sync): not yet wired into the discovery flow.  After
    ``merge_article_meta`` creates a stub, the caller must invoke this to
    fetch the actual git content.  Currently ``article show`` fails with
    "No source file found" for discovered articles.
    """
    repo_b64 = fetch_article_repo(server, article_id)
    if not repo_b64:
        return None
    payload = {"id": article_id, "repo_bundle": repo_b64}
    return ingest_article(DEFAULT_ARTICLES_DIR / article_id, payload)


def push_incremental(
    server: str, article_id: str, since_hash: str, to_hash: str,
) -> str:
    """Push local commits from *since_hash* to *to_hash*.

    Creates an incremental bundle and POSTs it to the server.
    Returns *to_hash* on success.

    Raises ``ProtocolError`` on transport failure or server rejection
    (conflict / error).
    """
    bundle_bytes = create_bundle(DEFAULT_ARTICLES_DIR / article_id, since_hash)
    push_bundle(server, article_id, bundle_bytes)
    return to_hash


def upload_article(server: str, article_id: str) -> bool:
    """Upload a full repo tar.gz when the server has no such article.

    Returns True on success.  Raises ``FileNotFoundError`` if the local
    git repo is missing.
    """
    rp = DEFAULT_ARTICLES_DIR / article_id
    if not (rp / ".git").is_dir():
        raise FileNotFoundError(f"Repo not found: {rp}")

    # Fail fast: don't upload an empty repo — the server expects at least
    # one commit (the initial commit from init_article_repo).
    get_head(rp)

    bundle_b64 = pack_article_repo(rp)
    return push_article_repo(server, article_id, bundle_b64)
