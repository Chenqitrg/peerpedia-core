# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

r"""ScriptMaintainer CRUD — database only, no side effects.

All functions call ``session.flush()`` only — the caller (CLI/REPL) is
responsible for ``session.commit()``.

Functions
---------
  list_articles_by_maintainer  All articles where user is a maintainer
  add_maintainer               Grant maintainer status (idempotent)
  remove_maintainer            Revoke maintainer status
  get_maintainer_ids           Ordered maintainer ID list for an article
  is_maintainer                True if user is a maintainer

ScriptMaintainer tracks who *manages* an article (edit/delete/publish/sync).
It is orthogonal to ArticleAuthorStorage — git history determines contribution,
this table determines management authority.  Maintainer status is always
explicitly granted, never derived.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from peerpedia_core.storage.db.models import ArticleMetaStorage, ScriptMaintainerStorage


def list_articles_by_maintainer(session: Session, user_id: str) -> list[ArticleMetaStorage]:
    """List all articles where *user_id* is a maintainer."""
    return (
        session.query(ArticleMetaStorage)
        .join(ScriptMaintainerStorage, ArticleMetaStorage.id == ScriptMaintainerStorage.article_id)
        .filter(ScriptMaintainerStorage.user_id == user_id)
        .all()
    )


def add_maintainer(session: Session, article_id: str, user_id: str) -> ScriptMaintainerStorage:
    """Grant maintainer status to a user for an article.

    Idempotent — returns existing row if already a maintainer.
    """
    existing = session.query(ScriptMaintainerStorage).filter(
        ScriptMaintainerStorage.article_id == article_id,
        ScriptMaintainerStorage.user_id == user_id,
    ).first()
    if existing:
        return existing
    row = ScriptMaintainerStorage(article_id=article_id, user_id=user_id)
    session.add(row)
    session.flush()
    return row


def remove_maintainer(session: Session, article_id: str, user_id: str) -> bool:
    """Revoke maintainer status.  Returns True if a row was deleted, False if
    the user was not a maintainer (no-op).
    """
    deleted = (
        session.query(ScriptMaintainerStorage)
        .filter(
            ScriptMaintainerStorage.article_id == article_id,
            ScriptMaintainerStorage.user_id == user_id,
        )
        .delete()
    )
    session.flush()
    return deleted > 0


def get_maintainer_ids(session: Session, article_id: str) -> list[str]:
    """Return maintainer IDs for an article, ordered by created_at."""
    rows = (
        session.query(ScriptMaintainerStorage)
        .filter(ScriptMaintainerStorage.article_id == article_id)
        .order_by(ScriptMaintainerStorage.created_at)
        .all()
    )
    return [r.user_id for r in rows]


def is_maintainer(session: Session, article_id: str, user_id: str) -> bool:
    """Return True if *user_id* is a maintainer of *article_id*."""
    return (
        session.query(ScriptMaintainerStorage)
        .filter(
            ScriptMaintainerStorage.article_id == article_id,
            ScriptMaintainerStorage.user_id == user_id,
        )
        .first()
        is not None
    )
