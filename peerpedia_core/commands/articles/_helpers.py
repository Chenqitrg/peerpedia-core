# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Shared helpers for article sub-modules."""

from __future__ import annotations

from pathlib import Path

from peerpedia_core.storage.db import Session, crud_maintainer
from peerpedia_core.exceptions import NotFoundError, NotAuthorizedError
from peerpedia_core.storage.db.crud_article import (
    add_article_authors,
    get_article as _get_article,
    get_author_ids as _get_author_ids,
    set_sink_start,
)
from peerpedia_core.storage.db.crud_user import get_user as _get_user
from peerpedia_core.storage.git_backend import (
    DEFAULT_ARTICLES_DIR, commit_status_marker, get_commit_authors, get_head_hash,
)
from peerpedia_core.storage.db.models import Article, User


def require_user(db: Session, user_id: str) -> User:
    """Return the user or raise NotFoundError.

    Eliminates the repeated ``user = get_user(db, uid); if user is None: raise``
    pattern that appears in 11+ command functions.
    """
    user = _get_user(db, user_id)
    if user is None:
        raise NotFoundError("User not found", resource_type="user", resource_id=user_id)
    return user


def require_article(db: Session, article_id: str) -> Article:
    """Return the article or raise NotFoundError.

    Eliminates the repeated ``article = get_article(db, aid); if article is None: raise``
    pattern that appears in 10+ command functions.
    """
    article = _get_article(db, article_id)
    if article is None:
        raise NotFoundError("Article not found", resource_type="article", resource_id=article_id)
    return article


def require_article_repo(article_id: str) -> Path:
    """Return the article repo path or raise NotFoundError.

    Eliminates the repeated ``rp = DEFAULT_ARTICLES_DIR / aid; if not (rp / ".git").is_dir(): raise``
    pattern that appears in 9+ locations.
    """
    rp = DEFAULT_ARTICLES_DIR / article_id
    if not (rp / ".git").is_dir():
        raise NotFoundError("Article repo not found", resource_type="article", resource_id=article_id)
    return rp


def reset_sink(db: Session, article_id: str, rp: Path, extra_days: int) -> None:
    """Write status marker to git and reset sink timer.

    Eliminates the repeated ``commit_status_marker + set_sink_start`` pair.
    """
    commit_status_marker(rp, "sedimentation")
    set_sink_start(db, article_id, extra_days)


def rebuild_article_authors(db: Session, article_id: str, since_hash: str | None = None) -> None:
    """Read author IDs from new git commits and merge them into DB.

    This is **incremental** — only adds new authors discovered in commits
    since ``since_hash`` (or ``last_author_rebuild_hash``).  It never removes
    authors already in the DB, even if they are no longer in git history.
    For a full replacement use ``crud_article.set_article_authors`` directly.

    Sets ``last_author_rebuild_hash`` to the current HEAD so the next
    rebuild only scans new commits.

    Raises NotFoundError if the article does not exist.
    """
    article = _get_article(db, article_id)
    if article is None:
        raise NotFoundError(f"Article not found: {article_id}")

    rp = DEFAULT_ARTICLES_DIR / article_id
    head_hash = get_head_hash(rp)
    new_ids = get_commit_authors(rp, since_hash=since_hash)

    existing = set(_get_author_ids(db, article_id))
    new_only = [a for a in new_ids if a not in existing]
    if new_only:
        add_article_authors(db, article_id, new_only)

    article.last_author_rebuild_hash = head_hash


def _assert_caller_is_maintainer(db: Session, article_id: str, caller_id: str) -> None:
    """Raise if *caller_id* is not a maintainer of *article_id*."""
    caller = _get_user(db, caller_id)
    if caller is None:
        raise NotFoundError("Caller not found")
    article = _get_article(db, article_id)
    if article is None:
        raise NotFoundError("Article not found")
    if not crud_maintainer.is_maintainer(db, article_id, caller_id):
        raise NotAuthorizedError(
            f"User {caller_id} is not a maintainer of script {article_id}"
        )
