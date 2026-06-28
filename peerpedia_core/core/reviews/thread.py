# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Review thread — reply to reviews, write to git, anonymous identity."""

from __future__ import annotations

import json
from contextlib import nullcontext
from datetime import datetime, timezone

from peerpedia_core.storage.db import Session
from peerpedia_core.config.params import make_peerpedia_email, params
from peerpedia_core.exceptions import ConflictError
from peerpedia_core.rules.articles import assert_can_reply_to_review
from peerpedia_core.rules.reviews import require_signing_key_not_none
from peerpedia_core.storage.db.guards import require_article, require_user
from peerpedia_core.storage.git.guards import require_article_repo
from peerpedia_core.storage.db.crud_maintainer import get_maintainer_ids
from peerpedia_core.names import derive_anonymous_name
from peerpedia_core.crypto import temp_signing_key
from peerpedia_core.storage.git import commit_article
from peerpedia_core.storage.locks import get_article_lock
from peerpedia_core.core.notifications import create_notification


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
    # ── Authorization ──────────────────────────────────────────────────────
    user = require_user(db, user_id)
    article = require_article(db, article_id)
    reviewer = require_user(db, reviewer_ref)
    mids = get_maintainer_ids(db, article_id)
    assert_can_reply_to_review(
        article, mids, user, fold_threshold=params.reputation.fold_score_threshold,
    )

    # ── Identity ───────────────────────────────────────────────────────────
    dir_id, display_name, email = _resolve_review_identity(
        article, user, reviewer_ref, signing_key_bytes=signing_key_bytes,
    )

    # ── Write to git ───────────────────────────────────────────────────────
    commit_hash = _write_thread_message(
        article_id, dir_id, content, display_name, email,
        commit_marker="[reply]",
        signing_key_bytes=signing_key_bytes, pubkey_hex=pubkey_hex,
    )

    # ── Notify ─────────────────────────────────────────────────────────────
    create_notification(
        db, user_id=reviewer_ref, event="review_reply",
        message=f"{user.name} replied to your review",
        article_id=article_id, actor_id=user_id,
    )

    return {"article_id": article_id, "directory_id": dir_id,
            "commit_hash": commit_hash}


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
    """Write review to git: scores.json + thread message.  Returns HEAD hash."""
    rp = require_article_repo(article_id)
    review_dir = rp / "reviews" / directory_id
    review_dir.mkdir(parents=True, exist_ok=True)
    (review_dir / "scores.json").write_text(json.dumps(scores, indent=2))

    return _write_thread_message(
        article_id, directory_id, comment, display_name, email,
        commit_marker="[review]",
        signing_key_bytes=signing_key_bytes, pubkey_hex=pubkey_hex,
    )


# ── Identity helpers ──────────────────────────────────────────────────────────


def _resolve_review_identity(article, user, reviewer_ref, *, signing_key_bytes):
    """Return (directory_id, display_name, email) for a review write."""
    if article.status == "sedimentation":
        anon_id = _derive_anonymous_id(article.id, signing_key=signing_key_bytes)
        return anon_id, derive_anonymous_name(anon_id), make_peerpedia_email(f"anon-{anon_id}")
    return reviewer_ref, user.name, make_peerpedia_email(user.id)


def _derive_anonymous_id(article_id: str, *, signing_key: bytes) -> str:
    """Derive a stable anonymous directory ID for a reviewer+article pair.

    Uses HMAC-SHA256 with the reviewer's Ed25519 signing key so the output
    is deterministic for the same reviewer+article pair but cannot be
    verified by anyone who doesn't hold the key.

    Raises ValueError if *signing_key* is None — fail fast, no fallback.
    """
    import hmac
    require_signing_key_not_none(signing_key)
    return hmac.new(signing_key, article_id.encode(), "sha256").hexdigest()[:12]


# ── Thread file writer ────────────────────────────────────────────────────────


def _write_thread_message(
    article_id: str, directory_id: str, content: str,
    display_name: str, email: str, commit_marker: str, *,
    signing_key_bytes: bytes | None = None, pubkey_hex: str | None = None,
) -> str:
    """Append a message to the review thread.  Returns HEAD hash."""
    # ── Prepare ────────────────────────────────────────────────────────────
    rp = require_article_repo(article_id)
    threads_dir = rp / "reviews" / directory_id / "threads"
    threads_dir.mkdir(parents=True, exist_ok=True)

    lock = get_article_lock(article_id)
    if not lock.acquire(timeout=10):
        raise ConflictError(code="ARTICLE_BUSY")
    try:
        # ── Write thread file ──────────────────────────────────────────────
        existing = sorted(threads_dir.glob("*.md"))
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        thread_path = threads_dir / f"{len(existing) + 1:03d}.md"
        thread_path.write_text(f"### {display_name} ({ts})\n\n{content}\n")

        # ── Git commit ─────────────────────────────────────────────────────
        with (temp_signing_key(signing_key_bytes) if signing_key_bytes else nullcontext()) as key_path:
            return commit_article(
                rp, f"{commit_marker} {display_name}", display_name, email,
                signing_key=key_path, pubkey_hex=pubkey_hex,
            )
    finally:
        lock.release()
