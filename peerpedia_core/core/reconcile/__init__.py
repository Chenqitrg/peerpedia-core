# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Reconcile DB state — from git source-of-truth and from pure computation.

Orchestrators that call individual git→DB and compute→DB reconcilers.
"""

from __future__ import annotations

import logging

from peerpedia_core.storage.db import Session
from peerpedia_core.exceptions import BadRequestError
from peerpedia_core.storage.db.crud_article import update_witnessed_at
from peerpedia_core.storage.git import (
    get_head_or_none, merge_fetch_head, rollback_to,
)
from peerpedia_core.core.guards import require_article_repo, verify_new_commits
from peerpedia_core.core.guards import assert_article_integrity
from peerpedia_core.core.articles.sink import publish_ready_articles
from peerpedia_core.core.reconcile.mirror import (
    reconcile_authors, reconcile_reviews, reconcile_status,
)
from peerpedia_core.core.reconcile.score import (
    reconcile_all_reputations, reconcile_reputation, reconcile_score,
)

logger = logging.getLogger(__name__)


# ── Full rebuild ───────────────────────────────────────────────────────────


def reconcile_all(db: Session, article_id: str) -> None:
    """Rebuild DB caches (authors, reviews, status, score) from git SOT."""
    update_witnessed_at(db, article_id)
    reconcile_authors(db, article_id)
    reconcile_reviews(db, article_id)
    reconcile_status(db, article_id)
    assert_article_integrity(db, article_id, level="full")
    reconcile_score(db, article_id)
    publish_ready_articles(db)


def reconcile_after_sync(
    db: Session, article_id: str, *, ff_only: bool = True,
) -> str:
    """Merge FETCH_HEAD, verify new commits, rebuild DB. Returns new HEAD."""
    rp = require_article_repo(article_id)
    old_head = get_head_or_none(rp)
    new_head = merge_fetch_head(rp, ff_only=ff_only)

    try:
        if old_head:
            verify_new_commits(db, rp, since_hash=old_head)
        reconcile_all(db, article_id)
    except Exception:
        rollback_to(rp, old_head, new_head)
        raise

    return new_head
