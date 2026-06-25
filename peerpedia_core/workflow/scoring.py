# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

r"""Score aggregation — pure computation, zero storage dependencies.

Single public function: ``aggregate_review_scores``.

Weight chain (multiplied together for each review):
    base weight = self_weight (0.15) or community_weight (0.85)
    × reviewer_weights[reviewer_id]          (reputation-based, optional)
    × scope_weights[scope]                   (sedimentation=1.0, published=0.5)

This means a sedimentation review from a high-reputation reviewer counts
much more than a published review from an unknown reviewer.

Reviewer's checklist
--------------------
- Is this file free of ``from peerpedia_core.storage`` and ``Session`` imports?
- Are scope_weights looked up with ``.get(scope, 1.0)`` to handle missing keys?
"""

from peerpedia_core.config.params import params
from peerpedia_core.types.scores import SCORE_DIMENSIONS

DIMS = list(SCORE_DIMENSIONS.values())  # derived, not hardcoded


def aggregate_review_scores(
    reviews: list[dict],
    reviewer_weights: dict[str, float] | None = None,
    scope_weights: dict[str, float] | None = None,
) -> dict | None:
    """Compute weighted average score from a list of reviews.

    Each review is a dict with:
        - scores: dict with keys from SCORE_DIMENSIONS.values()
        - is_self: bool (reviewer is article author)
        - reviewer_id: str (required when *reviewer_weights* is provided)
        - scope: str (optional, weighted by *scope_weights* if provided)

    Self-reviews are weighted by params.score.self_review_weight.
    Community reviews are weighted by params.score.community_weight.

    When *reviewer_weights* is given, each review's contribution is additionally
    multiplied by ``reviewer_weights.get(review.reviewer_id, 1.0)``.

    When *scope_weights* is given, each review's contribution is additionally
    multiplied by ``scope_weights.get(review.scope, 1.0)``.

    Raises ValueError if any review has empty or invalid scores.
    """
    if not reviews:
        return None

    # Guard: every review in the input list MUST have valid non-empty scores.
    # Fail FAST and LOUD — silently skipping malformed input hides bugs.
    for r in reviews:
        if not r.get("scores") or not isinstance(r["scores"], dict):
            raise ValueError(
                "aggregate_review_scores received review with empty or invalid scores"
            )

    self_reviews = [r for r in reviews if r.get("is_self")]
    community_reviews = [r for r in reviews if not r.get("is_self")]

    self_weight = params.score.self_review_weight
    community_weight = params.score.community_weight

    def _reviewer_mult(review: dict) -> float:
        w = 1.0
        if reviewer_weights is not None:
            w *= reviewer_weights.get(review.get("reviewer_id", ""), 1.0)
        if scope_weights is not None:
            w *= scope_weights.get(review.get("scope", ""), 1.0)
        return w

    # Pre-compute per-review weights once (constant across dimensions).
    self_weights = {id(r): self_weight * _reviewer_mult(r) for r in self_reviews}
    comm_weights = {id(r): community_weight * _reviewer_mult(r) for r in community_reviews}

    result = {}
    for dim in DIMS:
        total = 0.0
        count = 0.0

        for r in self_reviews:
            w = self_weights[id(r)]
            total += r["scores"][dim] * w
            count += w

        for r in community_reviews:
            w = comm_weights[id(r)]
            total += r["scores"][dim] * w
            count += w

        result[dim] = round(total / count, 2) if count > 0 else 0.0

    return result
