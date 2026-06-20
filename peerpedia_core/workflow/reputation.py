# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

r"""Reputation mechanism — pure computation, zero storage dependencies.

Three public functions used by ``commands/workflow.py``:

    compute_reputation(articles) → ReputationScores
        Aggregate article scores (5 dims) into reputation (4 dims), weighted
        by article status (published=1.0, sedimentation=0.7, draft=0.3).
        Returns all zeros if no articles have scores.

    blend_reputation(existing, new, weight) → ReputationScores
        EMA smooth new reputation into existing reputation.  Weight defaults
        to params.reputation.article_to_author_weight (0.3).

    get_reviewer_weight(reputation) → float
        Map reputation average to a review weight multiplier.  Neutral point
        is 3.0 → weight=1.0.  Returns 1.0 for None/empty reputation.

Dimension mapping (5→4)
-----------------------
    professionalism ← avg(originality, rigor)
    objectivity    ← completeness
    collaboration  ← avg(originality, impact)
    pedagogy       ← pedagogy (1:1)

Reviewer's checklist
--------------------
- Is this file free of storage/ and Session imports?
- Are status weights hardcoded or from params?  (currently hardcoded — by design,
  they define the reputation model, not tuning knobs)
"""

from peerpedia_core.config.params import params
from peerpedia_core.types.scores import ReputationScores

# Status-based weights for article scoring in reputation.
# Published articles carry the most weight.
_STATUS_WEIGHTS = {
    "published": 1.0,
    "sedimentation": 0.7,
    "draft": 0.3,
}

# Mapping from the 5 article-score dimensions to the 4 reputation dimensions.
_REP_DIMS: dict[str, list[str]] = {
    "professionalism": ["originality", "rigor"],
    "objectivity": ["completeness"],
    "collaboration": ["originality", "impact"],
    "pedagogy": ["pedagogy"],
}


def compute_reputation(articles: list[dict]) -> ReputationScores:
    """Compute raw reputation from a list of article dicts.

    Each article dict must have:
        - score: dict or None (FiveDimScores)
        - status: str

    Returns ReputationScores with all zeros if no articles have scores.
    """
    dim_totals: dict[str, float] = {
        "professionalism": 0.0,
        "objectivity": 0.0,
        "collaboration": 0.0,
        "pedagogy": 0.0,
    }
    total_weight = 0.0

    for article in articles:
        score = article.get("score")
        if not score:
            continue
        status_w = _STATUS_WEIGHTS.get(article.get("status", ""), 0.3)

        for rep_dim, article_dims in _REP_DIMS.items():
            values = [score.get(d, 0.0) for d in article_dims]
            dim_totals[rep_dim] += (sum(values) / len(values)) * status_w

        total_weight += status_w

    if total_weight == 0:
        return ReputationScores()

    return ReputationScores(
        professionalism=round(dim_totals["professionalism"] / total_weight, 2),
        objectivity=round(dim_totals["objectivity"] / total_weight, 2),
        collaboration=round(dim_totals["collaboration"] / total_weight, 2),
        pedagogy=round(dim_totals["pedagogy"] / total_weight, 2),
    )


def blend_reputation(
    existing: dict,
    new: ReputationScores,
    weight: float | None = None,
) -> ReputationScores:
    """Blend new reputation scores with existing ones using EMA smoothing.

    *existing* is the current reputation dict (may be empty).
    *weight* defaults to params.reputation.article_to_author_weight.
    """
    if weight is None:
        weight = params.reputation.article_to_author_weight

    return ReputationScores(
        professionalism=round(
            (1 - weight) * existing.get("professionalism", 0.0) + weight * new.professionalism, 2,
        ),
        objectivity=round(
            (1 - weight) * existing.get("objectivity", 0.0) + weight * new.objectivity, 2,
        ),
        collaboration=round(
            (1 - weight) * existing.get("collaboration", 0.0) + weight * new.collaboration, 2,
        ),
        pedagogy=round(
            (1 - weight) * existing.get("pedagogy", 0.0) + weight * new.pedagogy, 2,
        ),
    )


def get_reviewer_weight(reputation: dict | None) -> float:
    """Return a weight factor for a reviewer based on their reputation.

    Defaults to 1.0 when reputation is None or empty.
    """
    if not reputation:
        return 1.0

    rep = ReputationScores(
        professionalism=reputation.get("professionalism", 0.0),
        objectivity=reputation.get("objectivity", 0.0),
        collaboration=reputation.get("collaboration", 0.0),
        pedagogy=reputation.get("pedagogy", 0.0),
    )

    avg_rep = rep.average()
    weight = 1.0 + params.reputation.author_weight_in_review * (avg_rep - 3.0) / 2.0
    return max(0.0, weight)
