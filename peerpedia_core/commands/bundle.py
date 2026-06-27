# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

r"""Sync orchestration — apply incoming git bundles and reconcile DB state.

Call graph::

    apply_sync_bundle
      ├► git (merge FETCH_HEAD)
      ├► _verify_new_commits (TOFU signature check)
      ├► commands.integrity.rebuild_db_from_git
      │     ├► rebuild_article_authors
      │     ├► sync_reviews_from_worktree
      │     ├► sync_status_from_git
      │     ├► recompute_article_score
      │     └► publish_ready_articles
      └► rollback git on failure

"""

from __future__ import annotations

import logging
from pathlib import Path

from peerpedia_core.storage.db import Session

from peerpedia_core.types import short_id
from peerpedia_core.storage.git_backend import (
    get_head_or_none,
    merge_fetch_head,
    reset_to_commit,
)

from peerpedia_core.commands.guards import require_article_repo, verify_new_commits
from peerpedia_core.commands.integrity import rebuild_db_from_git


logger = logging.getLogger(__name__)


def _try_rollback(rp: Path, old_head: str | None, new_head: str) -> None:
    """Best-effort git reset after reconciliation failure."""
    if old_head is None:
        return
    try:
        reset_to_commit(rp, old_head)
    except Exception as exc:
        logger.error(
            "Failed to reset %s %s → %s after sync failure: %s",
            rp.name, short_id(new_head), short_id(old_head), exc,
        )


def apply_sync_bundle(
    db: Session, article_id: str, *, ff_only: bool = True,
) -> str:
    """Merge fetched bundle objects (``FETCH_HEAD``) and reconcile DB state."""
    rp = require_article_repo(article_id)
    old_head = get_head_or_none(rp)
    new_head = merge_fetch_head(rp, ff_only=ff_only)

    try:
        if old_head:
            verify_new_commits(db, rp, since_hash=old_head)

        rebuild_db_from_git(db, article_id)
    except Exception:
        _try_rollback(rp, old_head, new_head)
        raise

    return new_head


