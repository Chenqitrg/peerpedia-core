# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""DB-layer guard functions — fail-fast, reference message codes."""

from __future__ import annotations

from peerpedia_core.exceptions import (
    BadRequestError, ConflictError, NotFoundError, NotAuthorizedError,
)
from peerpedia_core.storage.db import Session
from peerpedia_core.storage.db._validators import (
    require_alias_nonempty, require_draft_status,
    require_helpfulness_score_range, require_keys, require_merge_proposal_open,
    require_not_same, require_sedimentation, require_signing_key,
    require_title_nonempty, validate_follow_entries,
)
from peerpedia_core.config.params import params
from peerpedia_core.rules.articles import assert_not_folded
from peerpedia_core.storage.db.crud_article import count_articles, get_article
from peerpedia_core.storage.db.crud_maintainer import get_maintainer_ids, is_maintainer
from peerpedia_core.storage.db.crud_merge import get_merge_proposal
from peerpedia_core.storage.db.crud_review import (
    get_accepted_invitation, get_pending_invitation, get_reviews_for_article,
)
from peerpedia_core.storage.db.crud_user import get_user_by_id
from peerpedia_core.storage.db.crud_follow import is_following
from peerpedia_core.storage.db.models import (
    ArticleMetaStorage, MergeProposalStorage, ReviewMetaStorage, UserStorage,
)
from peerpedia_core.types.status import ArticleStatus


def require_user(db: Session, user_id: str) -> UserStorage:
    """Return the user or raise NotFoundError."""
    user = get_user_by_id(db, user_id)
    if user is None:
        raise NotFoundError(code="USER_NOT_FOUND",
                            resource_type="user", resource_id=user_id)
    return user


def require_article(db: Session, article_id: str) -> ArticleMetaStorage:
    """Return the article or raise NotFoundError."""
    article = get_article(db, article_id)
    if article is None:
        raise NotFoundError(code="ARTICLE_NOT_FOUND",
                            resource_type="article", resource_id=article_id)
    return article


def require_maintainer(db: Session, article_id: str, user_id: str) -> None:
    """Raise NotAuthorizedError if *user_id* is not a maintainer."""
    if user_id not in get_maintainer_ids(db, article_id):
        raise NotAuthorizedError(code="NOT_MAINTAINER")


def assert_caller_is_maintainer(db: Session, article_id: str, caller_id: str) -> None:
    """Raise if *caller_id* is not a maintainer of *article_id*."""
    if get_user_by_id(db, caller_id) is None:
        raise NotFoundError(code="USER_NOT_FOUND",
                            resource_type="user", resource_id=caller_id)
    if get_article(db, article_id) is None:
        raise NotFoundError(code="ARTICLE_NOT_FOUND",
                            resource_type="article", resource_id=article_id)
    if not is_maintainer(db, article_id, caller_id):
        raise NotAuthorizedError(code="NOT_MAINTAINER")


def guard_not_already_maintainer(db: Session, article_id: str, user_id: str) -> None:
    """Raise ConflictError if *user_id* is already a maintainer."""
    if is_maintainer(db, article_id, user_id):
        raise ConflictError(code="ALREADY_MAINTAINER")


def require_authors_exist(db: Session, author_ids: list[str]) -> None:
    """Raise NotFoundError if any author does not exist."""
    for aid in author_ids:
        require_user(db, aid)


def require_following_for_alias(db: Session, owner_id: str, target_id: str) -> None:
    """Raise BadRequestError if *owner_id* does not follow *target_id*."""
    if not is_following(db, owner_id, target_id):
        raise BadRequestError(code="MUST_FOLLOW_FOR_ALIAS")


def require_review(db: Session, article_id: str, reviewer_id: str) -> ReviewMetaStorage:
    """Return the review by *reviewer_id* or raise NotFoundError."""
    for r in get_reviews_for_article(db, article_id):
        if r.reviewer_id == reviewer_id:
            return r
    raise NotFoundError(code="REVIEW_NOT_FOUND",
                        resource_type="review", resource_id=reviewer_id)


def authorize_article_action(
    db: Session, article_id: str, user_id: str,
) -> tuple[UserStorage, ArticleMetaStorage, list[str]]:
    """Resolve user, article, and maintainer_ids; block if article is folded."""
    user = require_user(db, user_id)
    article = require_article(db, article_id)
    mids = get_maintainer_ids(db, article_id)
    assert_not_folded(article, threshold=params.reputation.fold_score_threshold)
    return user, article, mids


def guard_sedimentation_limit(db: Session, user_id: str) -> None:
    """Raise BadRequestError if *user_id* has too many articles in sedimentation."""
    in_pool = count_articles(db, statuses={ArticleStatus.SEDIMENTATION}, author_id=user_id)
    if in_pool >= params.sink.max_sedimentation_per_author:
        raise BadRequestError(code="SEDIMENTATION_LIMIT",
                              count=in_pool,
                              max=params.sink.max_sedimentation_per_author)


def require_invitation(db: Session, article_id: str, reviewer_id: str) -> None:
    """Raise NotAuthorizedError if the reviewer lacks an accepted invitation."""
    if get_accepted_invitation(db, article_id, reviewer_id) is None:
        raise NotAuthorizedError(code="NO_INVITATION")


def guard_invitation_not_declined(db: Session, article_id: str, reviewer_id: str) -> None:
    """Raise BadRequestError if invitation was already declined."""
    declined = (
        db.query(ReviewMetaStorage)
        .filter(ReviewMetaStorage.article_id == article_id,
                ReviewMetaStorage.reviewer_id == reviewer_id,
                ReviewMetaStorage.status == "declined")
        .first()
    )
    if declined is not None:
        raise BadRequestError(code="INVITATION_DECLINED")


def guard_invitation_not_accepted(db: Session, article_id: str, reviewer_id: str) -> None:
    """Raise BadRequestError if invitation was already accepted."""
    if get_accepted_invitation(db, article_id, reviewer_id) is not None:
        raise BadRequestError(code="INVITATION_ACCEPTED_ALREADY")


def guard_not_last_maintainer(db: Session, article_id: str, caller_id: str,
                               user_id: str) -> None:
    """Raise NotAuthorizedError if caller tries to self-remove as the last maintainer."""
    if caller_id != user_id:
        return
    if len(get_maintainer_ids(db, article_id)) <= 1:
        raise NotAuthorizedError(code="LAST_MAINTAINER")


def require_open_proposal(db: Session, proposal_id: str,
                           article_id: str) -> MergeProposalStorage:
    """Return the merge proposal, or raise if missing/wrong article/not open."""
    mp = get_merge_proposal(db, proposal_id)
    if mp is None:
        raise NotFoundError(code="MERGE_PROPOSAL_NOT_FOUND")
    if mp.target_article_id != article_id:
        raise BadRequestError(code="MERGE_PROPOSAL_WRONG_ARTICLE")
    if mp.status != "open":
        raise BadRequestError(code="MERGE_PROPOSAL_CLOSED",
                              proposal_id=proposal_id, status=mp.status)
    return mp
