# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Composite guard functions — those that need both git and DB.

Pure rules live in ``rules/``, DB-only guards in ``storage/db/guards.py``,
git-only guards in ``storage/git/guards.py``.  This module re-exports
from all three so callers have a single import target.
"""

from __future__ import annotations

import logging
from pathlib import Path

from peerpedia_core.config.params import extract_user_id_from_email
from peerpedia_core.exceptions import BadRequestError, ConflictError, NotFoundError
from peerpedia_core.storage.db.crud_article import get_author_ids
from peerpedia_core.storage.db import Session
from peerpedia_core.storage.db.crud_review import (
    get_accepted_invitation, get_pending_invitation, get_reviews_for_article,
)
from peerpedia_core.storage.db.crud_user import get_users_by_ids, set_user_pubkey_tofu
from peerpedia_core.storage.git import (
    get_commit_authors, get_commit_history, read_status_from_git,
)
from peerpedia_core.storage.git.guards import (
    require_article_repo, require_commit_pubkey_signature,
)
from peerpedia_core.types.status import is_platform_commit
from peerpedia_core.storage.git.trailers import parse_closes_trailer, validate_closes_target

# ── Re-exports ───────────────────────────────────────────────────────────────

from peerpedia_core.rules.articles import (  # pure authorization rules
    PUBLIC_READABLE_STATUSES,
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
    visible_statuses_for_user,
)
from peerpedia_core.rules.reviews import (  # pure review validation
    assert_valid_review,
    guard_proposal_owner,
    require_integrity_level,
    require_signing_key_not_none,
)
from peerpedia_core.storage.db.guards import (  # re-export DB guards
    assert_caller_is_maintainer,
    authorize_article_action,
    guard_invitation_not_accepted,
    guard_invitation_not_declined,
    guard_not_already_maintainer,
    guard_not_last_maintainer,
    guard_sedimentation_limit,
    require_alias_nonempty,
    require_article,
    require_authors_exist,
    require_draft_status,
    require_following_for_alias,
    require_helpfulness_score_range,
    require_invitation,
    require_keys,
    require_maintainer,
    require_merge_proposal_open,
    require_not_same,
    require_open_proposal,
    require_review,
    require_sedimentation,
    require_signing_key,
    require_title_nonempty,
    require_user,
    validate_follow_entries,
)
from peerpedia_core.storage.git.guards import (  # re-export git guards
    require_review_scores,
)

logger = logging.getLogger(__name__)


# ── Composite: git + DB ──────────────────────────────────────────────────────


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


# ── ArticleMetaStorage integrity ────────────────────────────────────────────────────────


def assert_article_integrity(db: Session, article_id: str, *, level: str = "light") -> None:
    """Verify article integrity at the specified level.

    ``level="light"`` — verify the latest human-authored commit's signature.
    ``level="full"`` — light + DB cross-validation, auto-repair if inconsistent.
    """
    try:
        rp = require_article_repo(article_id)
        require_article(db, article_id)
    except NotFoundError:
        return

    require_integrity_level(level)
    if level == "light":
        _verify_light(rp)
    else:
        _verify_light(rp)
        _verify_full(db, article_id, rp)


def _verify_light(repo_path: Path) -> None:
    """Verify the latest human-authored commit's signature."""
    commits = list(get_commit_history(repo_path, max_count=1))
    if not commits:
        return
    commit = commits[0]
    if is_platform_commit(commit["author_email"]):
        return
    require_commit_pubkey_signature(
        repo_path, commit["hash"], commit["message"], commit["author_email"],
    )


def _verify_full(db: Session, article_id: str, repo_path: Path) -> None:
    """DB cross-validation: rebuild DB cache from git SOT if inconsistent."""
    from peerpedia_core.core.reconcile import reconcile_all, reconcile_authors

    article = require_article(db, article_id)

    expected_status = read_status_from_git(repo_path)
    if expected_status is not None and article.status != expected_status:
        reconcile_all(db, article_id)
        return

    db_authors = set(get_author_ids(db, article_id))
    git_authors = get_commit_authors(repo_path)
    if db_authors != git_authors:
        reconcile_authors(db, article_id)
