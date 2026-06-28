# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Git→DB mirror — read canonical state from git, write to DB cache."""

from __future__ import annotations

import logging

from peerpedia_core.storage.db import Session
from peerpedia_core.config.paths import article_repo_path
from peerpedia_core.exceptions import BadRequestError
from peerpedia_core.storage.db.crud_article import (
    add_article_authors, list_author_ids, update_article_status, update_witnessed_at,
)
from peerpedia_core.core.reconcile.score import reconcile_score
from peerpedia_core.storage.db.crud_review import upsert_review
from peerpedia_core.storage.git import (
    get_commit_authors, get_head_hash,
    list_review_dirs, read_status_from_git,
)
from peerpedia_core.rules.reviews import assert_valid_review
from peerpedia_core.storage.db.guards import require_article
from peerpedia_core.storage.git.guards import require_article_repo, require_review_scores
from peerpedia_core.rules.reviews import require_integrity_level
from peerpedia_core.storage.git import get_head_commit
from peerpedia_core.storage.git.guards import require_commit_pubkey_signature
from peerpedia_core.types.status import is_platform_commit

logger = logging.getLogger(__name__)


def reconcile_authors(
    db: Session, article_id: str, since_hash: str | None = None,
) -> None:
    """Read author IDs from new git commits and merge them into DB."""
    article = require_article(db, article_id)
    rp = article_repo_path(article_id)
    head_hash = get_head_hash(rp)
    new_ids = get_commit_authors(rp, since_hash=since_hash)

    existing = set(list_author_ids(db, article_id))
    new_only = [a for a in new_ids if a not in existing]
    if new_only:
        add_article_authors(db, article_id, new_only)

    article.last_author_rebuild_hash = head_hash


def reconcile_reviews(db: Session, article_id: str) -> None:
    """Sync review scores from git worktree into the DB ReviewMetaStorage cache."""
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


def reconcile_status(db: Session, article_id: str) -> None:
    """Read status transitions from git commit messages and update DB."""
    require_article(db, article_id)
    rp = require_article_repo(article_id)
    status = read_status_from_git(rp)
    if status is not None:
        update_article_status(db, article_id, status)


# ── Integrity check + repair ───────────────────────────────────────────────


def reconcile_integrity(db: Session, article_id: str, *, level: str = "light") -> None:
    """Check article integrity; on ``level="full"``, repair DB from git if inconsistent.

    ``level="light"`` — verify the latest human-authored commit's signature.
    ``level="full"`` — light + cross-check DB against git, auto-repair mismatches.
    """
    try:
        rp = require_article_repo(article_id)
        require_article(db, article_id)
    except Exception:
        return

    require_integrity_level(level)
    head = get_head_commit(rp)
    if head and not is_platform_commit(head["author_email"]):
        require_commit_pubkey_signature(
            rp, head["hash"], head["message"], head["author_email"])
    if level == "full":
        _repair_db_cache(db, article_id, rp)


def _repair_db_cache(db: Session, article_id: str, repo_path) -> None:
    """Cross-check DB against git SOT; repair mismatches."""
    article = require_article(db, article_id)

    expected_status = read_status_from_git(repo_path)
    if expected_status is not None and article.status != expected_status:
        update_witnessed_at(db, article_id)
        reconcile_authors(db, article_id)
        reconcile_reviews(db, article_id)
        reconcile_status(db, article_id)
        reconcile_score(db, article_id)
        return

    db_authors = set(list_author_ids(db, article_id))
    git_authors = get_commit_authors(repo_path)
    if db_authors != git_authors:
        reconcile_authors(db, article_id)
