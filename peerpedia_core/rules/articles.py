# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

r"""Pure article authorization rules — zero IO, zero DB/git dependencies.

Every function takes pre-fetched data (ArticleMetaExchange, UserExchange, maintainer_ids, ...)
and either returns the article or raises a semantic exception.

Importable from anywhere — ``storage/db/``, ``core/``, ``cli/`` — without
circular-dependency risk.
"""

from __future__ import annotations

from typing import Optional

from peerpedia_core.exceptions import BadRequestError, ConflictError, NotAuthorizedError
from peerpedia_core.types.entities import ArticleMetaExchange, UserExchange
from peerpedia_core.types.scores import FiveDimScores
from peerpedia_core.types.status import ArticleStatus

# ═══════════════════════════════════════════════════════════════════════════════
# Status constants
# ═══════════════════════════════════════════════════════════════════════════════

PUBLIC_READABLE_STATUSES = {ArticleStatus.SEDIMENTATION, ArticleStatus.PUBLISHED, ArticleStatus.REJECTED}
FORKABLE_STATUSES = {ArticleStatus.DRAFT, ArticleStatus.PUBLISHED, ArticleStatus.REJECTED}
PUBLIC_DOWNLOADABLE_STATUSES = {ArticleStatus.PUBLISHED, ArticleStatus.REJECTED}

_WRITABLE_STATUSES = {ArticleStatus.DRAFT, ArticleStatus.SEDIMENTATION, ArticleStatus.PUBLISHED}
_SYNCABLE_STATUSES = {ArticleStatus.DRAFT, ArticleStatus.SEDIMENTATION, ArticleStatus.PUBLISHED, ArticleStatus.REJECTED}


def visible_statuses_for_user(current_user: UserExchange | None) -> set[str]:
    """Return the set of statuses visible to *current_user*."""
    if current_user is not None:
        return {ArticleStatus.DRAFT, ArticleStatus.SEDIMENTATION, ArticleStatus.PUBLISHED, ArticleStatus.REJECTED}
    return {ArticleStatus.SEDIMENTATION, ArticleStatus.PUBLISHED, ArticleStatus.REJECTED}


# ═══════════════════════════════════════════════════════════════════════════════
# Pure helpers
# ═══════════════════════════════════════════════════════════════════════════════


def _is_author(author_ids: list[str], user: UserExchange | None) -> bool:
    if user is None:
        return False
    return user.id in author_ids


def _is_maintainer(maintainer_ids: list[str], user: UserExchange) -> bool:
    return user.id in maintainer_ids


def _assert_maintainer(
    article: ArticleMetaExchange,
    maintainer_ids: list[str],
    user: UserExchange,
    action: str,
    allowed_statuses: set[str] | None = None,
) -> None:
    eff = allowed_statuses if allowed_statuses is not None else _WRITABLE_STATUSES
    if not _is_maintainer(maintainer_ids, user):
        raise NotAuthorizedError(
            f"User {user.id} is not a maintainer of script {article.id}"
        )
    if article.status not in eff:
        raise NotAuthorizedError(
            f"Cannot {action} an article in {article.status} status"
        )


