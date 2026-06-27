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

from pathlib import Path

from peerpedia_core.exceptions import ConflictError
from peerpedia_core.storage.db import Session

from peerpedia_core.core import get_commit_history, publish_ready_articles, read_article_source
from peerpedia_core.core.reconcile import reconcile_after_sync
from peerpedia_core.storage.git import (
    create_bundle,
    get_head as _git_get_head,
    ingest_article,
    ingest_article_repo,
    ingest_bundle,
    is_ancestor,
    pack_article_repo,
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
    new_head = reconcile_after_sync(db, article_id, ff_only=True)
    publish_ready_articles(db)
    return new_head


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


# ── Article-ID-based wrappers ────────────────────────────────────────────
# Route handlers call these with article_id (str) instead of repo_path (Path).


def get_article_head(article_id: str) -> str | None:
    """Return the HEAD commit hash for *article_id*, or None."""
    return get_head(DEFAULT_ARTICLES_DIR / article_id)


def get_article_bundle(article_id: str, since_hash: str | None) -> bytes | None:
    """Return an incremental git bundle for *article_id*."""
    return get_bundle(DEFAULT_ARTICLES_DIR / article_id, since_hash)


def check_article_ancestor(article_id: str, commit_hash: str) -> bool:
    """Return True if *commit_hash* is an ancestor of *article_id*'s HEAD."""
    return check_ancestor(DEFAULT_ARTICLES_DIR / article_id, commit_hash)


def get_article_commit_history(
    article_id: str,
    *,
    max_count: int | None = None,
    since_hash: str | None = None,
) -> list[dict]:
    """Return commit history for *article_id* from git."""
    return list(get_commit_history(
        DEFAULT_ARTICLES_DIR / article_id,
        max_count=max_count,
        since_hash=since_hash,
    ))


def read_article_source_content(article_id: str) -> tuple[str, str] | None:
    """Return (content, format) for *article_id*'s source file, or None."""
    return read_article_source(DEFAULT_ARTICLES_DIR / article_id)


def ingest_first_article(article_id: str, payload: dict) -> str:
    """Ingest a first-time article upload (base64-encoded tar.gz)."""
    return ingest_article(DEFAULT_ARTICLES_DIR / article_id, payload)


def pack_article_repo_bundle(article_id: str) -> str:
    """Pack the full git repo for *article_id* as a base64-encoded tar.gz."""
    return pack_article_repo(DEFAULT_ARTICLES_DIR / article_id)
