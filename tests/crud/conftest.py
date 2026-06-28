# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Shared helpers for CRUD tests."""

import uuid

from sqlalchemy.orm import Session

from peerpedia_core.storage.db.models import ArticleAuthorStorage, ArticleMetaStorage, UserStorage


def make_user(session: Session, name: str) -> UserStorage:
    """Create and commit a minimal UserStorage row."""
    u = UserStorage(
        id=str(uuid.uuid4()),
        public_key="0000000000000000000000000000000000000000000000000000000000000000",
        name=name,
        affiliation="Test",
    )
    session.add(u)
    session.commit()
    return u


def make_article(session: Session, authors: list[str], **kw) -> ArticleMetaStorage:
    """Create and commit an ArticleMetaStorage row with author join rows."""
    a = ArticleMetaStorage(title=kw.pop("title", "A Treatise on Peer Review"), **kw)
    session.add(a)
    session.flush()
    for pos, aid in enumerate(authors):
        session.add(ArticleAuthorStorage(article_id=a.id, author_id=aid, position=pos))
    session.commit()
    return a


def default_scores() -> dict[str, float]:
    return {"originality": 3, "rigor": 3, "completeness": 3, "pedagogy": 3, "impact": 3}