def _assert_all_maintainers_consented(article: ArticleMetaExchange, maintainer_ids: list[str]) -> None:
    if len(maintainer_ids) <= 1:
        return
    consented = set(article.publish_consents or [])
    missing = [m for m in maintainer_ids if m not in consented]
    if missing:
        raise NotAuthorizedError(
            f"Unanimous consent required — {len(missing)} maintainer(s) "
            f"have not yet consented. Use 'peerpedia maintainer consent'."
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Fold (moderation)
# ═══════════════════════════════════════════════════════════════════════════════


def assert_not_folded(article, *, threshold: float = 1.0) -> None:
    """Raise NotAuthorizedError if the article's average score < *threshold*."""
    if article.score is None:
        return
    scores = article.score
    if isinstance(scores, dict):
        avg = FiveDimScores(**scores).average()
    else:
        avg = float(scores)
    if avg < threshold:
        raise NotAuthorizedError(
            "This article has been folded — "
            "interactions are disabled due to low score."
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Read permissions
# ═══════════════════════════════════════════════════════════════════════════════


def assert_can_read_article(
    article: ArticleMetaExchange,
    author_ids: list[str],
    user: UserExchange | None,
) -> ArticleMetaExchange:
    if article.status in PUBLIC_READABLE_STATUSES:
        return article
    if _is_author(author_ids, user):
        return article
    raise NotAuthorizedError(code="PRIVATE_ARTICLE")


def assert_can_access_content(
    article: ArticleMetaExchange,
    author_ids: list[str],
    user: UserExchange | None,
) -> ArticleMetaExchange:
    if article.status in PUBLIC_DOWNLOADABLE_STATUSES:
        return article
    if _is_author(author_ids, user):
        return article
    raise NotAuthorizedError(code="CONTENT_NOT_AVAILABLE")


# ═══════════════════════════════════════════════════════════════════════════════
# Write permissions — maintainer-gated, status-gated
# ═══════════════════════════════════════════════════════════════════════════════


def assert_can_edit_article(article: ArticleMetaExchange, maintainer_ids: list[str], user: UserExchange) -> ArticleMetaExchange:
    _assert_maintainer(article, maintainer_ids, user, "edit")
    return article


def assert_can_delete_article(article: ArticleMetaExchange, maintainer_ids: list[str], user: UserExchange) -> ArticleMetaExchange:
    _assert_maintainer(article, maintainer_ids, user, "delete", allowed_statuses={ArticleStatus.DRAFT})
    _assert_all_maintainers_consented(article, maintainer_ids)
    return article


def assert_can_rollback_article(article: ArticleMetaExchange, maintainer_ids: list[str], user: UserExchange) -> ArticleMetaExchange:
    _assert_maintainer(article, maintainer_ids, user, "rollback")
    return article


def assert_can_publish_article(article: ArticleMetaExchange, maintainer_ids: list[str], user: UserExchange) -> ArticleMetaExchange:
    _assert_maintainer(article, maintainer_ids, user, "publish")
    _assert_all_maintainers_consented(article, maintainer_ids)
    return article


def assert_can_accept_merge(article: ArticleMetaExchange, maintainer_ids: list[str], user: UserExchange) -> ArticleMetaExchange:
    _assert_maintainer(article, maintainer_ids, user, "accept merge")
    _assert_all_maintainers_consented(article, maintainer_ids)
    return article


def assert_can_submit_review(article: ArticleMetaExchange) -> ArticleMetaExchange:
    if article.status in (ArticleStatus.SEDIMENTATION, ArticleStatus.PUBLISHED):
        return article
    raise NotAuthorizedError(code="CANNOT_REVIEW_DRAFT")


def assert_can_reply_to_review(article: ArticleMetaExchange, maintainer_ids: list[str], user: UserExchange, *,
                               fold_threshold: float = 1.0) -> ArticleMetaExchange:
    assert_not_folded(article, threshold=fold_threshold)
    if article.status not in (ArticleStatus.SEDIMENTATION, ArticleStatus.PUBLISHED):
        raise NotAuthorizedError(code="CANNOT_REPLY_DRAFT")
    if user.id not in maintainer_ids:
        raise NotAuthorizedError(code="NOT_ARTICLE_AUTHOR")
    return article


def assert_can_extend_sink(article: ArticleMetaExchange, maintainer_ids: list[str], user: UserExchange) -> ArticleMetaExchange:
    _assert_maintainer(article, maintainer_ids, user, "extend sink", allowed_statuses={ArticleStatus.SEDIMENTATION})
    return article


def assert_can_sync_article(article: ArticleMetaExchange, maintainer_ids: list[str], user: UserExchange) -> ArticleMetaExchange:
    _assert_maintainer(article, maintainer_ids, user, "sync", allowed_statuses=_SYNCABLE_STATUSES)
    return article


# ═══════════════════════════════════════════════════════════════════════════════
# Fork — status-gated + duplicate check
# ═══════════════════════════════════════════════════════════════════════════════


def assert_can_fork_article(
    article: ArticleMetaExchange,
    already_forked: bool = False,
    user: UserExchange | None = None,
    maintainer_ids: list[str] | None = None,
) -> ArticleMetaExchange:
    if article.status == ArticleStatus.DRAFT:
        if not maintainer_ids or user is None or not _is_maintainer(maintainer_ids, user):
            raise NotAuthorizedError(
                "Only maintainers can fork a draft article. "
                "Wait for it to be published, or ask a maintainer to fork it."
            )
    elif article.status not in FORKABLE_STATUSES:
        raise NotAuthorizedError(
            f"Articles with status '{article.status}' cannot be forked. "
            f"Only {', '.join(sorted(FORKABLE_STATUSES))} articles can be forked."
        )

    if already_forked:
        raise ConflictError(code="ALREADY_FORKED")

    return article


# ═══════════════════════════════════════════════════════════════════════════════
# Publish score gate
# ═══════════════════════════════════════════════════════════════════════════════


def assert_article_has_score(article) -> None:
    """Raise BadRequestError if the article's score is None."""
    if article.score is None:
        raise BadRequestError(code="ARTICLE_NO_SCORE")
