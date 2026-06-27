# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Shared helpers for article sub-modules."""

from __future__ import annotations

from pathlib import Path

from peerpedia_core.storage.db import Session
from peerpedia_core.storage.db.crud_article import (
    add_article_authors,
    get_author_ids as _get_author_ids,
    set_sink_start,
)
from peerpedia_core.config.paths import article_repo_path
from peerpedia_core.storage.git_backend import (
    commit_status_marker, get_commit_authors, get_head_hash,
)
from peerpedia_core.commands.guards import require_article


def reset_sink(db: Session, article_id: str, rp: Path, extra_days: int) -> None:
    """Write status marker to git and reset sink timer.

    Eliminates the repeated ``commit_status_marker + set_sink_start`` pair.
    """
    commit_status_marker(rp, "sedimentation")
    set_sink_start(db, article_id, extra_days)


def rebuild_article_authors(db: Session, article_id: str, since_hash: str | None = None) -> None:
    """Read author IDs from new git commits and merge them into DB.

    This is **incremental** — only adds new authors discovered in commits
    since ``since_hash`` (or ``last_author_rebuild_hash``).  It never removes
    authors already in the DB, even if they are no longer in git history.
    For a full replacement use ``crud_article.set_article_authors`` directly.

    Sets ``last_author_rebuild_hash`` to the current HEAD so the next
    rebuild only scans new commits.

    Raises NotFoundError if the article does not exist.
    """
    article = require_article(db, article_id)

    rp = article_repo_path(article_id)
    head_hash = get_head_hash(rp)
    new_ids = get_commit_authors(rp, since_hash=since_hash)

    existing = set(_get_author_ids(db, article_id))
    new_only = [a for a in new_ids if a not in existing]
    if new_only:
        add_article_authors(db, article_id, new_only)

    article.last_author_rebuild_hash = head_hash
