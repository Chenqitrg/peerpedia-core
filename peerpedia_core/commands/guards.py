# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Composite guard functions — DB + git + policies combined.

Pure DB-level guards live in ``storage/db/guards.py`` and are re-exported
here so commands-layer callers have a single import target.
"""

from __future__ import annotations

import logging
from pathlib import Path

from peerpedia_core.config.params import extract_user_id_from_email, params
from peerpedia_core.config.paths import article_repo_path
from peerpedia_core.exceptions import BadRequestError, ConflictError, NotFoundError, NotAuthorizedError
from peerpedia_core.policies.articles import (
    assert_article_has_score,
    assert_can_accept_merge,
    assert_can_delete_article,
    assert_can_edit_article,
    assert_can_fork_article,
    assert_can_publish_article,
    assert_can_reply_to_review,
    assert_can_rollback_article,
    assert_can_submit_review,
    assert_not_folded,
    validate_self_review_scores,
)
from peerpedia_core.types.status import is_platform_commit
from peerpedia_core.storage.db import Session
from peerpedia_core.storage.db.crud_article import count_articles
from peerpedia_core.storage.db.crud_review import (
    get_accepted_invitation, get_pending_invitation, get_reviews_for_article,
)
from peerpedia_core.storage.db.crud_user import get_users_by_ids, set_user_pubkey_tofu
from peerpedia_core.storage.db.guards import (  # re-export pure DB guards
    assert_caller_is_maintainer,
    guard_not_already_maintainer,
    require_alias_nonempty,
    require_article,
    require_authors_exist,
    require_draft_status,
    require_following_for_alias,
    require_helpfulness_score_range,
    require_keys,
    require_maintainer,
    require_merge_proposal_open,
    require_not_same,
    require_review,
    require_sedimentation,
    require_signing_key,
    require_title_nonempty,
    require_user,
    validate_follow_entries,
)
from peerpedia_core.storage.git import (
    get_commit_history,
    read_review_scores,
    require_commit_pubkey_signature,
)
from peerpedia_core.commands.trailers import parse_closes_trailer, validate_closes_target
from peerpedia_core.types.scores import normalize_score_keys

logger = logging.getLogger(__name__)


# ── Resource existence (git-aware) ─────────────────────────────────────────


def require_article_repo(article_id: str) -> Path:
    """Return the article repo path or raise NotFoundError."""
    rp = article_repo_path(article_id)
    if not (rp / ".git").is_dir():
        raise NotFoundError("Article repo not found", resource_type="article", resource_id=article_id)
    return rp


def require_review_scores(repo_path: Path, reviewer_dir: str, article_id: str) -> dict:
    """Return parsed review scores or raise NotFoundError."""
    scores = read_review_scores(repo_path, reviewer_dir)
    if scores is None:
        raise NotFoundError(
            f"scores.json not found in reviews/{reviewer_dir}/ for article {article_id}",
            resource_type="review_scores",
            resource_id=f"{article_id}/reviews/{reviewer_dir}",
        )
    return scores


# ── Composite authorization ────────────────────────────────────────────────


def authorize_article_action(
    db: Session, article_id: str, user_id: str,
):
    """Resolve user, article, and maintainer_ids; block if article is folded."""
    from peerpedia_core.storage.db.crud_maintainer import get_maintainer_ids

    user = require_user(db, user_id)
    article = require_article(db, article_id)
    mids = get_maintainer_ids(db, article_id)
    assert_not_folded(article, threshold=params.reputation.fold_score_threshold)
    return user, article, mids


# ── Sedimentation guards ───────────────────────────────────────────────────


def guard_sedimentation_limit(db: Session, user_id: str) -> None:
    """Raise BadRequestError if *user_id* has too many articles in sedimentation."""
    in_pool = count_articles(db, status="sedimentation", author_id=user_id)
    if in_pool >= params.sink.max_sedimentation_per_author:
        raise BadRequestError(
            f"Author already has {in_pool} article(s) in sedimentation "
            f"(max {params.sink.max_sedimentation_per_author})"
        )


# ── Review invitation guards ───────────────────────────────────────────────


def require_invitation(db: Session, article_id: str, reviewer_id: str) -> None:
    """Raise NotAuthorizedError if the reviewer lacks an accepted invitation.

    Only call when the article is in sedimentation — the caller makes that
    decision, this function only checks + raises.
    """
    if get_accepted_invitation(db, article_id, reviewer_id) is None:
        raise NotAuthorizedError(
            "You have not been invited to review this article. "
            "During sedimentation, only invited reviewers may submit reviews."
        )


def guard_invitation_conflicts(db: Session, article_id: str, invited_id: str) -> None:
    """Raise ConflictError if the invitee has a conflicting invitation or review state."""
    if get_pending_invitation(db, article_id, invited_id) is not None:
        raise ConflictError("User already has a pending invitation for this article")
    if get_accepted_invitation(db, article_id, invited_id) is not None:
        raise ConflictError("User has already accepted an invitation for this article")
    for r in get_reviews_for_article(db, article_id):
        if r.reviewer_id == invited_id and r.status == "submitted":
            if not _author_has_replied(article_id):
                raise ConflictError(
                    "Reviewer has already submitted a review. "
                    "Author must reply to the review before re-inviting."
                )


def _author_has_replied(article_id: str) -> bool:
    """Check if any review directory for *article_id* has author replies."""
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


# ── Commit verification ────────────────────────────────────────────────────


def verify_commit_signature_and_tofu(
    db: Session, repo_path: Path, commit: dict, users_by_id: dict,
) -> None:
    """Verify one commit's Ed25519 signature and update TOFU pubkey."""
    pubkey_hex = require_commit_pubkey_signature(
        repo_path, commit["hash"], commit["message"], commit["author_email"],
    )
    uid = extract_user_id_from_email(commit["author_email"])
    result = set_user_pubkey_tofu(db, uid, pubkey_hex, user=users_by_id.get(uid))
    if result == "rotated":
        logger.warning(
            "Key rotation for %s: → %s... — auto-updated.", uid, pubkey_hex[:16],
        )


