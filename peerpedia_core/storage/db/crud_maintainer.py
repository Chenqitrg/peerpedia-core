# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

r"""ScriptMaintainer CRUD — database only, no side effects.

All functions call ``session.flush()`` only — the caller (CLI/REPL) is
responsible for ``session.commit()``.

ScriptMaintainer tracks who *manages* an article (edit/delete/publish/sync).
It is orthogonal to ArticleAuthor — git history determines contribution,
this table determines management authority.  Maintainer status is always
explicitly granted, never derived.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from peerpedia_core.storage.db.models import ScriptMaintainer


def add_maintainer(session: Session, article_id: str, user_id: str) -> ScriptMaintainer:
    """Grant maintainer status to a user for an article.

    Raises sqlalchemy.exc.IntegrityError if the row already exists
    (unique constraint on article_id + user_id).
    """
    row = ScriptMaintainer(article_id=article_id, user_id=user_id)
    session.add(row)
    session.flush()
    return row


def remove_maintainer(session: Session, article_id: str, user_id: str) -> bool:
    """Revoke maintainer status.  Returns True if a row was deleted, False if
    the user was not a maintainer (no-op).
    """
    deleted = (
        session.query(ScriptMaintainer)
        .filter(
            ScriptMaintainer.article_id == article_id,
            ScriptMaintainer.user_id == user_id,
        )
        .delete()
    )
    session.flush()
    return deleted > 0


def get_maintainer_ids(session: Session, article_id: str) -> list[str]:
    """Return maintainer IDs for an article, ordered by created_at."""
    rows = (
        session.query(ScriptMaintainer)
        .filter(ScriptMaintainer.article_id == article_id)
        .order_by(ScriptMaintainer.created_at)
        .all()
    )
    return [r.user_id for r in rows]


def is_maintainer(session: Session, article_id: str, user_id: str) -> bool:
    """Return True if *user_id* is a maintainer of *article_id*."""
    return (
        session.query(ScriptMaintainer)
        .filter(
            ScriptMaintainer.article_id == article_id,
            ScriptMaintainer.user_id == user_id,
        )
        .first()
        is not None
    )
