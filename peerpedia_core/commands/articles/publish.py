# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Publish an article — transition from draft to sedimentation."""

from __future__ import annotations

from peerpedia_core.storage.db import Session
from peerpedia_core.config.params import PLATFORM_EMAIL, make_peerpedia_email, params
from peerpedia_core.exceptions import BadRequestError, NotAuthorizedError
from peerpedia_core.policies.articles import (
    assert_article_has_score,
    assert_can_publish_article,
    assert_not_folded,
    validate_self_review_scores,
)
from peerpedia_core.storage.db.crud_article import (
    count_articles,
    set_sink_start,
    update_article_status,
)
from peerpedia_core.storage.db.crud_maintainer import get_maintainer_ids
from peerpedia_core.storage.db.crud_review import get_review, get_reviews_for_article, upsert_review
from peerpedia_core.storage.db.crud_user import get_followers
from peerpedia_core.storage.git_backend import (
    DEFAULT_ARTICLES_DIR,
    commit_article,
    get_head_hash,
    is_repo_dirty,
)
from peerpedia_core.commands.integrity import assert_article_integrity
from peerpedia_core.commands.reviews import write_review_to_git
from peerpedia_core.commands.notifications import create_notifications_batch
from peerpedia_core.commands.workflow import recompute_article_score
from peerpedia_core.commands.articles._helpers import require_article, require_user


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
    user = require_user(db, user_id)
    a = require_article(db, article_id)
    mids = get_maintainer_ids(db, article_id)
    assert_not_folded(a, threshold=params.reputation.fold_score_threshold)
    assert_can_publish_article(a, mids, user)

    assert_article_integrity(db, article_id, level="full")

    old_status = a.status
    if old_status != "draft":
        raise NotAuthorizedError("Only draft articles can be published")

    # TODO(lean-ci): if the article contains ```lean fenced code blocks,
    # run ``lean --run`` on each block before publishing.  All LEAN blocks
    # must compile successfully — broken proofs block publication, same as
    # missing self-review.  The LEAN verification result is written into
    # the commit message as a ``LEAN-verified: <hash>`` trailer, signed
    # alongside the article content.  Peers can trust the verification
    # without re-running (they can re-verify independently).  This is the
    # git-native equivalent of CI: the proof compiles → it ships.

    # Validate self-review BEFORE any mutations — failure here has zero side effects.
    validate_self_review_scores(self_review)

    # Anti-spam: limit concurrent articles in sedimentation per author.
    in_pool = count_articles(db, status="sedimentation", author_id=user_id)
    if in_pool >= params.sink.max_sedimentation_per_author:
        raise BadRequestError(
            f"Author already has {in_pool} article(s) in sedimentation "
            f"(max {params.sink.max_sedimentation_per_author})"
        )

    write_review_to_git(
        article_id, user_id, self_review, comment, user.name, make_peerpedia_email(user_id),
        signing_key_bytes=signing_key_bytes, pubkey_hex=pubkey_hex,
    )

    rp = DEFAULT_ARTICLES_DIR / article_id
    if is_repo_dirty(rp):
        commit_hash = commit_article(
            rp, "[status] sedimentation", "PeerPedia", PLATFORM_EMAIL,
            signing_key=None, pubkey_hex=None,
        )
    else:
        commit_hash = get_head_hash(rp)

    update_article_status(db, article_id, "sedimentation")

    upsert_review(
        db, article_id=article_id, commit_hash=commit_hash,
        reviewer_id=user_id, scores=self_review,
    )

    sink_days = (
        params.sink.new_article_default_days if old_status == "draft"
        else params.sink.edit_article_default_days
    )
    set_sink_start(db, article_id, sink_days)

    recompute_article_score(db, article_id)

    # Post-mutation guard: verify the score was computed successfully.
    assert_article_has_score(a)

    # Collect all notifications and flush in one batch.
    batch: list[dict] = []
    followers = get_followers(db, user_id)
    for follower in followers:
        batch.append({
            "user_id": follower.id, "event": "article_published",
            "message": f"{user.name} published \"{a.title}\"",
            "article_id": article_id, "actor_id": user_id,
        })

    reviews = get_reviews_for_article(db, article_id)
    notified = set()
    for r in reviews:
        rid = r.reviewer_id
        if rid != user_id and rid not in notified:
            notified.add(rid)
            batch.append({
                "user_id": rid, "event": "article_published",
                "message": f"\"{a.title}\" was published — your review contributed",
                "article_id": article_id, "actor_id": user_id,
            })

    if batch:
        create_notifications_batch(db, batch)

    return {"id": a.id, "title": a.title, "status": a.status, "commit_hash": commit_hash}