def verify_new_commits(db: Session, repo_path: Path, *, since_hash: str) -> None:
    """Verify signatures on new human-authored commits (TOFU model)."""
    commits = list(get_commit_history(repo_path, since_hash=since_hash))
    human_ids = {
        extract_user_id_from_email(c["author_email"])
        for c in commits if not is_platform_commit(c["author_email"])
    }
    users_by_id = {u.id: u for u in get_users_by_ids(db, human_ids)}

    for c in commits:
        if not is_platform_commit(c["author_email"]):
            verify_commit_signature_and_tofu(db, repo_path, c, users_by_id)


# ── Closes trailer guard ───────────────────────────────────────────────────


def guard_closes_trailer(message: str, article_id: str) -> None:
    """Raise BadRequestError if *message* lacks a valid Closes: trailer."""
    if not message:
        raise BadRequestError(
            "Sedimentation edits require a Closes: review/{dir}/thread-{n} "
            "trailer in the commit message"
        )
    parsed = parse_closes_trailer(message)
    if parsed is None:
        raise BadRequestError(
            "Sedimentation edits must reference a review thread via "
            "Closes: review/{reviewer-dir}/thread-{n} in the commit message"
        )
    reviewer_dir, thread_num = parsed
    if not validate_closes_target(article_id, reviewer_dir, thread_num):
        raise BadRequestError(
            f"Closes target not found: review/{reviewer_dir}/thread-{thread_num:03d}"
        )


# ── Merge proposal guard (DB + business context) ───────────────────────────


def require_open_proposal(db: Session, proposal_id: str, article_id: str):
    """Return the merge proposal, or raise if missing/wrong article/not open."""
    from peerpedia_core.storage.db.crud_merge import get_merge_proposal

    mp = get_merge_proposal(db, proposal_id)
    if mp is None:
        raise NotFoundError("Merge proposal not found")
    if mp.target_article_id != article_id:
        raise BadRequestError("Proposal does not belong to this article")
    if mp.status != "open":
        raise BadRequestError(f"Merge proposal {proposal_id} is already {mp.status}")
    return mp


# ── Proposal guards ────────────────────────────────────────────────────────


def guard_proposal_owner(mp, user_id: str) -> None:
    """Raise NotAuthorizedError if *user_id* is not the proposal owner."""
    if mp.proposer_id != user_id:
        raise NotAuthorizedError("Only the proposal creator can withdraw this proposal")


# ── Invitation state guards ────────────────────────────────────────────────


