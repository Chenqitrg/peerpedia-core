# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

r"""Article permission policy — centralized visibility and authorization.

Every endpoint must call the appropriate ``assert_can_*`` function instead
of duplicating ``current_user.id in get_author_ids(...)``.  All functions
raise semantic exceptions (``NotFoundError``, ``NotAuthorizedError``,
``ConflictError``, ``BadRequestError``) — no HTTP dependency.

Permission matrix
-----------------

| Operation   | Function                      | Who              | Allowed statuses        |
|-------------|-------------------------------|------------------|-------------------------|
| Read        | assert_can_read_article       | Anyone           | sedimentation, published|
|             |                               | Author           | draft, sedimentation, published |
| Download    | assert_can_download_content   | Anyone           | published               |
|             |                               | Author           | any                     |
| Edit        | assert_can_edit_article       | Maintainer only  | draft, published        |
| Delete      | assert_can_delete_article     | Maintainer only  | draft, published        |
| Publish     | assert_can_publish_article    | Maintainer only  | draft, published        |
| Rollback    | assert_can_rollback_article   | Maintainer only  | draft, published        |
| Fork        | assert_can_fork_article       | Anyone (no dupe) | published               |
| Review      | assert_can_submit_review      | Anyone           | sedimentation, published|
| Extend sink | assert_can_extend_sink        | Maintainer only  | sedimentation           |
| Sync        | assert_can_sync_article       | Maintainer only  | draft, published        |
| Accept merge| assert_can_accept_merge       | Maintainer only  | draft, published        |

Key: sedimentation articles are immutable — even a maintainer cannot edit,
delete, rollback, or sync during the peer-review window.

Visibility rules
----------------
- ``PUBLIC_READABLE_STATUSES = {"sedimentation", "published"}``
- ``FORKABLE_STATUSES = {"published"}``
- ``PUBLIC_DOWNLOADABLE_STATUSES = {"published"}``
- ``_WRITABLE_STATUSES = {"draft", "published"}``

Callers
-------
All ``assert_can_*`` functions are called from ``commands/``.  The only
exception is ``require_self_review_for_publish``, which is called from
``commands/articles.py:publish_article`` as a secondary gate (G6).

Reviewer's checklist
--------------------
- Does every new command function call the right policy check before mutating?
- Are new statuses added to the right visibility/writable sets?
- Does ``require_self_review_for_publish`` check AFTER the self-review is
  written and the score is computed?  (The check verifies the DB cache.)
"""

from __future__ import annotations

from typing import Optional

import git as gitmod
from sqlalchemy.orm import Session

from peerpedia_core.exceptions import BadRequestError, ConflictError, NotAuthorizedError, NotFoundError
from peerpedia_core.storage.db.crud_article import get_article, get_author_ids
from peerpedia_core.storage.db.crud_maintainer import get_maintainer_ids
from peerpedia_core.storage.db.models import Article, User

# ═══════════════════════════════════════════════════════════════════════════════
# Visibility rules
# ═══════════════════════════════════════════════════════════════════════════════

# Statuses readable by anyone (unauthenticated included).
PUBLIC_READABLE_STATUSES = {"sedimentation", "published"}

# Only published articles can be forked.
FORKABLE_STATUSES = {"published"}

# Only published articles can be downloaded — source, PDF, or full git repo.
# Sedimentation articles are publicly viewable on the web page but their
# source content and compiled output are not distributed during the pool period.
PUBLIC_DOWNLOADABLE_STATUSES = {"published"}


# ═══════════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════════


def get_article_or_raise(db: Session, article_id: str) -> Article:
    a = get_article(db, article_id)
    if a is None:
        raise NotFoundError("Article not found")
    return a


def _is_author(db: Session, article_id: str, user: Optional[User]) -> bool:
    """Check content contribution — user is an ArticleAuthor."""
    if user is None:
        return False
    return user.id in get_author_ids(db, article_id)


def _is_maintainer(db: Session, article_id: str, user: User) -> bool:
    """Check management authority — user is a ScriptMaintainer.

    Maintainer is always explicitly granted; it is never derived from
    authorship.  Management operations (edit/delete/publish/sync) are
    gated on maintainer, not author.

    *user* must be a resolved User object — callers must validate
    existence before calling.  Passing None raises AttributeError
    (fail fast, don't silently return False).
    """
    return user.id in get_maintainer_ids(db, article_id)


def visible_statuses_for_user(current_user: Optional[User]) -> set[str]:
    """Return the set of statuses visible to *current_user*.

    Anonymous users see ``sedimentation`` + ``published``.
    Authenticated users additionally see their own ``draft`` articles
    (the caller must still filter by author for drafts).
    """
    if current_user is not None:
        return {"draft", "sedimentation", "published"}
    return {"sedimentation", "published"}


# ═══════════════════════════════════════════════════════════════════════════════
# Read permissions
# ═══════════════════════════════════════════════════════════════════════════════


def assert_can_read_article(
    db: Session,
    article_id: str,
    current_user: Optional[User],
) -> Article:
    """Raise if *current_user* is not allowed to read this article."""
    a = get_article_or_raise(db, article_id)
    if a.status in PUBLIC_READABLE_STATUSES:
        return a
    if _is_author(db, article_id, current_user):
        return a
    raise NotAuthorizedError("Article is private")


def assert_can_download_content(
    db: Session,
    article_id: str,
    current_user: Optional[User],
) -> Article:
    """Raise if *current_user* cannot download article content.

    Source files, compiled PDF, and full git repo are all treated the
    same: only published articles are publicly downloadable.  During the
    sedimentation pool period content is viewable on the web but not
    distributed.
    """
    a = get_article_or_raise(db, article_id)
    if a.status in PUBLIC_DOWNLOADABLE_STATUSES:
        return a
    if _is_author(db, article_id, current_user):
        return a
    raise NotAuthorizedError("Content download not available for this article")


