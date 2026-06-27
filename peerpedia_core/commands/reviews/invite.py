# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Review invitations — invite, accept, decline."""

from __future__ import annotations

from datetime import datetime, timezone

from peerpedia_core.storage.db import Session
from peerpedia_core.exceptions import ConflictError, NotFoundError
from peerpedia_core.commands.guards import (
    guard_invitation_conflicts, guard_invitation_not_accepted,
    guard_invitation_not_declined,
    require_article, require_maintainer, require_not_same,
    require_sedimentation, require_user,
)
from peerpedia_core.storage.db.models import Review
from peerpedia_core.storage.db.crud_review import (
    get_pending_invitation, update_review_status,
)
from peerpedia_core.commands.notifications import create_notification


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
    # ── Authorization ──
    article = require_article(db, article_id)
    require_sedimentation(article)
    require_not_same(inviter_id, invited_id, label="invite")
    require_maintainer(db, article_id, inviter_id)
    require_user(db, invited_id)

    # ── Guards ──
    guard_invitation_conflicts(db, article_id, invited_id)

    # ── Create ──
    inv = _create_invitation(db, article_id, inviter_id, invited_id)

    # ── Notify ──
    create_notification(
        db, user_id=invited_id, event="review_invitation",
        message=f"{inviter_id} invited you to review an article",
        article_id=article_id, actor_id=inviter_id,
    )

    return {"invitation_id": inv.id, "article_id": article_id, "reviewer_id": invited_id}


def _create_invitation(db, article_id: str, inviter_id: str, invited_id: str) -> Review:
    """Insert a pending invitation Review row and flush.  Returns the new row."""
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
    return inv


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
    # ── Lookup ─────────────────────────────────────────────────────────────
    inv = get_pending_invitation(db, article_id, reviewer_id)
    if inv is None:
        guard_invitation_not_declined(db, article_id, reviewer_id)
        raise NotFoundError(
            "No pending invitation found for this article. "
            "Ask the article author to invite you with: "
            f"peerpedia review invite {article_id} --user @you"
        )

    # ── Update DB ──────────────────────────────────────────────────────────
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
    # ── Lookup ─────────────────────────────────────────────────────────────
    inv = get_pending_invitation(db, article_id, reviewer_id)
    if inv is None:
        guard_invitation_not_accepted(db, article_id, reviewer_id)
        raise NotFoundError(
            "No pending invitation to decline for this article — "
            "it may have already been accepted, declined, or expired."
        )

    # ── Update DB ──────────────────────────────────────────────────────────
    update_review_status(db, inv, "declined")
    db.flush()

    return {"invitation_id": inv.id, "article_id": article_id, "status": "declined"}
