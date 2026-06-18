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
import tempfile
from pathlib import Path

import httpx

from peerpedia_core.storage.git_backend import (
    DEFAULT_ARTICLES_DIR,
    apply_bundle,
    create_bundle,
    get_commit_history,
)


def _api_url(server: str, article_id: str) -> str:
    return f"{server}/api/v1/articles/{article_id}"


def _get_server_head(server: str, article_id: str) -> str | None:
    """Get the server's HEAD hash for an article. Returns None if 404."""
    try:
        r = httpx.get(f"{_api_url(server, article_id)}/head", timeout=30)
        if r.status_code == 200:
            data = r.json()
            return data.get("hash")
    except Exception:
        pass
    return None


def push(server: str, article_id: str) -> dict:
    """Push local commits to the remote server via git bundle.

    Returns:
        {"pushed": True, "head": "<hash>"} on success
        {"pushed": False, "head": None} on failure
    """
    # 1. Get local HEAD
    history = get_commit_history(DEFAULT_ARTICLES_DIR / article_id)
    if not history:
        return {"pushed": False, "head": None}
    local_head: str = history[0]["hash"]

    # 2. Pull server changes first if server has commits we don't have
    server_head = _get_server_head(server, article_id)
    if server_head and server_head != local_head:
        try:
            _pull_and_apply(server, article_id, local_head)
            # Refresh local HEAD after pull
            history = get_commit_history(DEFAULT_ARTICLES_DIR / article_id)
            if history:
                local_head = history[0]["hash"]
        except Exception:
            pass  # Non-fatal: continue with push anyway

    # 3. Create incremental bundle
    if server_head:
        bundle_bytes = create_bundle(DEFAULT_ARTICLES_DIR / article_id, server_head)
        if not bundle_bytes:
            return {"pushed": False, "head": None}
        # POST bundle to /sync
        try:
            r = httpx.post(
                f"{_api_url(server, article_id)}/sync",
                content=bundle_bytes,
                headers={"Content-Type": "application/octet-stream"},
                timeout=60,
            )
            if r.status_code == 200:
                data = r.json()
                return {"pushed": True, "head": data.get("head", local_head)}
            elif r.status_code == 409:
                # ff-only failed: pull + retry once
                _pull_and_apply(server, article_id, local_head)
                history = get_commit_history(DEFAULT_ARTICLES_DIR / article_id)
                if history:
                    local_head = history[0]["hash"]
                server_head = _get_server_head(server, article_id)
                if server_head:
                    bundle_bytes = create_bundle(DEFAULT_ARTICLES_DIR / article_id, server_head)
                    if bundle_bytes:
                        r2 = httpx.post(
                            f"{_api_url(server, article_id)}/sync",
                            content=bundle_bytes,
                            headers={"Content-Type": "application/octet-stream"},
                            timeout=60,
                        )
                        if r2.status_code == 200:
                            data = r2.json()
                            return {"pushed": True, "head": data.get("head", local_head)}
            return {"pushed": False, "head": None}
        except Exception:
            return {"pushed": False, "head": None}
    else:
        # First push: server doesn't have the article — upload full repo as tar.gz
        return _first_push(server, article_id, local_head)


def _first_push(server: str, article_id: str, local_head: str) -> dict:
    """Upload the full article repo as a tar.gz bundle (first-ever push)."""
    rp = DEFAULT_ARTICLES_DIR / article_id
    if not (rp / ".git").is_dir():
        return {"pushed": False, "head": None}

    # Create tar.gz of the repo
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        tar.add(str(rp), arcname=article_id)
    bundle_b64 = base64.b64encode(buf.getvalue()).decode("ascii")

    try:
        # Use a minimal create payload with repo_bundle
        r = httpx.post(
            f"{_api_url(server, '')}s",  # POST /articles
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
        if r.status_code in (200, 201):
            return {"pushed": True, "head": local_head}
    except Exception:
        pass
    return {"pushed": False, "head": None}


def pull(server: str, article_id: str) -> dict:
    """Pull latest commits from the remote server.

    Returns:
        {"pulled": True, "head": "<hash>"} or {"pulled": False}
    """
    local_head = None
    history = get_commit_history(DEFAULT_ARTICLES_DIR / article_id)
    if history:
        local_head = history[0]["hash"]

    try:
        new_head = _pull_and_apply(server, article_id, local_head)
        if new_head:
            return {"pulled": True, "head": new_head}
    except Exception:
        pass
    return {"pulled": False}


def _pull_and_apply(server: str, article_id: str, since_hash: str | None = None) -> str | None:
    """Download and apply an incremental git bundle from the server.

    Returns the new HEAD hash, or None on failure.
    """
    params = {}
    if since_hash:
        params["since"] = since_hash

    r = httpx.get(
        f"{_api_url(server, article_id)}/bundle",
        params=params,
        timeout=60,
    )
    if r.status_code != 200:
        return None

    bundle_bytes = r.content
    if not bundle_bytes:
        return None

    apply_bundle(DEFAULT_ARTICLES_DIR / article_id, bundle_bytes)

    history = get_commit_history(DEFAULT_ARTICLES_DIR / article_id)
    if history:
        return history[0]["hash"]
    return None
