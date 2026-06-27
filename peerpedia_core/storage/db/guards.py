# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""DB-layer guard functions — DB access wrappers with fail-fast semantics.

Pure-logic validators live in ``storage/db/_validators.py`` (zero DB deps)
so that CRUD modules can import them without circular-dependency risk.
This module re-exports them for convenience.
"""

from __future__ import annotations

from peerpedia_core.exceptions import (
    BadRequestError, ConflictError, NotFoundError, NotAuthorizedError,
)
from peerpedia_core.storage.db import Session
from peerpedia_core.storage.db._validators import (  # re-export pure validators
    require_alias_nonempty,
    require_draft_status,
    require_helpfulness_score_range,
    require_keys,
    require_merge_proposal_open,
    require_not_same,
    require_sedimentation,
    require_signing_key,
    require_title_nonempty,
    validate_follow_entries,
)
from peerpedia_core.storage.db.crud_article import get_article
from peerpedia_core.storage.db.crud_maintainer import get_maintainer_ids, is_maintainer
from peerpedia_core.storage.db.crud_review import (
    get_accepted_invitation, get_pending_invitation, get_reviews_for_article,
)
from peerpedia_core.storage.db.crud_user import get_user, is_following
from peerpedia_core.storage.db.models import MergeProposal, Review


# ── Resource existence ─────────────────────────────────────────────────────


def require_user(db: Session, user_id: str):
    """Return the user or raise NotFoundError."""
    user = get_user(db, user_id)
    if user is None:
        raise NotFoundError("User not found", resource_type="user", resource_id=user_id)
    return user


def require_article(db: Session, article_id: str):
    """Return the article or raise NotFoundError."""
    article = get_article(db, article_id)
    if article is None:
        raise NotFoundError("Article not found", resource_type="article", resource_id=article_id)
    return article


# ── Authorization guards ───────────────────────────────────────────────────


def require_maintainer(db: Session, article_id: str, user_id: str) -> None:
    """Raise NotAuthorizedError if *user_id* is not a maintainer of the article."""
    if user_id not in get_maintainer_ids(db, article_id):
        raise NotAuthorizedError("Only article maintainers can invite reviewers")


def assert_caller_is_maintainer(db: Session, article_id: str, caller_id: str) -> None:
    """Raise if *caller_id* is not a maintainer of *article_id*."""
    if get_user(db, caller_id) is None:
        raise NotFoundError("Caller not found")
    if get_article(db, article_id) is None:
        raise NotFoundError("Article not found")
    if not is_maintainer(db, article_id, caller_id):
        raise NotAuthorizedError(
            f"User {caller_id} is not a maintainer of script {article_id}"
        )


def guard_not_already_maintainer(db: Session, article_id: str, user_id: str) -> None:
    """Raise ConflictError if *user_id* is already a maintainer of *article_id*."""
    if is_maintainer(db, article_id, user_id):
        raise ConflictError("User is already a maintainer of this script")


# ── Composite guards ───────────────────────────────────────────────────────


def require_authors_exist(db: Session, author_ids: list[str]) -> None:
    """Raise NotFoundError if any author in *author_ids* does not exist."""
    for aid in author_ids:
        require_user(db, aid)


def require_following_for_alias(db: Session, owner_id: str, target_id: str) -> None:
    """Raise BadRequestError if *owner_id* does not follow *target_id*."""
    if not is_following(db, owner_id, target_id):
        raise BadRequestError(f"You must follow {target_id} to set an alias")


def require_review(db: Session, article_id: str, reviewer_id: str):
    """Return the review by *reviewer_id* or raise NotFoundError."""
    for r in get_reviews_for_article(db, article_id):
        if r.reviewer_id == reviewer_id:
            return r
    raise NotFoundError(f"No review found for reviewer {reviewer_id}")
