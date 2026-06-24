# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

r"""Article permission policy — pure authorization rules.

**Hard constraint**: this module only imports ``storage.db.models`` (type
definitions) and ``exceptions``.  It does NOT import CRUD functions,
``git_backend``, or any database operation library.  All data is passed
in by the caller.

Every function takes pre-fetched data (Article, author_ids, maintainer_ids)
and either returns the article or raises a semantic exception.  The caller
(``commands/``) is responsible for fetching data before calling.

TODO(moderation): users cannot delete published articles by design
(influence is irreversible), but there is no platform-level moderation
layer to remove illegal/harmful content.  Needs: admin role, article
hide/delete by admin, report mechanism, content review workflow.

Permission matrix
-----------------

| Operation   | Function                      | Who              | Allowed statuses        |
|-------------|-------------------------------|------------------|-------------------------|
| Read        | assert_can_read_article       | Anyone           | sedimentation, published|
|             |                               | Author           | draft, sedimentation, published |
| Download    | assert_can_download_content   | Anyone           | published               |
|             |                               | Author           | any                     |
| Edit        | assert_can_edit_article       | Maintainer only  | draft, published        |
| Delete      | assert_can_delete_article     | Maintainer only  | draft                   |
| Publish     | assert_can_publish_article    | Maintainer only  | draft, published        |
| Rollback    | assert_can_rollback_article   | Maintainer only  | draft, published        |
| Fork        | assert_can_fork_article       | Anyone (no dupe) | published               |
| Review      | assert_can_submit_review      | Anyone           | sedimentation, published|
| Extend sink | assert_can_extend_sink        | Maintainer only  | sedimentation           |
| Sync        | assert_can_sync_article       | Maintainer only  | draft, published        |
| Accept merge| assert_can_accept_merge       | Maintainer only  | draft, published        |

Key: sedimentation articles are immutable — even a maintainer cannot edit,
delete, rollback, or sync during the peer-review window.

Callers
-------
All ``assert_can_*`` functions are called from ``commands/``.  The caller
must fetch the ``Article`` and any needed IDs (author / maintainer) before
invoking the policy function.

Reviewer's checklist
--------------------
- Does every new command function call the right policy check before mutating?
- Does the caller fetch all required data BEFORE calling the policy?
- Are new statuses added to the right visibility/writable sets?
"""

from __future__ import annotations

from typing import Optional

from peerpedia_core.exceptions import BadRequestError, ConflictError, NotAuthorizedError
from peerpedia_core.storage.db.models import Article, Review, User

# ═══════════════════════════════════════════════════════════════════════════════
# Visibility rules
# ═══════════════════════════════════════════════════════════════════════════════

PUBLIC_READABLE_STATUSES = {"sedimentation", "published"}
FORKABLE_STATUSES = {"published"}
PUBLIC_DOWNLOADABLE_STATUSES = {"published"}

# Sedimentation articles are immutable.
_WRITABLE_STATUSES = {"draft", "published"}


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
# Pure helpers
# ═══════════════════════════════════════════════════════════════════════════════


def _is_author(author_ids: list[str], user: User | None) -> bool:
    """Check content contribution — user is an ArticleAuthor."""
    if user is None:
        return False
    return user.id in author_ids


def _is_maintainer(maintainer_ids: list[str], user: User) -> bool:
    """Check management authority — user is a ScriptMaintainer.

    *user* must be a resolved User object — callers must validate
    existence before calling.  Passing None raises AttributeError
    (fail fast, don't silently return False).
    """
    return user.id in maintainer_ids


