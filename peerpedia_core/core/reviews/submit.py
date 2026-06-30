# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Review submission — validate, write to git, persist to DB, recompute scores."""

from __future__ import annotations

from peerpedia_core.storage.db import Session
from peerpedia_core.config.params import params
from peerpedia_core.rules.articles import assert_can_submit_review, assert_not_folded
from peerpedia_core.rules.reviews import assert_valid_review
from peerpedia_core.storage.db.guards import require_article, require_user
from peerpedia_core.storage.db.crud_article import list_author_ids
from peerpedia_core.storage.db.crud_review import (
    get_accepted_invitation, update_review_status, upsert_review,
)
from peerpedia_core.core.reviews.thread import write_review_to_git, _resolve_review_identity
from peerpedia_core.core.notifications import create_notification
from peerpedia_core.core.reconcile import reconcile_reputation, reconcile_score


def submit_review(
    db: Session,
    article_id: str,
    reviewer_id: str,
    scores: dict,
    *,
    comment: str,
    signing_key_bytes: bytes | None = None,
    pubkey_hex: str | None = None,
) -> dict:
    """Submit or update a review for an article.

    Git-first: writes review files to git before DB mutation.
    Recomputes article score and author reputations.
    The commit_hash for the DB cache is taken from the new git commit.

    *comment* is required — reviews without substantive feedback are rejected.
    If *signing_key_bytes* and *pubkey_hex* are provided, the review commit
    is signed via SSH and the pubkey is embedded.

    Raises NotFoundError if the reviewer or article is not found.
    """
    # ── Authorization + Validation ──
    assert_valid_review(scores, comment)
    user = require_user(db, reviewer_id)
    article = require_article(db, article_id)
    assert_not_folded(article, threshold=params.reputation.fold_score_threshold)
    assert_can_submit_review(article)

    # ── Identity ──
    dir_id, display_name, email = _resolve_review_identity(
        article, user, reviewer_id, signing_key_bytes=signing_key_bytes,
    )

    # ── Write to git ──
    commit_hash = write_review_to_git(
        article_id, dir_id, scores, comment, display_name, email,
        signing_key_bytes=signing_key_bytes, pubkey_hex=pubkey_hex,
    )

    # ── Update DB ──
    r = _persist_review(db, article_id, reviewer_id, scores, commit_hash)

    # ── Recompute scores ──
    reconcile_score(db, article_id)
    for aid in list_author_ids(db, article_id):
        reconcile_reputation(db, aid)

    # ── Notify ──
    author_ids = list_author_ids(db, article_id)
    _notify_review_authors(db, article_id, reviewer_id, user.name, author_ids)

    return {"review_id": r.id, "scores": r.scores, "commit_hash": commit_hash}


def _persist_review(db, article_id, reviewer_id, scores, commit_hash):
    """Persist review to DB — routes through invitation update or direct upsert."""
    accepted_inv = get_accepted_invitation(db, article_id, reviewer_id)
    if accepted_inv is not None:
        update_review_status(db, accepted_inv, "submitted")
        accepted_inv.scores = scores
        accepted_inv.commit_hash = commit_hash
        db.flush()
        return accepted_inv
    return upsert_review(
        db, article_id=article_id, commit_hash=commit_hash,
        reviewer_id=reviewer_id, scores=scores,
    )


def _notify_review_authors(db, article_id, reviewer_id, reviewer_name, author_ids):
    """Notify article authors (except the reviewer) of a new review."""
    for aid in author_ids:
        if aid != reviewer_id:
            create_notification(
                db, user_id=aid, event="review_submitted",
                message=f"{reviewer_name} submitted a review on your article",
                article_id=article_id, actor_id=reviewer_id,
            )
