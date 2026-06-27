# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Article integrity verification — commit signatures and DB/git consistency."""

from __future__ import annotations

from pathlib import Path

from peerpedia_core.exceptions import NotFoundError
from peerpedia_core.storage.db import Session
from peerpedia_core.storage.db.crud_article import get_author_ids
from peerpedia_core.storage.git import (
    get_commit_authors, get_commit_history, read_status_from_git,
    require_commit_pubkey_signature,
)
from peerpedia_core.types.status import is_platform_commit
from peerpedia_core.commands.guards import (
    require_article, require_article_repo, require_integrity_level,
)


def assert_article_integrity(db: Session, article_id: str, *, level: str = "light") -> None:
    """Verify article integrity at the specified level.

    ``level="light"`` — verify the latest human-authored commit's signature.
    ``level="full"`` — light + DB cross-validation, auto-repair if inconsistent.
    """
    try:
        rp = require_article_repo(article_id)
        require_article(db, article_id)
    except NotFoundError:
        return

    require_integrity_level(level)
    if level == "light":
        _verify_light(rp)
    else:
        _verify_light(rp)
        _verify_full(db, article_id, rp)


# ── Helpers ────────────────────────────────────────────────────────────────


def _verify_light(repo_path: Path) -> None:
    """Verify the latest human-authored commit's signature."""
    commits = list(get_commit_history(repo_path, max_count=1))
    if not commits:
        return
    commit = commits[0]
    if is_platform_commit(commit["author_email"]):
        return
    require_commit_pubkey_signature(
        repo_path, commit["hash"], commit["message"], commit["author_email"],
    )


def _verify_full(db: Session, article_id: str, repo_path: Path) -> None:
    """DB cross-validation: rebuild DB cache from git SOT if inconsistent."""
    from peerpedia_core.commands.reconcile import reconcile_all, reconcile_authors

    article = require_article(db, article_id)

    expected_status = read_status_from_git(repo_path)
    if expected_status is not None and article.status != expected_status:
        reconcile_all(db, article_id)
        return

    db_authors = set(get_author_ids(db, article_id))
    git_authors = get_commit_authors(repo_path)
    if db_authors != git_authors:
        reconcile_authors(db, article_id)
