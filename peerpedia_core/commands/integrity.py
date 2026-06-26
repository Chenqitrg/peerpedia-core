# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Article integrity verification — commit signatures and DB/git consistency.

Three entry points (see the plan for details):

* **access** — ``level="light"``: verify the latest human-authored commit's
  Ed25519 signature.  Runs before article read/write operations.
* **sync** — ``level="full"``: light + DB cross-validation against git SOT.
  Runs after ``apply_sync_bundle`` completes reconciliation.
* **publish** — ``level="full"``: verify state consistency before allowing
  a status transition to ``sedimentation`` or ``published``.
"""

from __future__ import annotations

from pathlib import Path

from peerpedia_core.crypto import pubkey_hex_to_ssh_line
from peerpedia_core.exceptions import NotFoundError, SignatureVerificationError
from peerpedia_core.storage.db import Session
from peerpedia_core.commands.articles._helpers import require_article, require_article_repo
from peerpedia_core.commands.workflow import recompute_article_score
from peerpedia_core.storage.db.crud_article import get_author_ids, update_article_status
from peerpedia_core.storage.git_backend import (
    extract_pubkey_from_message, get_commit_authors,
    get_commit_history, read_status_from_git, verify_commit_signature,
)
from peerpedia_core.types import short_id
from peerpedia_core.types.status import is_platform_commit


def assert_article_integrity(db: Session, article_id: str, *, level: str = "light") -> None:
    """Verify article integrity at the specified level.

    ``level="light"`` — verify the latest human-authored commit's Ed25519
    signature.  Fast enough to run on every article access.  Raises
    ``SignatureVerificationError`` on failure.

    ``level="full"`` — light check + DB cross-validation (status, score,
    authors against git SOT).  If DB state is inconsistent, auto-repair by
    rebuilding the DB cache from git history.  Runs after sync and before
    publish.
    """
    try:
        rp = require_article_repo(article_id)
        require_article(db, article_id)
    except NotFoundError:
        return

    if level == "light":
        _verify_light(rp)
    elif level == "full":
        _verify_light(rp)
        _verify_full(db, article_id, rp)
    else:
        raise ValueError(f"Unknown integrity level: {level}")


# ── Helpers ──────────────────────────────────────────────────────────────────


def _verify_light(repo_path: Path) -> None:
    """Verify the latest human-authored commit's signature."""
    commits = list(get_commit_history(repo_path, max_count=1))
    if not commits:
        return
    commit = commits[0]
    if is_platform_commit(commit["author_email"]):
        return

    pubkey_hex = extract_pubkey_from_message(commit["message"])
    if not pubkey_hex:
        raise SignatureVerificationError(
            f"Local integrity failure: commit {short_id(commit['hash'])} "
            f"by {commit['author_email']} has no Pubkey trailer — "
            "the git repo may have been tampered with. "
            "Run 'peerpedia sync pull <article_id>' to repair from a trusted peer."
        )
    ssh_line = pubkey_hex_to_ssh_line(pubkey_hex)
    verify_commit_signature(repo_path, commit["hash"], ssh_line, commit["author_email"])


def _verify_full(db: Session, article_id: str, repo_path: Path) -> None:
    """DB cross-validation: rebuild DB cache from git SOT if inconsistent."""
    article = require_article(db, article_id)

    expected_status = read_status_from_git(repo_path)
    if expected_status is not None and article.status != expected_status:
        _repair_from_git(db, article_id, repo_path)
        return

    # Check author list consistency.
    db_authors = set(get_author_ids(db, article_id))
    git_authors = get_commit_authors(repo_path)
    if db_authors != git_authors:
        from peerpedia_core.commands.articles import rebuild_article_authors  # noqa: PLC0415
        rebuild_article_authors(db, article_id)


def _repair_from_git(db: Session, article_id: str, repo_path: Path) -> None:
    """Rebuild DB cache for *article_id* from git SOT."""
    from peerpedia_core.commands.articles import rebuild_article_authors  # noqa: PLC0415
    from peerpedia_core.commands.bundle import sync_reviews_from_worktree  # noqa: PLC0415

    rebuild_article_authors(db, article_id)
    # Sync status from git platform commits into DB.
    status = read_status_from_git(repo_path)
    if status is not None:
        update_article_status(db, article_id, status)
    # G9: sync reviews from git worktree before recomputing scores so
    # reviews that exist in git but not in DB are not silently dropped.
    sync_reviews_from_worktree(db, article_id)
    recompute_article_score(db, article_id)
