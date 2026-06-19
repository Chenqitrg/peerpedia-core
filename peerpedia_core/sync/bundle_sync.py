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
    apply_bundle,
    create_bundle,
    find_common_ancestor,
    get_commit_history,
    is_ancestor,
)


# ═══════════════════════════════════════════════════════════════════════════
# Sync logic (no HTTP details — all transport hidden below)
# ═══════════════════════════════════════════════════════════════════════════


def push(server: str, article_id: str) -> dict:
    """Push local commits to the remote server via git bundle.

    Three cases:
      - Server ahead (local is ancestor):  pull only, no push needed.
      - Local ahead (server is ancestor):  push only, no pull needed.
      - Diverged (both have new commits):  full pull, merge, then push.

    Returns:
        {"pushed": True, "head": "<hash>"} on success
        {"pushed": False, "head": None} on failure
    """
    rp = DEFAULT_ARTICLES_DIR / article_id
    try:
        history = get_commit_history(rp)
    except ValueError:
        return {"pushed": False, "head": None}
    local_head: str = history[0]["hash"]

    server_head = _fetch_head(server, article_id)

    # First push: server doesn't have this article yet
    if not server_head:
        return _dict(_create_article(server, article_id), local_head)

    # Already in sync
    if local_head == server_head:
        return {"pushed": True, "head": local_head}

    # ── Classify the relationship ────────────────────────────────────────
    # Probe: ask server "do you have local_head in your history?"
    # Bundle bytes double as the check result AND the data for case 1.
    ahead_bundle = _server_has_ancestor(server, article_id, local_head)
    local_ahead = is_ancestor(rp, server_head)

    # ── Case 1: Server ahead — apply the bundle we already downloaded ────
    if ahead_bundle:
        apply_bundle(rp, ahead_bundle)
        history = get_commit_history(rp)
        return {"pushed": True, "head": history[0]["hash"]}

    # ── Case 2: Local ahead — push only ─────────────────────────────────
    if local_ahead:
        return _do_push(server, article_id, server_head, local_head)

    # ── Case 3: Diverged — find merge base via interactive probe ────────
    merge_base = _find_merge_base_via_probe(server, article_id, rp)
    if merge_base:
        # Pull server's changes from merge_base → server HEAD
        bundle = _fetch_bundle(server, article_id, merge_base)
        if bundle:
            apply_bundle(rp, bundle, ff_only=False)
            history = get_commit_history(rp)
            return _do_push(server, article_id, server_head, history[0]["hash"])

    # Fallback: full pull
    new_head = _pull_full(server, article_id)
    if not new_head:
        return {"pushed": False, "head": None}
    return _do_push(server, article_id, server_head, new_head)


def pull(server: str, article_id: str) -> dict:
    """Pull latest commits from the remote server.

    Returns:
        {"pulled": True, "head": "<hash>"} or {"pulled": False}
    """
    try:
        history = get_commit_history(DEFAULT_ARTICLES_DIR / article_id)
        local_head = history[0]["hash"]
    except ValueError:
        local_head = None

    server_head = _fetch_head(server, article_id)
    if not server_head:
        return {"pulled": False}

    new_head = _pull_incremental(server, article_id, local_head)
    if not new_head:
        new_head = _pull_full(server, article_id)  # TODO: replace with merge-base path
    if new_head:
        return {"pulled": True, "head": new_head}
    return {"pulled": False}


def _do_push(server: str, article_id: str, server_head: str, local_head: str) -> dict:
    """Push a bundle from *server_head*..*local_head* to the server."""
    bundle_bytes = create_bundle(DEFAULT_ARTICLES_DIR / article_id, server_head)
    result = _push_bundle(server, article_id, bundle_bytes)
    if result == "ok":
        return {"pushed": True, "head": local_head}
    return {"pushed": False, "head": None}


def _dict(ok: bool, head: str) -> dict:
    return {"pushed": True, "head": head} if ok else {"pushed": False, "head": None}


# ═══════════════════════════════════════════════════════════════════════════
# Git operations (no HTTP)
# ═══════════════════════════════════════════════════════════════════════════


