# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

r"""Review orchestration — submit, invite, reply, rate.

Call graph::

    submit_review (submit.py)
      ├► policies.assert_can_submit_review
      ├► write_review_to_git (thread.py)          (git-first: scores.json + threads/*.md)
      ├► _persist_review                           (routes to invitation update or upsert)
      ├► reconcile_score / reconcile_reputation
      └► _notify_review_authors

    submit_reply (thread.py)
      ├► _resolve_review_identity → _derive_anonymous_id
      └► _write_thread_message → commit_article

Key design — anonymity during sedimentation
--------------------------------------------
When the article is in sedimentation, the git directory uses an anonymous
hash (``_derive_anonymous_id``) so reviewer identities are not exposed in
the git filesystem.  The DB stores the real ``reviewer_id`` from the caller.

    sedimentation review:   git dir = anon_hash    DB reviewer_id = real UUID
    published review:       git dir = real UUID     DB reviewer_id = real UUID
"""

from __future__ import annotations

from peerpedia_core.storage.db import Session
from peerpedia_core.core.reviews.submit import submit_review
from peerpedia_core.core.reviews.invite import (
    accept_invitation, decline_invitation, invite_reviewer,
)
from peerpedia_core.core.reviews.thread import submit_reply, write_review_to_git

from peerpedia_core.storage.db.crud_review import get_reviews_for_article as _get
from peerpedia_core.core.guards import (
    require_article, require_helpfulness_score_range,
    require_maintainer, require_review,
)


def get_reviews_for_article(db: Session, article_id: str) -> list[ReviewMetaStorage]:
    """Return all cached reviews for an article, newest first."""
    return _get(db, article_id)


def rate_review_helpfulness(
    db: Session,
    article_id: str,
    reviewer_id: str,
    rater_id: str,
    score: int,
) -> dict:
    """Rate a review's helpfulness (1-5).  Only article maintainers can rate.

    Updates the ReviewMetaStorage record in DB and writes to git.

    Raises NotFoundError if the article or review is not found.
    Raises NotAuthorizedError if the rater is not a maintainer.
    Raises BadRequestError if the score is outside 1-5 range.
    """
    article = require_article(db, article_id)
    require_maintainer(db, article_id, rater_id)
    require_helpfulness_score_range(score)

    target = require_review(db, article_id, reviewer_id)
    target.helpfulness_score = score
    db.flush()

    return {"review_id": target.id, "helpfulness_score": score}
