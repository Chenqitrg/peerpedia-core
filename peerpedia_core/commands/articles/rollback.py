# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Rollback an article to a previous commit."""

from __future__ import annotations

from peerpedia_core.storage.db import Session
from peerpedia_core.config.params import params
from peerpedia_core.exceptions import NotFoundError
from peerpedia_core.policies.articles import assert_can_rollback_article, assert_not_folded
from peerpedia_core.commands.integrity import assert_article_integrity
from peerpedia_core.storage.db.crud_article import (
    get_article as _get_article,
    set_sink_start,
)
from peerpedia_core.storage.db.crud_maintainer import get_maintainer_ids
from peerpedia_core.storage.db.crud_user import get_user
from peerpedia_core.storage.git_backend import (
    DEFAULT_ARTICLES_DIR,
    checkout_files,
    commit_article,
    commit_status_marker,
    get_head_hash,
    is_repo_dirty,
)
from peerpedia_core.crypto import write_key_to_tempfile
from peerpedia_core.commands.articles._helpers import rebuild_article_authors
from peerpedia_core.commands.workflow import recompute_article_score


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
    assert_article_integrity(db, article_id, level="light")

    user = get_user(db, user_id)
    if user is None:
        raise NotFoundError("User not found")
    article = _get_article(db, article_id)
    if article is None:
        raise NotFoundError("Article not found")
    mids = get_maintainer_ids(db, article_id)
    assert_can_rollback_article(article, mids, user)
    assert_not_folded(article, threshold=params.reputation.fold_score_threshold)
    old_status = article.status
    rp = DEFAULT_ARTICLES_DIR / article_id
    if not (rp / ".git").is_dir():
        raise NotFoundError("Article repo not found")

    checkout_files(rp, target_hash)

    if not is_repo_dirty(rp):
        return {"commit_hash": get_head_hash(rp),
                "message": f"Already at {target_hash[:8]} (no changes needed)"}

    if signing_key_bytes is None or not pubkey_hex:
        raise ValueError("signing_key_bytes and pubkey_hex are required for rollback")

    key_path = write_key_to_tempfile(signing_key_bytes)
    try:
        new_hash = commit_article(
            rp,
            f"Rollback to {target_hash[:8]}",
            user.name, f"{user_id}@peerpedia",
            signing_key=key_path, pubkey_hex=pubkey_hex,
        )
    finally:
        key_path.unlink(missing_ok=True)

    # G3: write a platform [status] marker so integrity repair can detect
    # divergence if the process dies before set_sink_start.
    if old_status == "published":
        commit_status_marker(rp, "sedimentation")
        set_sink_start(db, article_id, params.sink.edit_article_default_days)

    rebuild_article_authors(db, article_id)
    recompute_article_score(db, article_id)

    msg = f"Rollback to {target_hash[:8]}"
    return {"id": article.id, "title": article.title, "status": article.status,
            "commit_hash": new_hash, "message": msg}
