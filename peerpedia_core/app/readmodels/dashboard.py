# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Dashboard read models — query helpers for the CLI/REPL welcome screen."""

from __future__ import annotations

from peerpedia_core.core import (
    count_articles as _count_articles,
    list_active_users as _list_active_users,
    publish_ready_articles as _publish_ready_articles,
)
from peerpedia_core.storage.db import Session
from peerpedia_core.types.status import ArticleStatus


def count_user_articles(db: Session, author_id: str) -> dict[str, int]:
    """Return ``{status: count}`` for a user's articles (draft, sedimentation, published)."""
    return {
        ArticleStatus.DRAFT: _count_articles(db, statuses={ArticleStatus.DRAFT}, author_id=author_id),
        ArticleStatus.SEDIMENTATION: _count_articles(db, statuses={ArticleStatus.SEDIMENTATION}, author_id=author_id),
        ArticleStatus.PUBLISHED: _count_articles(db, statuses={ArticleStatus.PUBLISHED}, author_id=author_id),
    }


def count_users(db: Session) -> int:
    """Return the total number of registered users."""
    return len(_list_active_users(db))


def publish_ready(db: Session) -> None:
    """Publish any articles whose sedimentation period has elapsed."""
    _publish_ready_articles(db)
