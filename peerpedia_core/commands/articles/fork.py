# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Fork an article — clone its git repo into a new draft."""

from __future__ import annotations

import uuid

from peerpedia_core.storage.db import Session
from peerpedia_core.config.params import params
from peerpedia_core.policies.articles import assert_can_fork_article, assert_not_folded
from peerpedia_core.commands.integrity import assert_article_integrity
from peerpedia_core.storage.db.crud_article import (
    create_article,
    get_article_by_fork_and_author,
    increment_fork_count,
)
from peerpedia_core.storage.db.crud_maintainer import add_maintainer, get_maintainer_ids
from peerpedia_core.storage.git_backend import DEFAULT_ARTICLES_DIR, clone_article_repo, get_commit_authors
from peerpedia_core.commands.articles._helpers import require_article, require_user


def fork_article(db: Session, article_id: str, user_id: str) -> dict:
    """Fork an article: clone its git repo and create a new Article record.

    Returns:
        {"id": <fork_id>, "forked_from": <original_id>, "status": "draft"}

    Raises:
        NotFoundError: user not found in DB
        NotAuthorizedError: article not forkable (policy)
        ConflictError: user already forked this article
    """
    assert_article_integrity(db, article_id, level="light")

    user = require_user(db, user_id)
    original = require_article(db, article_id)
    maintainer_ids = get_maintainer_ids(db, article_id)
    existing_fork = get_article_by_fork_and_author(db, forked_from=article_id, author_id=user.id)
    assert_not_folded(original, threshold=params.reputation.fold_score_threshold)
    assert_can_fork_article(original, existing_fork, user=user, maintainer_ids=maintainer_ids)

    fork_id = str(uuid.uuid4())
    src = DEFAULT_ARTICLES_DIR / article_id
    dst = DEFAULT_ARTICLES_DIR / fork_id

    clone_article_repo(src, dst)

    git_authors = get_commit_authors(dst) | {user_id}

    fork = create_article(
        db, id=fork_id, title=original.title, abstract=original.abstract,
        keywords=original.keywords, categories=original.categories,
        authors=sorted(git_authors), status="draft", forked_from=article_id,
    )
    add_maintainer(db, fork_id, user_id)
    increment_fork_count(db, article_id)

    return {"id": fork.id, "forked_from": article_id, "status": "draft"}
