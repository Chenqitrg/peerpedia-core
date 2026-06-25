# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Shared helpers for article sub-modules."""

from __future__ import annotations

from peerpedia_core.storage.db import Session
from peerpedia_core.exceptions import NotFoundError
from peerpedia_core.storage.db.crud_article import (
    add_article_authors,
    get_article as _get_article,
    get_author_ids as _get_author_ids,
)
from peerpedia_core.storage.git_backend import DEFAULT_ARTICLES_DIR, get_commit_authors, get_head_hash


def rebuild_article_authors(db: Session, article_id: str, since_hash: str | None = None) -> None:
    """Read author IDs from git commits and merge them into DB.

    Sets ``last_author_rebuild_hash`` to the current HEAD so the next
    rebuild only scans new commits (*since_hash*).

    Raises NotFoundError if the article does not exist.
    """
    article = _get_article(db, article_id)
    if article is None:
        raise NotFoundError(f"Article not found: {article_id}")

    rp = DEFAULT_ARTICLES_DIR / article_id
    head_hash = get_head_hash(rp)
    new_ids = get_commit_authors(rp, since_hash=since_hash)

    existing = set(_get_author_ids(db, article_id))
    new_only = [a for a in new_ids if a not in existing]
    if new_only:
        add_article_authors(db, article_id, new_only)

    article.last_author_rebuild_hash = head_hash