def _find_merge_base_via_probe(
    server: str, article_id: str, repo_path: Path,
) -> str | None:
    """Find merge base by probing the server with candidate hashes.

    Uses k-exponential probe + binary refinement via
    GET /ancestor/{hash} on the server.
    """
    import httpx

    rp = repo_path

    def probe(hash: str) -> bool | None:
        """Ask server: do you have this hash in your history?"""
        try:
            resp = httpx.get(
                f"{_api_url(server, article_id)}/ancestor/{hash}",
                timeout=30,
            )
            return resp.status_code == 200
        except Exception:
            return None

    return find_common_ancestor(rp, probe)


def _pull_incremental(server: str, article_id: str, local_head: str | None) -> str | None:
    """Pull server commits when local is ancestor of server (ff-only case)."""
    if not local_head:
        return None
    bundle_bytes = _fetch_bundle(server, article_id, local_head)
    if not bundle_bytes:
        return None
    apply_bundle(DEFAULT_ARTICLES_DIR / article_id, bundle_bytes)
    history = get_commit_history(DEFAULT_ARTICLES_DIR / article_id)
    return history[0]["hash"]


def _pull_full(server: str, article_id: str) -> str | None:
    """Pull full server history and merge (diverged case — both sides have new commits)."""
    bundle_bytes = _fetch_bundle(server, article_id, None)
    if not bundle_bytes:
        return None
    # Non-ff merge: same files were not edited by both sides
    apply_bundle(DEFAULT_ARTICLES_DIR / article_id, bundle_bytes, ff_only=False)
    history = get_commit_history(DEFAULT_ARTICLES_DIR / article_id)
    return history[0]["hash"]


def _create_article(server: str, article_id: str) -> bool:
    """Upload a full repo tar.gz for a first-ever push."""
    rp = DEFAULT_ARTICLES_DIR / article_id
    if not (rp / ".git").is_dir():
        return False

    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        tar.add(str(rp), arcname=article_id)
    bundle_b64 = base64.b64encode(buf.getvalue()).decode("ascii")

    return _post_article(server, article_id, bundle_b64)


# ═══════════════════════════════════════════════════════════════════════════
# HTTP transport — the only place that touches httpx and status codes
# ═══════════════════════════════════════════════════════════════════════════

import httpx


def _api_url(server: str, article_id: str) -> str:
    """Build the REST base URL for an article on a remote server."""
    return f"{server}/api/v1/articles/{article_id}"


def _fetch_head(server: str, article_id: str) -> str | None:
    """GET /head → server's HEAD hash, or None if not found / unreachable."""
    try:
        resp = httpx.get(f"{_api_url(server, article_id)}/head", timeout=30)
        if resp.status_code == 200:
            return resp.json().get("hash")
    except Exception:
        pass
    return None


def _push_bundle(server: str, article_id: str, bundle_bytes: bytes) -> str:
    """POST /sync → "ok" | "conflict" | "error"."""
    try:
        resp = httpx.post(
            f"{_api_url(server, article_id)}/sync",
            content=bundle_bytes,
            headers={"Content-Type": "application/octet-stream"},
            timeout=60,
        )
        if resp.status_code == 200:
            return "ok"
        if resp.status_code == 409:
            return "conflict"
    except Exception:
        pass
    return "error"


def _server_has_ancestor(server: str, article_id: str, maybe_ancestor: str) -> bytes | None:
    """Check if *maybe_ancestor* is in server's history.

    Returns the incremental bundle bytes if yes (caller reuses them — no
    double download), None if no.
    """
    return _fetch_bundle(server, article_id, maybe_ancestor)


def _fetch_bundle(server: str, article_id: str, since_hash: str | None) -> bytes | None:
    """GET /bundle?since= → bundle bytes, or None."""
    try:
        resp = httpx.get(
            f"{_api_url(server, article_id)}/bundle",
            params={"since": since_hash} if since_hash else None,
            timeout=60,
        )
        if resp.status_code == 200 and resp.content:
            return resp.content
    except Exception:
        pass
    return None


def _post_article(server: str, article_id: str, bundle_b64: str) -> bool:
    """POST /articles with base64 tar.gz → True on success."""
    try:
        resp = httpx.post(
            f"{_api_url(server, '')}s",
            json={
                "id": article_id,
                "title": "",
                "content": "",
                "format": "markdown",
                "commit_message": "Initial push",
                "repo_bundle": bundle_b64,
            },
            timeout=60,
        )
        return resp.status_code in (200, 201)
    except Exception:
        return False
