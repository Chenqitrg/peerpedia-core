# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

r"""Pure article authorization rules — zero IO, zero DB/git dependencies.

Every function takes pre-fetched data (ArticleMetaStorage, UserStorage, maintainer_ids, ...)
and either returns the article or raises a semantic exception.

Importable from anywhere — ``storage/db/``, ``core/``, ``cli/`` — without
circular-dependency risk.
"""

from __future__ import annotations

from typing import Optional

from peerpedia_core.exceptions import BadRequestError, ConflictError, NotAuthorizedError
from peerpedia_core.storage.db.models import ArticleMetaStorage, UserStorage
from peerpedia_core.types.scores import FiveDimScores

# ═══════════════════════════════════════════════════════════════════════════════
# Status constants
# ═══════════════════════════════════════════════════════════════════════════════

PUBLIC_READABLE_STATUSES = {"sedimentation", "published", "rejected"}
FORKABLE_STATUSES = {"draft", "published", "rejected"}
PUBLIC_DOWNLOADABLE_STATUSES = {"published", "rejected"}

_WRITABLE_STATUSES = {"draft", "sedimentation", "published"}
_SYNCABLE_STATUSES = {"draft", "sedimentation", "published", "rejected"}


def visible_statuses_for_user(current_user: UserStorage | None) -> set[str]:
    """Return the set of statuses visible to *current_user*."""
    if current_user is not None:
        return {"draft", "sedimentation", "published", "rejected"}
    return {"sedimentation", "published", "rejected"}


# ═══════════════════════════════════════════════════════════════════════════════
# Pure helpers
# ═══════════════════════════════════════════════════════════════════════════════


def _is_author(author_ids: list[str], user: UserStorage | None) -> bool:
    if user is None:
        return False
    return user.id in author_ids


def _is_maintainer(maintainer_ids: list[str], user: UserStorage) -> bool:
    return user.id in maintainer_ids


def _assert_maintainer(
    article: ArticleMetaStorage,
    maintainer_ids: list[str],
    user: UserStorage,
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


def _assert_all_maintainers_consented(article: ArticleMetaStorage, maintainer_ids: list[str]) -> None:
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
    article: ArticleMetaStorage,
    author_ids: list[str],
    user: UserStorage | None,
) -> ArticleMetaStorage:
    if article.status in PUBLIC_READABLE_STATUSES:
        return article
    if _is_author(author_ids, user):
        return article
    raise NotAuthorizedError("Article is private")


def assert_can_access_content(
    article: ArticleMetaStorage,
    author_ids: list[str],
    user: UserStorage | None,
) -> ArticleMetaStorage:
    if article.status in PUBLIC_DOWNLOADABLE_STATUSES:
        return article
    if _is_author(author_ids, user):
        return article
    raise NotAuthorizedError("Content download not available for this article")


# ═══════════════════════════════════════════════════════════════════════════════
# Write permissions — maintainer-gated, status-gated
# ═══════════════════════════════════════════════════════════════════════════════


def assert_can_edit_article(article: ArticleMetaStorage, maintainer_ids: list[str], user: UserStorage) -> ArticleMetaStorage:
    _assert_maintainer(article, maintainer_ids, user, "edit")
    return article


def assert_can_delete_article(article: ArticleMetaStorage, maintainer_ids: list[str], user: UserStorage) -> ArticleMetaStorage:
    _assert_maintainer(article, maintainer_ids, user, "delete", allowed_statuses={"draft"})
    _assert_all_maintainers_consented(article, maintainer_ids)
    return article


def assert_can_rollback_article(article: ArticleMetaStorage, maintainer_ids: list[str], user: UserStorage) -> ArticleMetaStorage:
    _assert_maintainer(article, maintainer_ids, user, "rollback")
    return article


def assert_can_publish_article(article: ArticleMetaStorage, maintainer_ids: list[str], user: UserStorage) -> ArticleMetaStorage:
    _assert_maintainer(article, maintainer_ids, user, "publish")
    _assert_all_maintainers_consented(article, maintainer_ids)
    return article


def assert_can_accept_merge(article: ArticleMetaStorage, maintainer_ids: list[str], user: UserStorage) -> ArticleMetaStorage:
    _assert_maintainer(article, maintainer_ids, user, "accept merge")
    _assert_all_maintainers_consented(article, maintainer_ids)
    return article


def assert_can_submit_review(article: Article) -> ArticleMetaStorage:
    if article.status in ("sedimentation", "published"):
        return article
    raise NotAuthorizedError("Cannot review a draft article")


def assert_can_reply_to_review(article: ArticleMetaStorage, maintainer_ids: list[str], user: UserStorage, *,
                               fold_threshold: float = 1.0) -> ArticleMetaStorage:
    assert_not_folded(article, threshold=fold_threshold)
    if article.status not in ("sedimentation", "published"):
        raise NotAuthorizedError("Cannot reply to reviews on a draft article")
    if user.id not in maintainer_ids:
        raise NotAuthorizedError("Only article authors can reply to reviews")
    return article


def assert_can_extend_sink(article: ArticleMetaStorage, maintainer_ids: list[str], user: UserStorage) -> ArticleMetaStorage:
    _assert_maintainer(article, maintainer_ids, user, "extend sink", allowed_statuses={"sedimentation"})
    return article


def assert_can_sync_article(article: ArticleMetaStorage, maintainer_ids: list[str], user: UserStorage) -> ArticleMetaStorage:
    _assert_maintainer(article, maintainer_ids, user, "sync", allowed_statuses=_SYNCABLE_STATUSES)
    return article


# ═══════════════════════════════════════════════════════════════════════════════
# Fork — status-gated + duplicate check
# ═══════════════════════════════════════════════════════════════════════════════


def assert_can_fork_article(
    article: ArticleMetaStorage,
    existing_fork: ArticleMetaStorage | None,
    user: UserStorage | None = None,
    maintainer_ids: list[str] | None = None,
) -> ArticleMetaStorage:
    if article.status == "draft":
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

    if existing_fork is not None:
        raise ConflictError("Already forked this article")

    return article


# ═══════════════════════════════════════════════════════════════════════════════
# Publish score gate
# ═══════════════════════════════════════════════════════════════════════════════


def assert_article_has_score(article) -> None:
    """Raise BadRequestError if the article's score is None."""
    if article.score is None:
        raise BadRequestError("Article must have a score before publishing")
