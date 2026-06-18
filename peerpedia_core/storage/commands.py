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

from sqlalchemy.orm import Session

from peerpedia_core.exceptions import NotFoundError
from peerpedia_core.policies.articles import assert_can_fork_article
from peerpedia_core.storage.db.crud_article import (
    create_article,
    get_article,
    get_authors_from_git,
    increment_fork_count,
    rebuild_article_authors,
)
from peerpedia_core.storage.db.crud_user import get_user
from peerpedia_core.storage.git_backend import DEFAULT_ARTICLES_DIR, init_article_repo


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
