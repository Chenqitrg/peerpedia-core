# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Article orchestration commands.

Each function combines core primitives (CRUD, git, policies, workflow) into
a single business operation.  Callers (CLI, backend routes) own the transaction
boundary — these functions do NOT call ``db.commit()``.
"""

from __future__ import annotations

import shutil
import uuid
from pathlib import Path

import git as gitmod
from sqlalchemy.orm import Session

from peerpedia_core.config.params import params

from peerpedia_core.exceptions import NotFoundError
from peerpedia_core.policies.articles import (
    assert_can_fork_article,
    assert_can_rollback_article,
)
from peerpedia_core.storage.db.crud_article import (
    create_article,
    get_article,
    get_author_ids,
    get_authors_from_git,
    increment_fork_count,
    rebuild_article_authors,
    set_sink_start,
)
from peerpedia_core.storage.db.crud_review import create_review
from peerpedia_core.storage.db.crud_user import get_user
from peerpedia_core.storage.git_backend import (
    DEFAULT_ARTICLES_DIR,
    commit_article,
    init_article_repo,
)
from peerpedia_core.workflow.scoring import compute_article_score_for_commit


# ═══════════════════════════════════════════════════════════════════════════════
# Fork
# ═══════════════════════════════════════════════════════════════════════════════


def fork_article(db: Session, article_id: str, user_id: str) -> dict:
    """Fork an article: clone its git repo and create a new Article record.

    Returns:
        {"id": <fork_id>, "forked_from": <original_id>, "status": "draft"}

    Raises:
        NotFoundError: user not found in DB
        NotAuthorizedError: article not forkable (policy)
        ConflictError: user already forked this article
    """
    user = get_user(db, user_id)
    if user is None:
        raise NotFoundError("User not found")

    original = assert_can_fork_article(db, article_id, user)

    fork_id = str(uuid.uuid4())
    src = DEFAULT_ARTICLES_DIR / article_id
    dst = DEFAULT_ARTICLES_DIR / fork_id

    if (src / ".git").is_dir():
        shutil.copytree(src, dst, symlinks=True)
    else:
        init_article_repo(fork_id)

    fork = create_article(
        db,
        id=fork_id,
        title=original.title,
        abstract=original.abstract,
        keywords=original.keywords,
        categories=original.categories,
        authors=[user_id],
        status="draft",
        forked_from=article_id,
    )
    increment_fork_count(db, article_id)

    if (dst / ".git").is_dir():
        git_authors = get_authors_from_git(dst, db)
        git_authors.add(user_id)
        rebuild_article_authors(db, fork_id, git_authors)

    return {"id": fork.id, "forked_from": article_id, "status": "draft"}


# ═══════════════════════════════════════════════════════════════════════════════
# Rollback
# ═══════════════════════════════════════════════════════════════════════════════


def rollback_article(db: Session, article_id: str, target_hash: str, user_id: str) -> dict:
    """Rollback to a previous commit (creates a new revert commit, not force-push).

    Returns:
        {"commit_hash": <new_hash>, "message": "Rollback to ..."}

    Raises:
        NotAuthorizedError: user lacks rollback permission
        NotFoundError: article repo not found
    """
    user = get_user(db, user_id)
    if user is None:
        raise NotFoundError("User not found")

    article = assert_can_rollback_article(db, article_id, user)
    rp = DEFAULT_ARTICLES_DIR / article_id
    if not (rp / ".git").is_dir():
        raise NotFoundError("Article repo not found")

    repo = gitmod.Repo(rp)
    repo.commit(target_hash)
    repo.git.checkout(target_hash, "--", ".")

    new_hash = commit_article(
        rp, f"Rollback to {target_hash[:8]}", "System", "system@peerpedia",
    )
    set_sink_start(db, article_id, params.sink.edit_article_default_days)

    author_ids = get_author_ids(db, article_id)
    create_review(
        db,
        article_id=article_id,
        commit_hash=new_hash,
        reviewer_id=author_ids[0] if author_ids else "system",
        scope="pool",
        scores={"originality": 0, "rigor": 0, "completeness": 0, "pedagogy": 0, "impact": 0},
    )
    score = compute_article_score_for_commit(db, article_id, new_hash)
    if score is not None:
        article.score = score

    return {"commit_hash": new_hash, "message": f"Rollback to {target_hash[:8]}"}
