# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Rollback an article to a previous commit."""

from __future__ import annotations

from peerpedia_core.storage.db import Session
from peerpedia_core.config.params import make_peerpedia_email, params
from peerpedia_core.rules.articles import assert_can_rollback_article
from peerpedia_core.core.reconcile import reconcile_integrity
from peerpedia_core.storage.db.crud_publish import clear_publish_consents
from peerpedia_core.storage.git import (
    checkout_files, commit_article, get_head_hash, is_repo_dirty,
)
from peerpedia_core.crypto import temp_signing_key
from peerpedia_core.core.articles._helpers import reset_sink
from peerpedia_core.core.reconcile import reconcile_authors, reconcile_score
from peerpedia_core.storage.db.guards import authorize_article_action, require_signing_key
from peerpedia_core.storage.git.guards import require_article_repo
from peerpedia_core.types.status import ArticleStatus


def rollback_article(
    db: Session, article_id: str, target_hash: str, user_id: str,
    signing_key_bytes: bytes | None = None, pubkey_hex: str | None = None,
) -> dict:
    """Rollback to a previous commit by creating a new forward commit.

    Instead of ``git reset --hard`` (which rewrites history and breaks P2P
    fast-forward sync), this does ``checkout_files`` at *target_hash* and
    creates a new signed commit.  The result is a linear history that peers
    can fast-forward to without conflicts.

    Raises NotFoundError if the user, article, or repo is not found.
    Raises ValueError if signing key is missing.
    """
    # ── Authorization ──────────────────────────────────────────────────────
    reconcile_integrity(db, article_id, level="light")
    user, article, mids = authorize_article_action(db, article_id, user_id)
    assert_can_rollback_article(article, mids, user)
    rp = require_article_repo(article_id)

    # ── Checkout target ────────────────────────────────────────────────────
    checkout_files(rp, target_hash)
    if not is_repo_dirty(rp):
        return {
            "id": article.id, "title": article.title, "status": article.status,
            "commit_hash": get_head_hash(rp),
            "message": f"Already at {target_hash} (no changes needed)",
        }

    # ── Commit ─────────────────────────────────────────────────────────────
    require_signing_key(signing_key_bytes, pubkey_hex, "rollback")
    with temp_signing_key(signing_key_bytes) as key_path:
        new_hash = commit_article(
            rp, f"Rollback to {target_hash}",
            user.name, make_peerpedia_email(user_id),
            signing_key=key_path, pubkey_hex=pubkey_hex,
        )

    # ── Post-rollback effects ──────────────────────────────────────────────
    clear_publish_consents(db, article_id)
    if article.status == ArticleStatus.PUBLISHED:
        reset_sink(db, article_id, rp, params.sink.edit_article_default_days)
    reconcile_authors(db, article_id)
    reconcile_score(db, article_id)

    return {
        "id": article.id, "title": article.title, "status": article.status,
        "commit_hash": new_hash,
        "message": f"Rollback to {target_hash}",
    }