# ═══════════════════════════════════════════════════════════════════════════════
# Write permissions — maintainer-gated, status-gated
# ═══════════════════════════════════════════════════════════════════════════════

# Sedimentation articles are immutable — even a maintainer cannot edit, delete,
# rollback, or sync during the peer-review window.  Draft and published
# articles accept writes (published will eventually go through a PR flow).
_WRITABLE_STATUSES = {"draft", "published"}


def _assert_is_maintainer(
    db: Session,
    article_id: str,
    current_user: User,
    action: str,
    allowed_statuses: set[str] | None = None,
) -> Article:
    """Gate management operations on maintainer role, not authorship."""
    eff = allowed_statuses if allowed_statuses is not None else _WRITABLE_STATUSES
    a = get_article_or_raise(db, article_id)
    if not _is_maintainer(db, article_id, current_user):
        raise NotAuthorizedError(f"User {current_user.id} is not a maintainer of script {article_id}")
    if a.status not in eff:
        raise NotAuthorizedError(
            f"Cannot {action} an article in {a.status} status"
        )
    return a


def assert_can_edit_article(db: Session, article_id: str, current_user: User) -> Article:
    return _assert_is_maintainer(db, article_id, current_user, "edit")


def assert_can_delete_article(db: Session, article_id: str, current_user: User) -> Article:
    return _assert_is_maintainer(db, article_id, current_user, "delete", allowed_statuses={"draft"})


def assert_can_rollback_article(db: Session, article_id: str, current_user: User) -> Article:
    return _assert_is_maintainer(db, article_id, current_user, "rollback")


def assert_can_publish_article(db: Session, article_id: str, current_user: User) -> Article:
    # TODO: unanimous consent — all maintainers must confirm before publishing.
    # Currently any single maintainer can push a draft into the sedimentation pool,
    # which is irreversible.  Needs a confirmation mechanism (new table or
    # in-git sign-off) that gates the publish action on every maintainer's approval.
    return _assert_is_maintainer(db, article_id, current_user, "publish")


def assert_can_accept_merge(db: Session, article_id: str, current_user: User) -> Article:
    # TODO: consent model — not every maintainer should be able to accept a merge
    # unilaterally.  The current "any maintainer" check is a permission gap —
    # merge acceptance should require explicit consent from all target
    # maintainers.  Needs a consent model before tightening.
    return _assert_is_maintainer(db, article_id, current_user, "accept merge")


def assert_can_submit_review(db: Session, article_id: str) -> Article:
    """Raise if *current_user* cannot submit a review.

    Sedimentation and published articles accept community reviews, including authors.
    """
    a = get_article_or_raise(db, article_id)
    if a.status in ("sedimentation", "published"):
        return a
    raise NotAuthorizedError("Cannot review a draft article")


def assert_can_extend_sink(db: Session, article_id: str, current_user: User) -> Article:
    return _assert_is_maintainer(db, article_id, current_user, "extend sink", allowed_statuses={"sedimentation"})


def assert_can_sync_article(db: Session, article_id: str, current_user: User) -> Article:
    return _assert_is_maintainer(db, article_id, current_user, "sync")


# ═══════════════════════════════════════════════════════════════════════════════
# Fork — status-gated + duplicate check
# ═══════════════════════════════════════════════════════════════════════════════


def assert_can_fork_article(
    db: Session,
    article_id: str,
    current_user: User,
) -> Article:
    """Raise if the article cannot be forked by *current_user*.

    Checks (in order):
    1. Article exists
    2. Status is forkable (``published`` only)
    3. User has not already forked this article
    """
    from peerpedia_core.storage.db.crud_article import get_article_by_fork_and_author

    a = get_article_or_raise(db, article_id)

    if a.status not in FORKABLE_STATUSES:
        raise NotAuthorizedError("Only published articles can be forked")

    existing = get_article_by_fork_and_author(
        db,
        forked_from=article_id,
        author_id=current_user.id,
    )
    if existing is not None:
        raise ConflictError("Already forked this article")

    return a


# ═══════════════════════════════════════════════════════════════════════════════
# Publish — self-review gate
# ═══════════════════════════════════════════════════════════════════════════════


def require_self_review_for_publish(
    db: Session,
    article_id: str,
    current_user: User,
) -> None:
    """Raise if the current HEAD lacks a self-review by *current_user*."""
    from peerpedia_core.storage.db.models import Review
    from peerpedia_core.storage.git_backend import DEFAULT_ARTICLES_DIR

    rp = DEFAULT_ARTICLES_DIR / article_id
    if not (rp / ".git").is_dir():
        raise BadRequestError(
            "self_review is required before publishing — no git repo found",
        )

    repo = gitmod.Repo(rp)
    if not repo.head.is_valid():
        raise BadRequestError(
            "self_review is required before publishing — no commits yet",
        )

    article = get_article(db, article_id)
    if article is None:
        raise BadRequestError("Article not found")

    head = repo.head.commit.hexsha
    existing = (
        db.query(Review)
        .filter(
            Review.article_id == article_id,
            Review.reviewer_id == current_user.id,
            Review.scope == article.status,
            Review.commit_hash == head,
        )
        .first()
    )
    if existing is None:
        raise BadRequestError("self_review is required before publishing")

    # Score must be computed before entering the sedimentation pool.
    # Without a score the article cannot be ranked, forked, or evaluated.
    a = get_article(db, article_id)
    if a is not None and a.score is None:
        raise BadRequestError("Article must have a score before publishing")
