# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Compute→DB — compute score/reputation from DB cache, write results back."""

from __future__ import annotations

from peerpedia_core.storage.db import Session
from peerpedia_core.config.params import params
from peerpedia_core.storage.db.crud_article import (
    get_author_ids, update_article_score,
)
from peerpedia_core.storage.db.crud_review import get_reviews_for_article
from peerpedia_core.storage.db.crud_user import (
    get_user, get_users_by_ids, list_users, update_user_reputation,
)
from peerpedia_core.types.scores import ReputationScores
from peerpedia_core.compute.reputation import (
    blend_reputation, compute_reputation, get_reviewer_weight,
)
from peerpedia_core.compute.scoring import aggregate_review_scores
from peerpedia_core.core.guards import require_article
from peerpedia_core.storage.db.state import extract_reputation_state


def reconcile_score(db: Session, article_id: str) -> dict[str, float] | None:
    """Compute article score from cached reviews and write to DB."""
    # ── Setup ──────────────────────────────────────────────────────────────
    article = require_article(db, article_id)
    all_reviews = get_reviews_for_article(db, article_id)
    if not all_reviews:
        return None

    authors = get_author_ids(db, article_id)
    reviewer_users = get_users_by_ids(db, {r.reviewer_id for r in all_reviews})

    # ── Build weights ──────────────────────────────────────────────────────
    user_weight_map = _build_reviewer_weight_map(reviewer_users)

    # ── Build review inputs ────────────────────────────────────────────────
    review_dicts = []
    reviewer_weights: dict[str, float] = {}
    for r in all_reviews:
        if not r.scores or r.status != "submitted":
            continue
        review_dicts.append({
            "scores": r.scores,
            "is_self": r.reviewer_id in authors,
            "reviewer_id": r.reviewer_id,
            "scope": r.scope,
        })
        reviewer_weights[r.reviewer_id] = user_weight_map.get(r.reviewer_id, 1.0)

    # ── Compute + write ────────────────────────────────────────────────────
    scope_weights = {
        "sedimentation": params.score.sedimentation_scope_weight,
        "published": params.score.published_scope_weight,
    }
    score = aggregate_review_scores(review_dicts, reviewer_weights, scope_weights)
    if score is not None:
        update_article_score(db, article.id, score)
    return score


def _build_reviewer_weight_map(reviewer_users) -> dict[str, float]:
    """Build a map of reviewer_id → reputation weight."""
    weight_map: dict[str, float] = {}
    for u in reviewer_users:
        weight_map[u.id] = get_reviewer_weight(u.reputation if u.reputation else None)
    return weight_map


def reconcile_reputation(db: Session, user_id: str, *, user=None) -> ReputationScores:
    """Compute and persist a blended reputation for *user_id*."""
    if user is None:
        user = get_user(db, user_id)
    if user is None:
        raise ValueError(f"User not found: {user_id}")

    state = extract_reputation_state(db, user_id)
    new_rep = compute_reputation(state, user_id)
    existing_rep = user.reputation if user.reputation else {}
    blended = blend_reputation(existing_rep, new_rep)
    update_user_reputation(db, user_id, blended.to_result())
    return blended


def reconcile_all_reputations(db: Session) -> int:
    """Recompute reputation for every user in the system."""
    users = list_users(db)
    for u in users:
        reconcile_reputation(db, u.id, user=u)
    return len(users)
