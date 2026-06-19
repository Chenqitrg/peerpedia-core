# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Git bundle sync — push/pull article repos to/from a remote server.

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

from peerpedia_core.storage.git_backend import (
    DEFAULT_ARTICLES_DIR,
    get_commit_history,
)
from peerpedia_core.sync.git_bundle import (
    apply_bundle,
    create_bundle,
    find_common_ancestor,
)


# ═══════════════════════════════════════════════════════════════════════════
# Sync logic (no HTTP details — all transport hidden below)
# ═══════════════════════════════════════════════════════════════════════════


def sync(server: str, article_id: str) -> dict:
    """Synchronize local article with the remote server.

    Finds the common ancestor, then acts on three cases:

      - Server ahead (merge_base == local_head):  pull only (ff).
      - Local ahead  (merge_base == server_head): push only.
      - Diverged:                                 pull (non-ff), merge, then push.

    Returns:
        {"synced": True, "head": "<hash>"} on success
        {"synced": False, "head": None} on failure
    """
    rp = DEFAULT_ARTICLES_DIR / article_id
    try:
        history = get_commit_history(rp)
    except ValueError:
        return {"synced": False, "head": None}
    local_head: str = history[0]["hash"]

    server_head = fetch_head(server, article_id)

    # Server doesn't have this article yet — upload full repo
    if not server_head:
        return _dict(_create_article(server, article_id), local_head)

    # Already in sync
    if local_head == server_head:
        return {"synced": True, "head": local_head}

    merge_base = _find_merge_base_via_probe(server, article_id, rp, server_head)

    # ── Case 1: Server ahead — pull only (ff) ────────────────────────────
    # _pull_incremental → fetch_bundle (GET) + apply_bundle (git merge --ff-only)
    if merge_base == local_head:
        new_head = _pull_incremental(server, article_id, local_head)
        return _dict(new_head is not None, new_head)

    # ── Case 2: Local ahead — push only ──────────────────────────────────
    # _push_incremental → create_bundle (git bundle create) + push_bundle (POST)
    if merge_base == server_head:
        return _dict(
            _push_incremental(server, article_id, server_head, local_head) is not None,
            local_head,
        )

    # ── Case 3: Diverged — pull (non-ff merge), then push ────────────────
    # _pull_incremental(ff_only=False) → apply_bundle without --ff-only →
    #    git merge creates a merge commit (or fast-forwards if possible).
    # Then _push_incremental uploads the merged result.
    if merge_base is not None:
        new_head = _pull_incremental(server, article_id, merge_base, ff_only=False)
        if not new_head:
            return {"synced": False, "head": None}
        return _dict(
            _push_incremental(server, article_id, server_head, new_head) is not None,
            new_head,
        )

    # No common ancestor or probe failed — shouldn't happen after fast-path
    return {"synced": False, "head": None}


def _dict(ok: bool, head: str) -> dict:
    return {"synced": True, "head": head} if ok else {"synced": False, "head": None}


def _find_merge_base_via_probe(
    server: str, article_id: str, repo_path: Path, server_head: str,
) -> str | None:
    """Find merge base by probing the server with candidate hashes.

    Delegates the HTTP probing to ``_ancestor_probe`` and the search to
    ``find_common_ancestor``.  This function itself has no HTTP code.
    """
    probe = ancestor_probe(server, article_id)
    return find_common_ancestor(repo_path, probe, server_head=server_head)


# ═══════════════════════════════════════════════════════════════════════════
# Git operations (no HTTP)
# ═══════════════════════════════════════════════════════════════════════════


def _pull_incremental(
    server: str, article_id: str, since_hash: str | None, *, ff_only: bool = True,
) -> str | None:
    """Pull server commits from *since_hash* to server HEAD.

    Does two things:
      1. ``fetch_bundle`` — GET /bundle?since=… (HTTP)
      2. ``apply_bundle`` — git bundle verify + git fetch + git merge

    *since_hash=None* means "full pull" (from the beginning).
    *ff_only=True*  → ``git merge --ff-only`` (server ahead).
    *ff_only=False* → ``git merge`` — creates a merge commit when diverged.
    """
    bundle_bytes = fetch_bundle(server, article_id, since_hash)
    if not bundle_bytes:
        return None
    # apply_bundle → git merge (with or without --ff-only)
    apply_bundle(DEFAULT_ARTICLES_DIR / article_id, bundle_bytes, ff_only=ff_only)
    history = get_commit_history(DEFAULT_ARTICLES_DIR / article_id)
    return history[0]["hash"]


def _push_incremental(
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


def _create_article(server: str, article_id: str) -> bool:
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
