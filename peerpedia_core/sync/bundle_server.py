# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Server-side bundle handlers — mirror of ``bundle_client``.

These functions receive decoded HTTP request data and call into
``git_bundle`` and ``commands``.  They contain no HTTP code — the HTTP
layer (``server/main.py``) calls them after parsing requests and checking
permissions.

Every function that accepts or produces bytes is the server-side mirror of
a client operation in ``bundle_client.py``.
"""

import base64
import io
import tarfile
from pathlib import Path

from sqlalchemy.orm import Session

from peerpedia_core.commands import apply_sync_bundle
from peerpedia_core.storage.git_backend import DEFAULT_ARTICLES_DIR
from peerpedia_core.sync.git_bundle import (
    create_bundle,
    ingest_bundle,
    is_ancestor,
)


def serve_get_head(repo_path: Path) -> str | None:
    """Return the HEAD hash for an article repo, or None if not found.

    Called by the HTTP layer for ``GET /head``.
    """
    import git

    if not (repo_path / ".git").is_dir():
        return None
    repo = git.Repo(repo_path)
    try:
        return repo.head.commit.hexsha
    except (ValueError, git.GitError):
        return None


def serve_post_sync(db: Session, article_id: str, bundle_bytes: bytes) -> str:
    """Apply an incoming git bundle and reconcile DB state.

    1. ``ingest_bundle`` — verify + fetch objects (pure git)
    2. ``apply_sync_bundle`` — merge + DB reconcile (via commands)

    Fast-forward only — diverged histories raise MergeConflictError
    so the client pulls and retries.

    Called by the HTTP layer for ``POST /sync``.
    Returns the new HEAD hash.
    """
    rp = DEFAULT_ARTICLES_DIR / article_id
    ingest_bundle(rp, bundle_bytes)
    return apply_sync_bundle(db, article_id, ff_only=True)


def serve_get_bundle(repo_path: Path, since_hash: str | None) -> bytes | None:
    """Return a git bundle from *since_hash* to HEAD.

    *since_hash=None* → full bundle from the beginning.

    Called by the HTTP layer for ``GET /bundle?since=``.
    """
    if since_hash is None:
        return _create_full_bundle(repo_path)
    return create_bundle(repo_path, since_hash)


def serve_get_ancestor(repo_path: Path, hash: str) -> bool:
    """Check if *hash* is an ancestor of HEAD.

    Called by the HTTP layer for ``GET /ancestor/{hash}``.
    Returns True (200) or False (404).
    """
    return is_ancestor(repo_path, hash)


def serve_post_articles(repo_path: Path, payload: dict) -> str:
    """Create a new article from a full-repo tar.gz upload.

    *payload* must contain:
      - ``id``: article ID (directory name)
      - ``repo_bundle``: base64-encoded tar.gz of the full git repo

    Called by the HTTP layer for ``POST /articles`` (first-ever push).

    Returns the HEAD hash of the newly created article.
    """
    # Decode and extract the tar.gz
    bundle_bytes = base64.b64decode(payload["repo_bundle"])
    with tarfile.open(fileobj=io.BytesIO(bundle_bytes), mode="r:gz") as tar:
        tar.extractall(path=DEFAULT_ARTICLES_DIR)

    return serve_get_head(repo_path)


# ── Internal helpers ─────────────────────────────────────────────────────────


def _create_full_bundle(repo_path: Path) -> bytes:
    """Create a full git bundle containing all commits (no since_hash)."""
    import git
    import tempfile

    if not (repo_path / ".git").is_dir():
        raise FileNotFoundError(f"Git repo not found: {repo_path}")

    repo = git.Repo(repo_path)
    with tempfile.NamedTemporaryFile(suffix=".bundle", delete=False) as f:
        bundle_path = f.name
    try:
        repo.git.bundle("create", bundle_path, "HEAD")
        return Path(bundle_path).read_bytes()
    finally:
        Path(bundle_path).unlink(missing_ok=True)
