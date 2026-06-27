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

import logging

from peerpedia_core.exceptions import BadRequestError, NotFoundError
from peerpedia_core.storage.db import Session
from peerpedia_core.commands.articles._helpers import rebuild_article_authors
from peerpedia_core.commands.guards import (
    require_article, require_article_repo, require_integrity_level, require_review_scores,
)
from peerpedia_core.commands.reviews import assert_valid_review
from peerpedia_core.commands.workflow import publish_ready_articles, recompute_article_score
from peerpedia_core.storage.db.crud_article import get_author_ids, update_article_status, update_witnessed_at
from peerpedia_core.storage.db.crud_review import upsert_review
from peerpedia_core.storage.git_backend import (
    get_commit_authors, get_commit_history, get_head_hash,
    list_review_dirs, read_status_from_git, require_commit_pubkey_signature,
)
from peerpedia_core.types.status import is_platform_commit

logger = logging.getLogger(__name__)


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

    require_integrity_level(level)
    if level == "light":
        _verify_light(rp)
    else:
        _verify_light(rp)
        _verify_full(db, article_id, rp)


# ── Helpers ──────────────────────────────────────────────────────────────────


def _verify_light(repo_path: Path) -> None:
    """Verify the latest human-authored commit's signature."""
    commits = list(get_commit_history(repo_path, max_count=1))
    if not commits:
        return
    commit = commits[0]
    if is_platform_commit(commit["author_email"]):
        return

    require_commit_pubkey_signature(
        repo_path, commit["hash"], commit["message"], commit["author_email"],
    )


def _verify_full(db: Session, article_id: str, repo_path: Path) -> None:
    """DB cross-validation: rebuild DB cache from git SOT if inconsistent."""
    article = require_article(db, article_id)

    expected_status = read_status_from_git(repo_path)
    if expected_status is not None and article.status != expected_status:
        _repair_from_git(db, article_id)
        return

    # Check author list consistency.
    db_authors = set(get_author_ids(db, article_id))
    git_authors = get_commit_authors(repo_path)
    if db_authors != git_authors:
        rebuild_article_authors(db, article_id)


def sync_status_from_git(db: Session, article_id: str) -> None:
    """Read status transitions from commit messages and update DB.

    Delegates to ``git_backend.read_status_from_git`` for the git traversal.
    Raises NotFoundError if the article or its git repo is not found.
    """
    require_article(db, article_id)
    rp = require_article_repo(article_id)
    status = read_status_from_git(rp)
    if status is not None:
        update_article_status(db, article_id, status)


def sync_reviews_from_worktree(db: Session, article_id: str) -> None:
    """Sync review scores from git worktree into the DB Review cache."""
    rp = require_article_repo(article_id)
    head_hash = get_head_hash(rp)

    for dir_name in list_review_dirs(rp):
        scores = require_review_scores(rp, dir_name, article_id)
        try:
            assert_valid_review(scores, comment=None, check_comment=False)
        except BadRequestError as e:
            logger.warning(
                "Sync: skipping invalid review in %s/reviews/%s: %s",
                article_id, dir_name, e.detail,
            )
            continue
        upsert_review(
            db, article_id=article_id, commit_hash=head_hash,
            reviewer_id=dir_name, scores=scores,
        )


def rebuild_db_from_git(db: Session, article_id: str) -> None:
    """Rebuild DB caches (authors, reviews, status, score) from git SOT.

    Called after git state changes (sync merge, integrity repair) to bring
    the DB back in sync with git — the source of truth for article content.
    """
    update_witnessed_at(db, article_id)
    rebuild_article_authors(db, article_id)
    sync_reviews_from_worktree(db, article_id)
    sync_status_from_git(db, article_id)
    assert_article_integrity(db, article_id, level="full")
    recompute_article_score(db, article_id)
    publish_ready_articles(db)


def _repair_from_git(db: Session, article_id: str) -> None:
    """Rebuild DB cache for *article_id* from git SOT (integrity-triggered)."""
    rebuild_db_from_git(db, article_id)
