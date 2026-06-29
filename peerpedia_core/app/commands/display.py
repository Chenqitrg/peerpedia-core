# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Display helpers — thin wrappers over core for CLI rendering.

CLI display code needs author names, article paths, frontmatter, etc.
These are read-only lookups; the wrappers exist so CLI never imports
from ``core/`` directly, which architecture tests enforce.
"""

from __future__ import annotations

from pathlib import Path

from peerpedia_core.core import (
    article_source_path as _article_source_path,
    list_articles as _list_articles,
    list_author_ids as _list_author_ids,
    list_author_ids_batch as _list_author_ids_batch,
    list_users_by_ids as _list_users_by_ids,
    parse_frontmatter as _parse_frontmatter,
)
from peerpedia_core.storage.db import Session
from peerpedia_core.types import short_id


# ── Author display ────────────────────────────────────────────────────────

def resolve_author_names(db: Session, author_ids: list[str]) -> list[str]:
    """Convert author UUIDs to display names.

    UUIDs that can't be resolved are shown as 8-char prefixes.
    """
    if not author_ids:
        return []
    users = {u.id: u for u in _list_users_by_ids(db, set(author_ids))}
    return [
        users[uid].name if uid in users else short_id(uid)
        for uid in author_ids
    ]


def list_author_ids(db: Session, article_id: str) -> list[str]:
    """Return author UUIDs for *article_id*."""
    return _list_author_ids(db, article_id)


def list_author_ids_batch(db: Session, article_ids: list[str]) -> dict[str, list[str]]:
    """Return ``{article_id: [author_id, ...]}`` for a batch of articles."""
    return _list_author_ids_batch(db, article_ids)


# ── Article source ────────────────────────────────────────────────────────

def read_frontmatter(raw: str) -> dict:
    """Parse YAML frontmatter from article source text."""
    return _parse_frontmatter(raw)


def source_path(article_id: str) -> Path | None:
    """Return the file path to an article's source, or None."""
    return _article_source_path(article_id)


def list_articles(db: Session, *, search_query: str | None = None,
                  limit: int | None = None, statuses: set[str] | None = None,
                  author_ids: set[str] | None = None) -> list:
    """List article ORM objects with optional filters — for CLI display."""
    return _list_articles(db, search_query=search_query, limit=limit,
                          statuses=statuses, author_ids=author_ids)
