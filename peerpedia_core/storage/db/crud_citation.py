# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Citation CRUD operations."""

from sqlalchemy.orm import Session

from peerpedia_core.storage.db.models import Citation


def create_or_update_citation(
    session: Session,
    from_id: str,
    to_id: str,
    forward: float = 0.0,
    backward: float = 0.0,
) -> Citation:
    if from_id == to_id:
        raise ValueError("An article cannot cite itself")
    c = session.query(Citation).filter(Citation.from_article_id == from_id, Citation.to_article_id == to_id).first()
    if c:
        c.forward_prob = forward
        c.backward_prob = backward
    else:
        c = Citation(
            from_article_id=from_id,
            to_article_id=to_id,
            forward_prob=forward,
            backward_prob=backward,
        )
        session.add(c)
    session.commit()
    return c


def get_citation(session: Session, from_id: str, to_id: str) -> Citation | None:
    return session.query(Citation).filter(Citation.from_article_id == from_id, Citation.to_article_id == to_id).first()


def get_citations(session: Session, article_id: str) -> list[Citation]:
    """All citation edges involving this article."""
    return session.query(Citation).filter((Citation.from_article_id == article_id) | (Citation.to_article_id == article_id)).all()


def get_cites(session: Session, article_id: str) -> list[Citation]:
    """Articles this article cites (outgoing edges)."""
    return session.query(Citation).filter(Citation.from_article_id == article_id).all()


def get_cited_by(session: Session, article_id: str) -> list[Citation]:
    """Articles that cite this article (incoming edges)."""
    return session.query(Citation).filter(Citation.to_article_id == article_id).all()
