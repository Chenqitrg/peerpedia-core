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

Moderation model (reputation-weighted, no roles):
  - High-reputation reviewers naturally have more influence via
    get_reviewer_weight() — no special admin override.
  - Articles with score < fold_score_threshold are frozen (no reviews,
    edits, forks, or publishing).  See also assert_not_folded() below.
  - Discovery path: share/forward to high-reputation users (TODO).
    No separate report table — forwarding is the signal.

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
from peerpedia_core.types.scores import SCORE_DIMENSIONS, FiveDimScores

# ═══════════════════════════════════════════════════════════════════════════════
# Visibility rules
# ═══════════════════════════════════════════════════════════════════════════════

PUBLIC_READABLE_STATUSES = {"sedimentation", "published", "rejected"}
FORKABLE_STATUSES = {"published", "rejected"}
PUBLIC_DOWNLOADABLE_STATUSES = {"published", "rejected"}

# Sedimentation articles are editable by maintainers (with Closes: requirement).
# Rejected is terminal (not writable).
_WRITABLE_STATUSES = {"draft", "sedimentation", "published"}

# Sync is allowed on rejected articles so the rejection propagates via P2P.
_SYNCABLE_STATUSES = {"draft", "sedimentation", "published", "rejected"}


def visible_statuses_for_user(current_user: Optional[User]) -> set[str]:
    """Return the set of statuses visible to *current_user*.

    Anonymous users see ``sedimentation`` + ``published``.
    Authenticated users additionally see their own ``draft`` articles
    (the caller must still filter by author for drafts).
    """
    if current_user is not None:
        return {"draft", "sedimentation", "published", "rejected"}
    return {"sedimentation", "published", "rejected"}


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


# ── Fold (moderation) ────────────────────────────────────────────────────────


def assert_not_folded(article, *, threshold: float = 1.0) -> None:
    """Raise ``NotAuthorizedError`` if the article's average score < *threshold*.

    A folded article is frozen — no reviews, edits, forks, or other
    interactions are allowed.  The caller provides the threshold from
    configuration so this module stays free of config imports.
    """
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
    """Raise if *user* is not a maintainer, or article status forbids editing.

    Maintainers can edit articles in ``draft``, ``sedimentation``, or
    ``published`` status.  Sedimentation edits require a ``Closes:``
    trailer in the commit message (enforced by the caller).
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


def _assert_all_maintainers_consented(article: Article, maintainer_ids: list[str]) -> None:
    """Raise if not all maintainers have consented to publish/merge.

    Single-maintainer articles are exempt — sole maintainer's action IS consent.
    """
    if len(maintainer_ids) <= 1:
        return
    consents = set(article.publish_consents or [])
    missing = [m for m in maintainer_ids if m not in consents]
    if missing:
        raise NotAuthorizedError(
            f"Unanimous consent required — {len(missing)} maintainer(s) "
            f"have not yet consented. Use 'peerpedia maintainer consent'."
        )


def assert_can_publish_article(article: Article, maintainer_ids: list[str], user: User) -> Article:
    """Raise if *user* is not a maintainer, or unanimous consent is missing.

    Publishing transitions a draft article into the sedimentation pool
    for peer review.  Once in sedimentation, an article publishes
    automatically when the sink timer expires — manual re-publish is
    not allowed.
    """
    _assert_maintainer(article, maintainer_ids, user, "publish")
    _assert_all_maintainers_consented(article, maintainer_ids)
    return article


def assert_can_accept_merge(article: Article, maintainer_ids: list[str], user: User) -> Article:
    """Raise if *user* is not a maintainer, or unanimous consent is missing.

    Merge proposals can be accepted on draft or published articles.
    Sedimentation articles are immutable during peer review.
    """
    _assert_maintainer(article, maintainer_ids, user, "accept merge")
    _assert_all_maintainers_consented(article, maintainer_ids)
    return article


def assert_can_submit_review(article: Article) -> Article:
    """Raise if reviews are not accepted for *article*.

    Sedimentation and published articles accept community reviews,
    including from authors.
    """
    if article.status in ("sedimentation", "published"):
        return article
    raise NotAuthorizedError("Cannot review a draft article")


def assert_can_reply_to_review(article: Article, maintainer_ids: list[str], user: User, *,
                               fold_threshold: float = 1.0) -> Article:
    """Raise if *user* (an author) cannot reply to reviews on *article*.

    Authors can reply to reviews during sedimentation and after publication.
    Only maintainers (authors) of the article can reply.

    *fold_threshold* is the minimum average score for a non-folded article.
    The caller should pass ``params.reputation.fold_score_threshold``.
    """
    assert_not_folded(article, threshold=fold_threshold)
    if article.status not in ("sedimentation", "published"):
        raise NotAuthorizedError("Cannot reply to reviews on a draft article")
    if user.id not in maintainer_ids:
        raise NotAuthorizedError("Only article authors can reply to reviews")
    return article


def assert_can_extend_sink(article: Article, maintainer_ids: list[str], user: User) -> Article:
    """Raise if *user* is not a maintainer, or article is not in sedimentation.

    Only sedimentation articles can have their sink timer extended.
    The caller must also enforce the maximum total sink duration
    (``params.sink.max_days``).
    """
    _assert_maintainer(article, maintainer_ids, user, "extend sink", allowed_statuses={"sedimentation"})
    return article


def assert_can_sync_article(article: Article, maintainer_ids: list[str], user: User) -> Article:
    """Raise if *user* is not a maintainer, or article status forbids sync.

    Sync is allowed on draft, sedimentation, published, and rejected.
    """
    _assert_maintainer(article, maintainer_ids, user, "sync", allowed_statuses=_SYNCABLE_STATUSES)
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

# Abbreviated keys (CLI input) and full-name keys (internal representation).
# Derived from SCORE_DIMENSIONS (types/scores.py) — single source of truth.
_FULL_DIMS = set(SCORE_DIMENSIONS.values())
_ABBR_DIMS = set(SCORE_DIMENSIONS.keys())
_DIMS_LIST = ", ".join(sorted(SCORE_DIMENSIONS.keys()))

def validate_self_review_scores(self_review: dict) -> None:
    """Validate self-review scores BEFORE any mutations.

    Must be called before ``write_review_to_git`` so a bad request fails
    with zero side effects.
    """
    if not isinstance(self_review, dict):
        raise BadRequestError("self_review must be a dict")
    keys = set(self_review.keys())
    if not (_ABBR_DIMS.issubset(keys) or _FULL_DIMS.issubset(keys)):
        raise BadRequestError(
            f"self_review must contain all {len(SCORE_DIMENSIONS)} dimensions: "
            f"{_DIMS_LIST}"
        )
    for dim, val in self_review.items():
        if not isinstance(val, (int, float)) or val < 1 or val > 5:
            raise BadRequestError(
                f"self_review dimension '{dim}' must be a number between 1 and 5, got {val!r}"
            )


def assert_article_has_score(article) -> None:
    """Assert the article has a score after score recomputation.

    Must be called AFTER ``recompute_article_score``.
    """
    if article.score is None:
        raise BadRequestError("Article must have a score before publishing")
