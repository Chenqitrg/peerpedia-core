# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

r"""Review orchestration — submit reviews and write review files to git.

review-feedback: reviewers are notified when the article publishes
(see publish_article → get_reviews_for_article → create_notification).

author-rebuttal / author-reply: implemented — authors can reply to reviews
via submit_reply(), which posts to the review thread with a [reply] marker.

Call graph::

    submit_review
      ├► policies.assert_can_submit_review     (sedimentation or published)
      ├► write_review_to_git                  (git-first: scores.json + threads/*.md)
      │     ├► git_backend.commit_article      (returns commit_hash)
      │     └► storage.locks.get_article_lock  (serialize concurrent git writes)
      ├► crud_review.upsert_review             (DB cache, uses commit_hash from git)
      ├► commands.workflow.recompute_article_score
      └► commands.workflow.recompute_author_reputation  (for each author)

    _derive_anonymous_id
      └► sha256(article_id:reviewer_id)[:12]   (deterministic, stable per article)

    write_review_to_git
      ├► Write reviews/{directory_id}/scores.json  (overwrite latest)
      ├► Write reviews/{directory_id}/threads/{nnn}.md  (append new file)
      └► git_backend.commit_article

Key design — anonymity during sedimentation
--------------------------------------------
When the article is in sedimentation, the git directory uses an anonymous
hash (``_derive_anonymous_id``) so reviewer identities are not exposed in
the git filesystem.  The DB stores the real ``reviewer_id`` from the caller.
The anonymous directory name and the real DB ``reviewer_id`` are linked only
through the commit — when the article publishes, the mapping can be resolved.

    sedimentation review:   git dir = anon_hash    DB reviewer_id = real UUID
    published review:       git dir = real UUID     DB reviewer_id = real UUID

Reviewer's checklist
--------------------
- Is ``write_review_to_git`` called before ``upsert_review``?  (git-first)
- Is ``commit_hash`` taken from the return value of ``write_review_to_git``,
  not from an external parameter?  (previous bug)
- Are author reputations recomputed for every author after score changes?
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from peerpedia_core.storage.db import Session

from peerpedia_core.config.params import make_peerpedia_email, params
from peerpedia_core.exceptions import BadRequestError, ConflictError, NotFoundError, NotAuthorizedError
from peerpedia_core.policies.articles import (
    assert_can_reply_to_review, assert_can_submit_review, assert_not_folded,
)
from peerpedia_core.storage.db.crud_article import get_author_ids
from peerpedia_core.storage.db.crud_maintainer import get_maintainer_ids
from peerpedia_core.storage.db.models import Review
from peerpedia_core.storage.db.crud_review import (
    get_reviews_for_article as _get,
    get_accepted_invitation,
    get_pending_invitation,
    update_review_status,
    upsert_review,
)
from peerpedia_core.names import derive_anonymous_name
from peerpedia_core.crypto import temp_signing_key
from peerpedia_core.storage.git_backend import DEFAULT_ARTICLES_DIR, commit_article
from peerpedia_core.storage.locks import get_article_lock
from peerpedia_core.commands.workflow import recompute_article_score, recompute_author_reputation
from peerpedia_core.commands.articles._helpers import (
    require_article,
    require_article_repo,
    require_user,
)
from peerpedia_core.commands.notifications import create_notification
from peerpedia_core.types.scores import SCORE_DIMENSIONS


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
    assert_valid_review(scores, comment)

    user = require_user(db, reviewer_id)
    article = require_article(db, article_id)
    assert_not_folded(article, threshold=params.reputation.fold_score_threshold)
    assert_can_submit_review(article)

    author_ids = get_author_ids(db, article_id)

    if article.status == "sedimentation":
        # Sedimentation reviews REQUIRE an accepted invitation.
        accepted_inv = get_accepted_invitation(db, article_id, reviewer_id)
        if accepted_inv is None:
            raise NotAuthorizedError(
                "Must accept a review invitation before submitting a review "
                "during sedimentation"
            )
        anon_id = _derive_anonymous_id(article_id, signing_key=signing_key_bytes)
        display_name = derive_anonymous_name(anon_id)
        email = make_peerpedia_email(f"anon-{anon_id}")
        commit_hash = write_review_to_git(
            article_id, anon_id, scores, comment, display_name, email,
            signing_key_bytes=signing_key_bytes, pubkey_hex=pubkey_hex,
        )
        # Update the accepted row in-place — state transition, not cache upsert.
        update_review_status(db, accepted_inv, "submitted")
        accepted_inv.scores = scores
        accepted_inv.commit_hash = commit_hash
        db.flush()
        r = accepted_inv
    else:
        # Published articles: open reviews, no invitation needed.
        display_name = user.name
        email = make_peerpedia_email(reviewer_id)
        commit_hash = write_review_to_git(
            article_id, reviewer_id, scores, comment, display_name, email,
            signing_key_bytes=signing_key_bytes, pubkey_hex=pubkey_hex,
        )
        r = upsert_review(
            db, article_id=article_id, commit_hash=commit_hash,
            reviewer_id=reviewer_id, scores=scores,
        )

    recompute_article_score(db, article_id)

    for aid in author_ids:
        recompute_author_reputation(db, aid)

    # Notify article authors about the new review (exclude self-review).
    for aid in author_ids:
        if aid != reviewer_id:
            create_notification(
                db, user_id=aid, event="review_submitted",
                message=f"{user.name} submitted a review on your article",
                article_id=article_id, actor_id=reviewer_id,
            )

    return {"review_id": r.id, "scores": r.scores, "commit_hash": commit_hash}


def invite_reviewer(
    db: Session,
    article_id: str,
    inviter_id: str,
    invited_id: str,
) -> dict:
    """Invite a user to review an article during sedimentation.

    Only a maintainer of the article can send invitations.  The invitation
    is recorded as a Review row with ``status='invited'``.

    Raises NotFoundError if the article or invited user is not found.
    Raises BadRequestError if the article is not in sedimentation or inviter == invited.
    Raises NotAuthorizedError if the inviter is not a maintainer.
    Raises ConflictError if the user has a pending/accepted invitation, or
        has already submitted a review and the author has not yet replied.
    """
    article = require_article(db, article_id)
    if article.status != "sedimentation":
        raise BadRequestError("Can only invite reviewers to articles in sedimentation")

    # Self-invite: authors review their own articles via publish, not invite.
    if inviter_id == invited_id:
        raise BadRequestError("Cannot invite yourself to review")

    mids = get_maintainer_ids(db, article_id)
    if inviter_id not in mids:
        raise NotAuthorizedError("Only article maintainers can invite reviewers")

    invited_user = require_user(db, invited_id)

    # Guard: no pending or accepted invitation may already exist.
    pending = get_pending_invitation(db, article_id, invited_id)
    if pending is not None:
        raise ConflictError("User already has a pending invitation for this article")
    accepted = get_accepted_invitation(db, article_id, invited_id)
    if accepted is not None:
        raise ConflictError("User has already accepted an invitation for this article")

    # Guard: if the reviewer already submitted a review, require author reply
    # before re-invitation.
    for r in _get(db, article_id):
        if r.reviewer_id == invited_id and r.status == "submitted":
            if not _author_has_replied(article_id):
                raise ConflictError(
                    "Reviewer has already submitted a review. "
                    "Author must reply to the review before re-inviting."
                )

    # Create a pending invitation row.
    inv = Review(
        article_id=article_id,
        commit_hash="pending",
        reviewer_id=invited_id,
        scope="sedimentation",
        status="invited",
        scores={},
        invited_by=inviter_id,
        invited_at=datetime.now(timezone.utc),
    )
    db.add(inv)
    db.flush()

    create_notification(
        db, user_id=invited_id, event="review_invitation",
        message=f"{inviter_id} invited you to review an article",
        article_id=article_id, actor_id=inviter_id,
    )

    return {"invitation_id": inv.id, "article_id": article_id, "reviewer_id": invited_id}


def _author_has_replied(article_id: str) -> bool:
    """Check if any review directory for *article_id* has author replies.

    A reply exists when a review thread has more than one message file
    (the first is the review, subsequent ones are replies).
    """
    rp = require_article_repo(article_id)
    reviews_dir = rp / "reviews"
    if not reviews_dir.is_dir():
        return False
    for reviewer_dir in reviews_dir.iterdir():
        if not reviewer_dir.is_dir():
            continue
        threads_dir = reviewer_dir / "threads"
        if threads_dir.is_dir():
            md_files = sorted(threads_dir.glob("*.md"))
            if len(md_files) > 1:
                return True
    return False


def accept_invitation(
    db: Session,
    article_id: str,
    reviewer_id: str,
) -> dict:
    """Accept a pending review invitation.

    Transitions the Review row from ``status='invited'`` to ``status='accepted'``.

    Raises NotFoundError if no pending invitation exists.
    Raises BadRequestError if the invitation was already declined.
    """
    inv = get_pending_invitation(db, article_id, reviewer_id)
    if inv is None:
        declined = (
            db.query(Review)
            .filter(
                Review.article_id == article_id,
                Review.reviewer_id == reviewer_id,
                Review.status == "declined",
            )
            .first()
        )
        if declined is not None:
            raise BadRequestError("Cannot accept a declined invitation")
        raise NotFoundError("No pending invitation found for this article")

    update_review_status(db, inv, "accepted")
    db.flush()

    return {"invitation_id": inv.id, "article_id": article_id, "status": "accepted"}


def decline_invitation(
    db: Session,
    article_id: str,
    reviewer_id: str,
) -> dict:
    """Decline a pending review invitation.

    Transitions the Review row from ``status='invited'`` to ``status='declined'``.

    Raises NotFoundError if no pending invitation exists.
    Raises BadRequestError if the invitation was already accepted.
    """
    inv = get_pending_invitation(db, article_id, reviewer_id)
    if inv is None:
        acc = get_accepted_invitation(db, article_id, reviewer_id)
        if acc is not None:
            raise BadRequestError("Cannot decline an already accepted invitation")
        raise NotFoundError("No pending invitation found for this article")

    update_review_status(db, inv, "declined")
    db.flush()

    return {"invitation_id": inv.id, "article_id": article_id, "status": "declined"}


def submit_reply(
    db: Session,
    article_id: str,
    user_id: str,
    reviewer_ref: str,
    content: str,
    *,
    signing_key_bytes: bytes | None = None,
    pubkey_hex: str | None = None,
) -> dict:
    """Post an author reply to a review thread.  Git-first — committed to the
    reviewer's directory under ``threads/{nnn}.md`` with a ``[reply]`` marker.

    *reviewer_ref* is the reviewer's user ID (real UUID for published articles,
    or the target reviewer UUID for sedimentation — the directory ID is derived
    from this).

    Notifies the reviewer via the notification system.

    Raises NotFoundError if the user, article, or reviewer is not found.
    """
    user = require_user(db, user_id)
    article = require_article(db, article_id)
    reviewer = require_user(db, reviewer_ref)

    mids = get_maintainer_ids(db, article_id)
    assert_can_reply_to_review(
        article, mids, user,
        fold_threshold=params.reputation.fold_score_threshold,
    )

    if article.status == "sedimentation":
        directory_id = _derive_anonymous_id(article_id, signing_key=signing_key_bytes)
        display_name = derive_anonymous_name(directory_id)
        email = make_peerpedia_email(f"anon-{directory_id}")
    else:
        directory_id = reviewer_ref
        display_name = user.name
        email = make_peerpedia_email(user_id)

    commit_hash = _write_thread_message(
        article_id, directory_id, content, display_name, email,
        commit_marker="[reply]",
        signing_key_bytes=signing_key_bytes, pubkey_hex=pubkey_hex,
    )

    create_notification(
        db, user_id=reviewer_ref, event="review_reply",
        message=f"{user.name} replied to your review",
        article_id=article_id, actor_id=user_id,
    )

    return {"article_id": article_id, "directory_id": directory_id,
            "commit_hash": commit_hash}



def _derive_anonymous_id(article_id: str, *, signing_key: bytes) -> str:
    """Derive a stable anonymous directory ID for a reviewer+article pair.

    Uses HMAC-SHA256 with the reviewer's Ed25519 signing key so the output
    is deterministic for the same reviewer+article pair but cannot be
    verified by anyone who doesn't hold the key.

    Raises ValueError if *signing_key* is None — fail fast, no fallback.
    """
    import hmac
    if signing_key is None:
        raise ValueError("signing_key is required for anonymous review ID derivation")
    return hmac.new(signing_key, article_id.encode(), "sha256").hexdigest()[:12]


def assert_valid_review(scores: dict, comment: str | None = None, *, check_comment: bool = True) -> None:
    """Validate a review before submission — shared by local and sync paths.

    Raises BadRequestError if scores are invalid or comment is too short.
    Called by both ``submit_review`` (local, *check_comment=True*) and
    ``sync_reviews_from_worktree`` (sync, *check_comment=False* — comment
    is in thread files not scores.json).
    """
    if check_comment:
        min_len = params.comment.min_length
        if not comment or not isinstance(comment, str):
            raise BadRequestError("Review comment is required")
        if len(comment.strip()) < min_len:
            raise BadRequestError(
                f"Review comment must be at least {min_len} characters "
                f"(got {len(comment.strip())})"
            )

    full_dims = set(SCORE_DIMENSIONS.values())
    abbr_dims = set(SCORE_DIMENSIONS.keys())
    if not isinstance(scores, dict):
        raise BadRequestError("scores must be a dict")
    keys = set(scores.keys())
    if not (abbr_dims.issubset(keys) or full_dims.issubset(keys)):
        raise BadRequestError(
            f"scores must contain all {len(SCORE_DIMENSIONS)} dimensions: "
            f"{', '.join(sorted(SCORE_DIMENSIONS.keys()))}"
        )
    for dim, val in scores.items():
        if not isinstance(val, (int, float)) or val < 1 or val > 5:
            raise BadRequestError(
                f"score dimension '{dim}' must be a number between 1 and 5, got {val!r}"
            )

    # Normalize abbreviation keys to full names for downstream consistency.
    # aggregate_review_scores accesses only full-name keys (DIMS =
    # SCORE_DIMENSIONS.values()).  accept both but store full names.
    _dim_map = dict(SCORE_DIMENSIONS)
    for abbr, full in _dim_map.items():
        if abbr in scores and full not in scores:
            scores[full] = scores.pop(abbr)


def _write_thread_message(
    article_id: str,
    directory_id: str,
    content: str,
    display_name: str,
    email: str,
    commit_marker: str,
    *,
    signing_key_bytes: bytes | None = None,
    pubkey_hex: str | None = None,
) -> str:
    """Append a message to the review thread.  Returns the new HEAD commit hash.

    *commit_marker* is ``"[review]"`` for reviewer messages or ``"[reply]"``
    for author replies.
    """
    rp = require_article_repo(article_id)
    threads_dir = rp / "reviews" / directory_id / "threads"
    threads_dir.mkdir(parents=True, exist_ok=True)

    lock = get_article_lock(article_id)
    acquired = lock.acquire(timeout=10)
    if not acquired:
        raise ConflictError("Article busy — retry later")

    try:
        existing = sorted(threads_dir.glob("*.md"))
        next_num = len(existing) + 1
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        thread_path = threads_dir / f"{next_num:03d}.md"
        thread_path.write_text(f"### {display_name} ({ts})\n\n{content}\n")

        if signing_key_bytes:
            with temp_signing_key(signing_key_bytes) as key_path:
                h = commit_article(
                    rp, f"{commit_marker} {display_name}", display_name, email,
                    signing_key=key_path, pubkey_hex=pubkey_hex,
                )
        else:
            h = commit_article(
                rp, f"{commit_marker} {display_name}", display_name, email,
                signing_key=None, pubkey_hex=pubkey_hex,
            )
    finally:
        lock.release()
    return h


def write_review_to_git(
    article_id: str,
    directory_id: str,
    scores: dict,
    comment: str,
    display_name: str,
    email: str,
    signing_key_bytes: bytes | None = None,
    pubkey_hex: str | None = None,
) -> str:
    """Write review to git: scores.json + thread message.  Returns HEAD hash.

    Raises NotFoundError if the article repo does not exist.
    """
    rp = DEFAULT_ARTICLES_DIR / article_id
    review_dir = rp / "reviews" / directory_id
    review_dir.mkdir(parents=True, exist_ok=True)

    # Write scores.json first, then delegate to _write_thread_message
    # which acquires the lock and commits both files in one git operation.
    (review_dir / "scores.json").write_text(json.dumps(scores, indent=2))

    return _write_thread_message(
        article_id, directory_id, comment, display_name, email,
        commit_marker="[review]",
        signing_key_bytes=signing_key_bytes, pubkey_hex=pubkey_hex,
    )


# ── Read wrapper ──────────────────────────────────────────────────────────


def get_reviews_for_article(db: Session, article_id: str) -> list:
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

    Updates the Review record in DB and writes to git.

    Raises NotFoundError if the article or review is not found.
    Raises NotAuthorizedError if the rater is not a maintainer.
    Raises BadRequestError if the score is outside 1-5 range.
    """
    article = require_article(db, article_id)
    mids = get_maintainer_ids(db, article_id)
    if rater_id not in mids:
        raise NotAuthorizedError("Only article maintainers can rate reviews")

    if score < 1 or score > 5:
        raise BadRequestError("Helpfulness score must be between 1 and 5")

    # Find the review and update it
    all_reviews = _get(db, article_id)
    target = None
    for r in all_reviews:
        if r.reviewer_id == reviewer_id:
            target = r
            break
    if target is None:
        raise NotFoundError(f"No review found for reviewer {reviewer_id}")

    target.helpfulness_score = score
    db.flush()

    return {"review_id": target.id, "helpfulness_score": score}