def _assert_maintainer(
    article: Article,
    maintainer_ids: list[str],
    user: User,
    action: str,
    allowed_statuses: set[str] | None = None,
) -> None:
    """Raise if *user* is not a maintainer or *article* status is wrong."""
    eff = allowed_statuses if allowed_statuses is not None else _WRITABLE_STATUSES
    if not _is_maintainer(maintainer_ids, user):
        raise NotAuthorizedError(
            f"User {user.id} is not a maintainer of script {article.id}"
        )
    if article.status not in eff:
        raise NotAuthorizedError(
            f"Cannot {action} an article in {article.status} status"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Read permissions
# ═══════════════════════════════════════════════════════════════════════════════


def assert_can_read_article(
    article: Article,
    author_ids: list[str],
    user: User | None,
) -> Article:
    """Raise if *user* is not allowed to read this article."""
    if article.status in PUBLIC_READABLE_STATUSES:
        return article
    if _is_author(author_ids, user):
        return article
    raise NotAuthorizedError("Article is private")


def assert_can_download_content(
    article: Article,
    author_ids: list[str],
    user: User | None,
) -> Article:
    """Raise if *user* cannot download article content."""
    if article.status in PUBLIC_DOWNLOADABLE_STATUSES:
        return article
    if _is_author(author_ids, user):
        return article
    raise NotAuthorizedError("Content download not available for this article")


# ═══════════════════════════════════════════════════════════════════════════════
# Write permissions — maintainer-gated, status-gated
# ═══════════════════════════════════════════════════════════════════════════════


def assert_can_edit_article(article: Article, maintainer_ids: list[str], user: User) -> Article:
    """Raise if *user* is not a maintainer, or article is in sedimentation.

    Maintainers can edit articles in ``draft`` or ``published`` status.
    Sedimentation articles are immutable — they cannot be edited during
    the peer-review window.
    """
    _assert_maintainer(article, maintainer_ids, user, "edit")
    return article


def assert_can_delete_article(article: Article, maintainer_ids: list[str], user: User) -> Article:
    """Raise if *user* is not a maintainer, or article is not in ``draft``.

    Only draft articles can be deleted.  Once published or in
    sedimentation, the article is part of the permanent record.
    """
    _assert_maintainer(article, maintainer_ids, user, "delete", allowed_statuses={"draft"})
    return article


def assert_can_rollback_article(article: Article, maintainer_ids: list[str], user: User) -> Article:
    """Raise if *user* is not a maintainer, or article is in sedimentation.

    Rollback creates a forward commit (never rewrites history), so it is
    allowed on draft and published articles but NOT during sedimentation
    when the article is under active peer review.
    """
    _assert_maintainer(article, maintainer_ids, user, "rollback")
    return article


def assert_can_publish_article(article: Article, maintainer_ids: list[str], user: User) -> Article:
    """Raise if *user* is not a maintainer, or article is in sedimentation.

    Publishing transitions a draft article into the sedimentation pool
    for peer review.  Once in sedimentation, an article publishes
    automatically when the sink timer expires — manual re-publish is
    not allowed.

    TODO: unanimous consent — all maintainers must confirm before publishing.
    """
    _assert_maintainer(article, maintainer_ids, user, "publish")
    return article


def assert_can_accept_merge(article: Article, maintainer_ids: list[str], user: User) -> Article:
    """Raise if *user* is not a maintainer, or article is in sedimentation.

    Merge proposals can be accepted on draft or published articles.
    Sedimentation articles are immutable during peer review.

    TODO: consent model — merge acceptance should require all maintainers.
    """
    _assert_maintainer(article, maintainer_ids, user, "accept merge")
    return article


def assert_can_submit_review(article: Article) -> Article:
    """Raise if reviews are not accepted for *article*.

    Sedimentation and published articles accept community reviews,
    including from authors.
    """
    if article.status in ("sedimentation", "published"):
        return article
    raise NotAuthorizedError("Cannot review a draft article")


def assert_can_extend_sink(article: Article, maintainer_ids: list[str], user: User) -> Article:
    """Raise if *user* is not a maintainer, or article is not in sedimentation.

    Only sedimentation articles can have their sink timer extended.
    The caller must also enforce the maximum total sink duration
    (``params.sink.max_days``).
    """
    _assert_maintainer(article, maintainer_ids, user, "extend sink", allowed_statuses={"sedimentation"})
    return article


def assert_can_sync_article(article: Article, maintainer_ids: list[str], user: User) -> Article:
    """Raise if *user* is not a maintainer, or article is in sedimentation.

    Sync (P2P bundle exchange) is allowed on draft and published articles.
    Sedimentation articles are immutable — sync would change the content
    under active peer review.
    """
    _assert_maintainer(article, maintainer_ids, user, "sync")
    return article


# ═══════════════════════════════════════════════════════════════════════════════
# Fork — status-gated + duplicate check
# ═══════════════════════════════════════════════════════════════════════════════


def assert_can_fork_article(
    article: Article,
    existing_fork: Article | None,
) -> Article:
    """Raise if the article cannot be forked by *user*.

    Checks (in order):
    1. Status is forkable (``published`` only)
    2. User has not already forked this article
    """
    if article.status not in FORKABLE_STATUSES:
        raise NotAuthorizedError("Only published articles can be forked")

    if existing_fork is not None:
        raise ConflictError("Already forked this article")

    return article


# ═══════════════════════════════════════════════════════════════════════════════
# Publish — self-review gate
# ═══════════════════════════════════════════════════════════════════════════════


def require_self_review_for_publish(
    article: Article,
    existing_review: Review | None,
) -> None:
    """Raise if the article lacks a self-review by *user* at current HEAD.

    The caller must have already verified the git repo exists and has a
    HEAD, fetched the article, and looked up the self-review.
    """
    if existing_review is None:
        raise BadRequestError("self_review is required before publishing")

    if article.score is None:
        raise BadRequestError("Article must have a score before publishing")
