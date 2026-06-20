# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Git bundle sync — push/pull article repos to/from a remote server.

Client-side functions mirror the server-side handlers in ``bundle_server``:

  client_sync()              ↔  (orchestration, no direct server mirror)
  client_find_merge_base()   ↔  serve_get_ancestor()
  client_pull_incremental()  ↔  serve_get_bundle()
  client_push_incremental()  ↔  serve_post_sync()
  client_create_article()    ↔  serve_post_articles()

Protocol:
  1. GET /api/v1/articles/{id}/head  → server HEAD hash (or 404 if unknown)
  2. POST /api/v1/articles/{id}/sync → send incremental git bundle (ff-only)
  3. GET /api/v1/articles/{id}/bundle?since=<hash> → pull incremental bundle
  4. 409 Conflict → pull + retry once
"""

from __future__ import annotations

import base64
import io
import tarfile
from pathlib import Path

import git as _git
from sqlalchemy.orm import Session

from peerpedia_core.commands import apply_sync_bundle
from peerpedia_core.sync.git_bundle import (
    create_bundle,
    find_common_ancestor,
    ingest_bundle,
)

# Sync domain defines its own articles directory — no dependency on git_backend.
DEFAULT_ARTICLES_DIR = Path.home() / ".peerpedia" / "articles"


# ═══════════════════════════════════════════════════════════════════════════
# Sync logic (no HTTP details — all transport hidden below)
# ═══════════════════════════════════════════════════════════════════════════


def client_sync(db: Session, server: str, article_id: str) -> dict:
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
        repo = _git.Repo(rp)
        local_head: str = repo.head.commit.hexsha
    except (ValueError, _git.GitError):
        return {"synced": False, "head": None}

    server_head = fetch_head(server, article_id)

    # Server doesn't have this article yet — upload full repo
    if not server_head:
        return _dict(client_create_article(server, article_id), local_head)

    # Already in sync
    if local_head == server_head:
        return {"synced": True, "head": local_head}

    merge_base = client_find_merge_base(server, article_id, rp, server_head)

    # ── Case 1: Server ahead — pull only (ff) ────────────────────────────
    if merge_base == local_head:
        new_head = client_pull_incremental(db, server, article_id, local_head)
        return _dict(new_head is not None, new_head)

    # ── Case 2: Local ahead — push only ──────────────────────────────────
    if merge_base == server_head:
        return _dict(
            client_push_incremental(server, article_id, server_head, local_head) is not None,
            local_head,
        )

    # ── Case 3: Diverged — pull (non-ff merge), then push ────────────────
    if merge_base is not None:
        new_head = client_pull_incremental(db, server, article_id, merge_base, ff_only=False)
        if not new_head:
            return {"synced": False, "head": None}
        return _dict(
            client_push_incremental(server, article_id, server_head, new_head) is not None,
            new_head,
        )

    # No common ancestor or probe failed — shouldn't happen after fast-path
    return {"synced": False, "head": None}


def _dict(ok: bool, head: str) -> dict:
    return {"synced": True, "head": head} if ok else {"synced": False, "head": None}


def client_find_merge_base(
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


def client_pull_incremental(
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


def client_push_incremental(
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


def client_create_article(server: str, article_id: str) -> bool:
    """Upload a full repo tar.gz for a first-ever push."""
    rp = DEFAULT_ARTICLES_DIR / article_id
    if not (rp / ".git").is_dir():
        return False

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
