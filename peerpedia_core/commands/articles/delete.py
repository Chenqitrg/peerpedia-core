# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Delete an article from DB and git."""

from __future__ import annotations

from peerpedia_core.storage.db import Session
from peerpedia_core.policies.articles import assert_can_delete_article
from peerpedia_core.storage.db.crud_article import (
    decrement_fork_count,
    delete_article as _delete,
)
from peerpedia_core.storage.db.crud_maintainer import get_maintainer_ids
from peerpedia_core.config.paths import article_repo_path
from peerpedia_core.storage.git_backend import delete_article_repo
from peerpedia_core.commands.articles._helpers import require_article, require_user
from peerpedia_core.commands.integrity import assert_article_integrity


def delete_article(db: Session, article_id: str, *, user_id: str) -> None:
    """Delete an article from DB and its git repo.

    Only callable from ``draft`` status by an author.  Sedimentation and
    published articles cannot be deleted.

    Raises NotFoundError if the user or article is not found.
    """
    assert_article_integrity(db, article_id, level="light")

    user = require_user(db, user_id)
    article = require_article(db, article_id)
    mids = get_maintainer_ids(db, article_id)
    assert_can_delete_article(article, mids, user)

    _delete(db, article_id)

    if article.forked_from:
        decrement_fork_count(db, article.forked_from)

    delete_article_repo(article_repo_path(article_id))
