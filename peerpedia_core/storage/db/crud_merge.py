# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""MergeProposal CRUD operations."""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from peerpedia_core.storage.db._validators import require_merge_proposal_open, require_not_same
from peerpedia_core.storage.db.models import ArticleMetaStorage, MergeProposalStorage
from peerpedia_core.types.status import ArticleStatus


def create_merge_proposal(
    session: Session,
    fork_id: str,
    target_id: str,
    proposer_id: str,
) -> MergeProposalStorage:
    """Create a merge request from *fork_id* into *target_id*."""
    require_not_same(fork_id, target_id, label="merge")

    mp = MergeProposalStorage(
        fork_article_id=fork_id,
        target_article_id=target_id,
        proposer_id=proposer_id,
        status="open",
    )
    session.add(mp)
    session.flush()
    return mp


def get_merge_proposal(session: Session, proposal_id: str) -> MergeProposalStorage | None:
    """Return a merge proposal by ID, or None."""
    return session.get(MergeProposalStorage, proposal_id)


def get_merge_proposals_for_article(session: Session, article_id: str) -> list[MergeProposalStorage]:
    """Return all merge proposals targeting *article_id*, newest first."""
    return (
        session.query(MergeProposalStorage)
        .filter(MergeProposalStorage.target_article_id == article_id)
        .order_by(MergeProposalStorage.created_at.desc())
        .all()
    )


def _resolve(session: Session, proposal_id: str, new_status: ArticleStatus) -> MergeProposalStorage:
    mp = session.get(MergeProposalStorage, proposal_id)
    require_merge_proposal_open(mp)
    mp.status = new_status
    mp.resolved_at = datetime.now(timezone.utc)
    session.flush()
    return mp


def accept_merge_proposal(session: Session, proposal_id: str) -> MergeProposalStorage:
    """Accept a merge proposal.  Raises ValueError if not found or already resolved."""
    return _resolve(session, proposal_id, "accepted")


def reject_merge_proposal(session: Session, proposal_id: str) -> MergeProposalStorage:
    """Intentionally unwired — target maintainers cannot reject contributions."""
    return _resolve(session, proposal_id, ArticleStatus.REJECTED)


def withdraw_merge_proposal(session: Session, proposal_id: str) -> MergeProposalStorage:
    """Change a merge proposal status to ``withdrawn``.

    Authorization (proposer-only) is enforced by the commands layer.
    """
    return _resolve(session, proposal_id, "withdrawn")
