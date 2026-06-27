# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Citation CRUD operations."""

from sqlalchemy.orm import Session

from peerpedia_core.storage.db._validators import require_not_same
from peerpedia_core.storage.db.models import CitationStorage


def create_or_update_citation(
    session: Session,
    from_id: str,
    to_id: str,
    forward: float = 0.0,
    backward: float = 0.0,
) -> CitationStorage:
    """Create or update a citation edge between two articles."""
    require_not_same(from_id, to_id, label="cite")
    c = session.query(CitationStorage).filter(CitationStorage.from_article_id == from_id, CitationStorage.to_article_id == to_id).first()
    if c:
        c.forward_prob = forward
        c.backward_prob = backward
    else:
        c = CitationStorage(
            from_article_id=from_id,
            to_article_id=to_id,
            forward_prob=forward,
            backward_prob=backward,
        )
        session.add(c)
    session.flush()
    return c


def get_citation(session: Session, from_id: str, to_id: str) -> CitationStorage | None:
    """Return the citation edge from *from_id* to *to_id*, or None."""
    return session.query(CitationStorage).filter(CitationStorage.from_article_id == from_id, CitationStorage.to_article_id == to_id).first()


def get_citations(session: Session, article_id: str) -> list[CitationStorage]:
    """All citation edges involving this article."""
    return session.query(CitationStorage).filter((CitationStorage.from_article_id == article_id) | (CitationStorage.to_article_id == article_id)).all()


def get_cites(session: Session, article_id: str) -> list[CitationStorage]:
    """Articles this article cites (outgoing edges)."""
    return session.query(CitationStorage).filter(CitationStorage.from_article_id == article_id).all()


def get_cited_by(session: Session, article_id: str) -> list[CitationStorage]:
    """Articles that cite this article (incoming edges)."""
    return session.query(CitationStorage).filter(CitationStorage.to_article_id == article_id).all()
