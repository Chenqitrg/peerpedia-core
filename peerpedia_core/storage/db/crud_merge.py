# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""MergeProposal CRUD operations."""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from peerpedia_core.storage.db.models import MergeProposal


def create_merge_proposal(
    session: Session,
    fork_id: str,
    target_id: str,
    proposer_id: str,
) -> MergeProposal:
    """Create a merge request from *fork_id* into *target_id*.

    Raises ValueError if fork and target are the same article.
    """
    if fork_id == target_id:
        raise ValueError("Cannot create a merge proposal for an article with itself")
    mp = MergeProposal(
        fork_article_id=fork_id,
        target_article_id=target_id,
        proposer_id=proposer_id,
        status="open",
    )
    session.add(mp)
    session.flush()
    return mp


def get_merge_proposal(session: Session, proposal_id: str) -> MergeProposal | None:
    """Return a merge proposal by ID, or None."""
    return session.get(MergeProposal, proposal_id)


def get_merge_proposals_for_article(session: Session, article_id: str) -> list[MergeProposal]:
    """Return all merge proposals targeting *article_id*, newest first."""
    return (
        session.query(MergeProposal)
        .filter(MergeProposal.target_article_id == article_id)
        .order_by(MergeProposal.created_at.desc())
        .all()
    )


def _resolve(session: Session, proposal_id: str, new_status: str) -> MergeProposal:
    mp = session.get(MergeProposal, proposal_id)
    if mp is None:
        raise ValueError(f"MergeProposal {proposal_id} not found")
    if mp.status != "open":
        raise ValueError(f"MergeProposal {proposal_id} is already {mp.status}")
    mp.status = new_status
    mp.resolved_at = datetime.now(timezone.utc)
    session.flush()
    return mp


def accept_merge_proposal(session: Session, proposal_id: str) -> MergeProposal:
    """Accept a merge proposal.  Raises ValueError if not found or already resolved."""
    return _resolve(session, proposal_id, "accepted")


def reject_merge_proposal(session: Session, proposal_id: str) -> MergeProposal:
    """Intentionally unwired — target maintainers cannot reject contributions."""
    return _resolve(session, proposal_id, "rejected")


def withdraw_merge_proposal(session: Session, proposal_id: str) -> MergeProposal:
    """Change a merge proposal status to ``withdrawn``.

    Authorization (proposer-only) is enforced by the commands layer.
    """
    return _resolve(session, proposal_id, "withdrawn")