def guard_invitation_not_declined(db: Session, article_id: str, reviewer_id: str) -> None:
    """Raise BadRequestError if invitation was already declined."""
    from peerpedia_core.storage.db.models import Review
    declined = (
        db.query(Review)
        .filter(Review.article_id == article_id, Review.reviewer_id == reviewer_id,
                Review.status == "declined")
        .first()
    )
    if declined is not None:
        raise BadRequestError("Cannot accept a declined invitation")


def guard_invitation_not_accepted(db: Session, article_id: str, reviewer_id: str) -> None:
    """Raise BadRequestError if invitation was already accepted."""
    if get_accepted_invitation(db, article_id, reviewer_id) is not None:
        raise BadRequestError("Cannot decline an already accepted invitation")


# ── Crypto guards ──────────────────────────────────────────────────────────


def require_signing_key_not_none(signing_key: bytes | None) -> None:
    """Raise ValueError if *signing_key* is None."""
    if signing_key is None:
        raise ValueError("signing_key is required for anonymous review ID derivation")


# ── Integrity guards ───────────────────────────────────────────────────────


def require_integrity_level(level: str) -> None:
    """Raise ValueError if *level* is not 'light' or 'full'."""
    if level not in ("light", "full"):
        raise ValueError(f"Unknown integrity level: {level}")


# ── Maintainer guards ──────────────────────────────────────────────────────


def guard_not_last_maintainer(db: Session, article_id: str, caller_id: str, user_id: str) -> None:
    """Raise NotAuthorizedError if caller tries to self-remove as the last maintainer."""
    if caller_id != user_id:
        return
    from peerpedia_core.storage.db.crud_maintainer import get_maintainer_ids
    if len(get_maintainer_ids(db, article_id)) <= 1:
        raise NotAuthorizedError(
            "Cannot remove yourself as the last maintainer. "
            "Add another maintainer first, then remove yourself."
        )

# ── Review validation ──────────────────────────────────────────────────────


def assert_valid_review(scores: dict, comment: str | None = None, *, check_comment: bool = True) -> None:
    """Validate a review before submission — shared by local and sync paths.

    Raises BadRequestError if scores are invalid or comment is too short.
    """
    # ── Validate ───────────────────────────────────────────────────────────
    errors = _collect_review_errors(scores, comment, check_comment=check_comment)
    if errors:
        raise BadRequestError("; ".join(errors))

    # ── Normalize keys ─────────────────────────────────────────────────────
    normalize_score_keys(scores)


def _collect_review_errors(scores: dict, comment: str | None, *, check_comment: bool) -> list[str]:
    """Orchestrate review validation — delegate to individual checkers."""
    errors: list[str] = []

    if check_comment:
        _validate_review_comment(comment, errors)
    _validate_review_scores(scores, errors)

    return errors


def _validate_review_scores(scores: dict, errors: list[str]) -> None:
    """Append score validation errors to *errors* list."""
    if not isinstance(scores, dict):
        errors.append("scores must be a dict")
        return

    _check_score_dimensions(scores, errors)
    _check_score_values(scores, errors)


def _check_score_dimensions(scores: dict, errors: list[str]) -> None:
    """Append dimension completeness errors to *errors* list."""
    from peerpedia_core.types.scores import SCORE_DIMENSIONS

    abbr_dims = set(SCORE_DIMENSIONS.keys())
    full_dims = set(SCORE_DIMENSIONS.values())
    keys = set(scores.keys())
    if not (abbr_dims.issubset(keys) or full_dims.issubset(keys)):
        errors.append(
            f"scores must contain all {len(SCORE_DIMENSIONS)} dimensions: "
            f"{', '.join(sorted(SCORE_DIMENSIONS.keys()))}"
        )


def _check_score_values(scores: dict, errors: list[str]) -> None:
    """Append score value range errors (1-5) to *errors* list."""
    for dim, val in scores.items():
        if not isinstance(val, (int, float)) or val < 1 or val > 5:
            errors.append(
                f"score dimension '{dim}' must be a number between 1 and 5, got {val!r}"
            )


def _validate_review_comment(comment: str | None, errors: list[str]) -> None:
    """Append comment validation errors to *errors* list."""
    from peerpedia_core.config.params import params

    min_len = params.comment.min_length
    if not comment or not isinstance(comment, str):
        errors.append("Review comment is required")
    elif len(comment.strip()) < min_len:
        actual = len(comment.strip())
        errors.append(
            f"Review comment must be at least {min_len} characters "
            f"(got {actual} — {min_len - actual} more needed). "
            f"Tip: echo 'your comment' | wc -c to count before pasting."
        )

