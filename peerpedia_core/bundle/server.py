# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

r"""Server-side bundle handlers — mirror of ``bundle_client``.

These functions are the server's half of the sync protocol.  They receive
decoded HTTP request data and call into ``git_bundle`` and ``commands``.
They contain NO HTTP code — the routing layer in ``transport/http_server.py``
(Starlette/ASGI) parses requests, maps exceptions to status codes, and
calls these handlers.  Start the server with ``peerpedia server start``.

Function mapping (client → server)::

    bundle_client                         bundle_server
    ─────────────                         ─────────────
    find_merge_base  ──probe──►    check_ancestor
    pull_incremental ──GET──►      get_bundle
    push_incremental ──POST──►     apply_sync
    upload_article   ──POST──►     ingest_article
    (client asks for head)  ──GET──►      get_head

Call graph::

    get_head(repo_path) → str | None
      └─ git.Repo.head.commit.hexsha

    get_bundle(repo_path, since_hash) → bytes | None
      └─ git_bundle.create_bundle

    apply_sync(repo_path, bundle_bytes) → str
      ├─ git_bundle.ingest_bundle      (verify + fetch objects)
      └─ commands.sync.apply_sync_bundle   (merge + reconcile DB)

    check_ancestor(repo_path, hash) → bool
      └─ git_bundle.is_ancestor

    create_article(repo_path, payload) → str
      ├─ tar.gz unpack
      └─ git.Repo.init

Reviewer's checklist
--------------------
- Is every function stateless?  (No server-side session — each call is
  independent, just like git's HTTP protocol.)
- Does ``apply_sync`` call ``apply_sync_bundle`` to reconcile the DB?
- Are bundle bytes verified before being applied?  (ingest_bundle does this.)
"""

import base64
import io
import tarfile
from pathlib import Path

from peerpedia_core.exceptions import ConflictError
from peerpedia_core.storage.db import Session

from peerpedia_core.commands import apply_sync_bundle
from peerpedia_core.bundle.git_bundle import (
    create_bundle,
    get_head as _git_get_head,
    ingest_bundle,
    is_ancestor,
)

from peerpedia_core.config.paths import ARTICLES_DIR as DEFAULT_ARTICLES_DIR


def get_head(repo_path: Path) -> str | None:
    """Return the HEAD hash for an article repo, or None if not found.

    Called by the HTTP layer for ``GET /head``.
    Raises ValueError if repo exists but has no commits (empty repo).
    """
    try:
        return _git_get_head(repo_path)
    except FileNotFoundError:
        return None


def apply_sync(db: Session, article_id: str, bundle_bytes: bytes) -> str:
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


def get_bundle(repo_path: Path, since_hash: str | None) -> bytes | None:
    """Return a git bundle from *since_hash* to HEAD.

    *since_hash=None* → full bundle from the beginning.

    Called by the HTTP layer for ``GET /bundle?since=``.
    """
    return create_bundle(repo_path, since_hash)


def check_ancestor(repo_path: Path, hash: str) -> bool:
    """Check if *hash* is an ancestor of HEAD.

    Called by the HTTP layer for ``GET /ancestor/{hash}``.
    Returns True (200) or False (404).
    """
    return is_ancestor(repo_path, hash)


def ingest_article(repo_path: Path, payload: dict) -> str:
    """Receive and unpack a full article repo upload.

    *payload* must contain:
      - ``id``: article ID (directory name)
      - ``repo_bundle``: base64-encoded tar.gz of the full git repo

    Called by the HTTP layer for ``POST /articles`` (first-ever push)
    to bootstrap a new article locally from a peer's full upload.

    Returns the HEAD hash of the newly ingested article.

    Raises ConflictError if the article already exists locally.
    """
    if (repo_path / ".git").is_dir():
        raise ConflictError(f"Article already exists locally: {repo_path.name}")

    # Decode and extract the tar.gz
    bundle_bytes = base64.b64decode(payload["repo_bundle"])
    with tarfile.open(fileobj=io.BytesIO(bundle_bytes), mode="r:gz") as tar:
        tar.extractall(path=DEFAULT_ARTICLES_DIR)

    return get_head(repo_path)



