# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Reputation mechanism — core calculation logic.

Computes author reputation from article scores and uses reputation
to weight reviewer contributions.
"""

from sqlalchemy.orm import Session

from peerpedia_core.config.params import params
from peerpedia_core.storage.db.crud_article import get_articles_by_author
from peerpedia_core.storage.db.crud_user import update_user_reputation
from peerpedia_core.storage.db.models import User
from peerpedia_core.types.scores import ReputationScores

# Status-based weights for article scoring in reputation.
# Published articles carry the most weight.
_STATUS_WEIGHTS = {
    "published": 1.0,
    "sedimentation": 0.7,
    "draft": 0.3,
}

# Mapping from the 5 article-score dimensions to the 4 reputation dimensions.
# professionalism ← avg(originality, rigor)
# objectivity    ← completeness
# collaboration  ← avg(originality, impact)
# pedagogy       ← pedagogy (1:1)
_REP_DIMS: dict[str, list[str]] = {
    "professionalism": ["originality", "rigor"],
    "objectivity": ["completeness"],
    "collaboration": ["originality", "impact"],
    "pedagogy": ["pedagogy"],
}


def compute_author_reputation(session: Session, user_id: str) -> ReputationScores:
    """Compute and persist a blended reputation for *user_id*.

    1. Fetch every article where the user is listed as an author.
    2. Aggregate the article scores (5 dims) into reputation scores (4 dims)
       using the dimension mapping defined above.
    3. Weight each article's contribution by its status
       (published > sedimentation > draft).
    4. Blend the result with the user's existing reputation using
       ``article_to_author_weight`` so that reputation changes smoothly.
    5. Persist via ``update_user_reputation()``.
    6. Return the new ``ReputationScores``.
    """
    articles = get_articles_by_author(session, user_id)

    # --- Compute reputation from article scores --------------------------------
    if not articles:
        rep = ReputationScores()
        update_user_reputation(session, user_id, rep.to_dict())
        return rep

    dim_totals: dict[str, float] = {
        "professionalism": 0.0,
        "objectivity": 0.0,
        "collaboration": 0.0,
        "pedagogy": 0.0,
    }
    total_weight = 0.0

    for article in articles:
        if not article.score:
            continue
        status_w = _STATUS_WEIGHTS.get(article.status, 0.3)

        for rep_dim, article_dims in _REP_DIMS.items():
            values = [article.score.get(d, 0.0) for d in article_dims]
            dim_totals[rep_dim] += (sum(values) / len(values)) * status_w

        total_weight += status_w

    if total_weight == 0:
        rep = ReputationScores()
    else:
        rep = ReputationScores(
            professionalism=round(dim_totals["professionalism"] / total_weight, 2),
            objectivity=round(dim_totals["objectivity"] / total_weight, 2),
            collaboration=round(dim_totals["collaboration"] / total_weight, 2),
            pedagogy=round(dim_totals["pedagogy"] / total_weight, 2),
        )

    # --- Blend with existing reputation -----------------------------------------
    user = session.get(User, user_id)
    existing_rep: dict = user.reputation if (user and user.reputation) else {}

    weight = params.reputation.article_to_author_weight  # 0.3
    blended = ReputationScores(
        professionalism=round(
            (1 - weight) * existing_rep.get("professionalism", 0.0) + weight * rep.professionalism,
            2,
        ),
        objectivity=round(
            (1 - weight) * existing_rep.get("objectivity", 0.0) + weight * rep.objectivity,
            2,
        ),
        collaboration=round(
            (1 - weight) * existing_rep.get("collaboration", 0.0) + weight * rep.collaboration,
            2,
        ),
        pedagogy=round(
            (1 - weight) * existing_rep.get("pedagogy", 0.0) + weight * rep.pedagogy,
            2,
        ),
    )

    update_user_reputation(session, user_id, blended.to_dict())
    return blended


def get_reviewer_weight(session: Session, reviewer_id: str) -> float:
    """Return a weight factor for a reviewer based on their reputation.

    Formula:
        weight = 1.0 + author_weight_in_review * (avg_rep - 3.0) / 2.0

    - 1.0  = neutral (no influence).
    - >1.0 = trusted reviewer (their reviews count more).
    - <1.0 = low-reputation reviewer (their reviews count less).

    Defaults to 1.0 when the user has no reputation data.
    """
    user = session.get(User, reviewer_id)
    if user is None or not user.reputation:
        return 1.0

    rep = ReputationScores(
        professionalism=user.reputation.get("professionalism", 0.0),
        objectivity=user.reputation.get("objectivity", 0.0),
        collaboration=user.reputation.get("collaboration", 0.0),
        pedagogy=user.reputation.get("pedagogy", 0.0),
    )

    avg_rep = rep.average()
    weight = 1.0 + params.reputation.author_weight_in_review * (avg_rep - 3.0) / 2.0
    return max(0.0, weight)


def recalculate_all_reputations(session: Session) -> int:
    """Recalculate reputation for every user in the system.

    Returns the number of users whose reputation was (re)computed.
    """
    users = session.query(User).all()
    for user in users:
        compute_author_reputation(session, user.id)
    return len(users)
