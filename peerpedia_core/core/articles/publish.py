# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Publish an article — transition from draft to sedimentation."""

from __future__ import annotations

from peerpedia_core.storage.db import Session
from peerpedia_core.config.params import make_peerpedia_email, params
from peerpedia_core.config.paths import article_repo_path
from peerpedia_core.rules.articles import (
    assert_article_has_score, assert_can_publish_article,
)
from peerpedia_core.rules.reviews import assert_valid_review
from peerpedia_core.storage.db.guards import (
    authorize_article_action, guard_sedimentation_limit, require_draft_status,
)
from peerpedia_core.core.reconcile import reconcile_integrity, reconcile_score
from peerpedia_core.storage.db.crud_article import (
    clear_publish_consents, set_sink_start, update_article_status,
)
from peerpedia_core.storage.db.crud_review import get_reviews_for_article, upsert_review
from peerpedia_core.storage.db.crud_user import get_followers
from peerpedia_core.storage.git import commit_status_marker
from peerpedia_core.core.reviews import write_review_to_git
from peerpedia_core.core.notifications import create_notifications_batch


def _build_publish_notifications(db: Session, article_id: str, a, user) -> list[dict]:
    """Build notification batch for article publication."""
    batch: list[dict] = []
    for follower in get_followers(db, user.id):
        batch.append({
            "user_id": follower.id, "event": "article_published",
            "message": f"{user.name} published \"{a.title}\"",
            "article_id": article_id, "actor_id": user.id,
        })
    notified = {user.id}
    for r in get_reviews_for_article(db, article_id):
        if r.reviewer_id not in notified:
            notified.add(r.reviewer_id)
            batch.append({
                "user_id": r.reviewer_id, "event": "article_published",
                "message": f"\"{a.title}\" was published — your review contributed",
                "article_id": article_id, "actor_id": user.id,
            })
    return batch


def publish_article(
    db: Session, article_id: str, user_id: str, self_review: dict, *,
    comment: str = "", signing_key_bytes: bytes, pubkey_hex: str,
) -> dict:
    """Publish an article to the sedimentation pool.

    Only callable from ``draft`` status.  Writes the self-review to git,
    caches scores in DB, starts the sink timer, and recomputes the article
    score.

    Raises NotFoundError if the user or article is not found.
    Raises NotAuthorizedError if the article is not in draft status.
    Raises BadRequestError if the author has too many articles in sedimentation.
    """
    # ── Authorization ──────────────────────────────────────────────────────
    user, a, mids = authorize_article_action(db, article_id, user_id)
    assert_can_publish_article(a, mids, user)
    reconcile_integrity(db, article_id, level="full")

    require_draft_status(a)

    # ── Validation ─────────────────────────────────────────────────────────
    assert_valid_review(self_review, check_comment=False)
    guard_sedimentation_limit(db, user_id)

    # ── Write review + status commit ───────────────────────────────────────
    write_review_to_git(
        article_id, user_id, self_review, comment, user.name, make_peerpedia_email(user_id),
        signing_key_bytes=signing_key_bytes, pubkey_hex=pubkey_hex,
    )
    commit_hash = commit_status_marker(article_repo_path(article_id), "sedimentation")

    # ── Update DB ──────────────────────────────────────────────────────────
    update_article_status(db, article_id, "sedimentation")
    upsert_review(
        db, article_id=article_id, commit_hash=commit_hash,
        reviewer_id=user_id, scores=self_review,
    )
    clear_publish_consents(db, article_id)
    set_sink_start(db, article_id, params.sink.new_article_default_days)
    reconcile_score(db, article_id)
    assert_article_has_score(a)

    # ── Notify ─────────────────────────────────────────────────────────────
    batch = _build_publish_notifications(db, article_id, a, user)
    if batch:
        create_notifications_batch(db, batch)

    return {"id": a.id, "title": a.title, "status": a.status, "commit_hash": commit_hash}
