# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Score aggregation — weighted average of reviews."""

from sqlalchemy.orm import Session

from peerpedia_core.config.params import params
from peerpedia_core.storage.db.crud_article import get_article, get_author_ids
from peerpedia_core.storage.db.crud_review import get_reviews_for_article
from peerpedia_core.storage.db.models import User
from peerpedia_core.types.scores import ReputationScores

DIMS = ["originality", "rigor", "completeness", "pedagogy", "impact"]


def compute_article_score(
    reviews: list[dict],
    reviewer_weights: dict[str, float] | None = None,
) -> dict | None:
    """Compute weighted average score from a list of reviews.

    Each review is a dict with:
        - scores: {originality, rigor, completeness, pedagogy, impact}
        - is_self: bool (reviewer is article author)
        - reviewer_id: str (required when *reviewer_weights* is provided)

    Self-reviews are weighted by params.score.self_review_weight.
    Community reviews are weighted by params.score.community_weight.

    When *reviewer_weights* is given, each review's contribution is additionally
    multiplied by ``reviewer_weights.get(review.reviewer_id, 1.0)``, allowing
    reputation-weighted scoring.
    """
    if not reviews:
        return None

    self_reviews = [r for r in reviews if r.get("is_self")]
    community_reviews = [r for r in reviews if not r.get("is_self")]

    self_weight = params.score.self_review_weight
    community_weight = params.score.community_weight

    def _reviewer_mult(review: dict) -> float:
        if reviewer_weights is None:
            return 1.0
        return reviewer_weights.get(review.get("reviewer_id", ""), 1.0)

    result = {}
    for dim in DIMS:
        total = 0.0
        count = 0.0

        for r in self_reviews:
            w = self_weight * _reviewer_mult(r)
            total += r["scores"][dim] * w
            count += w

        for r in community_reviews:
            w = community_weight * _reviewer_mult(r)
            total += r["scores"][dim] * w
            count += w

        result[dim] = round(total / count, 2) if count > 0 else 0.0

    return result


def compute_article_score_for_commit(
    session: Session,
    article_id: str,
    commit_hash: str | None = None,
) -> dict | None:
    """Compute the score for an article by aggregating all reviews.

    Aggregates reviews across all commits; editing a sedimentation article
    no longer erases existing review scores. The optional *commit_hash*
    parameter is kept for backward compatibility but no longer filters.

    Returns ``None`` if no reviews exist for the article.
    """
    article = get_article(session, article_id)
    if article is None:
        return None

    all_reviews = get_reviews_for_article(session, article_id)
    if not all_reviews:
        return None

    authors = get_author_ids(session, article_id)
    review_dicts: list[dict] = []
    reviewer_weights: dict[str, float] = {}

    # Batch-load all reviewer users in one query
    reviewer_ids = {r.reviewer_id for r in all_reviews}
    reviewer_users = session.query(User).filter(User.id.in_(reviewer_ids)).all()
    user_weight_map: dict[str, float] = {}
    for u in reviewer_users:
        if u.reputation:
            rep = ReputationScores(
                professionalism=u.reputation.get("professionalism", 0.0),
                objectivity=u.reputation.get("objectivity", 0.0),
                collaboration=u.reputation.get("collaboration", 0.0),
                pedagogy=u.reputation.get("pedagogy", 0.0),
            )
            w = 1.0 + params.reputation.author_weight_in_review * (rep.average() - 3.0) / 2.0
            user_weight_map[u.id] = max(0.0, w)
        else:
            user_weight_map[u.id] = 1.0

    for r in all_reviews:
        review_dicts.append(
            {
                "scores": r.scores,
                "is_self": r.reviewer_id in authors,
                "reviewer_id": r.reviewer_id,
            }
        )
        reviewer_weights[r.reviewer_id] = user_weight_map.get(r.reviewer_id, 1.0)

    return compute_article_score(review_dicts, reviewer_weights)
