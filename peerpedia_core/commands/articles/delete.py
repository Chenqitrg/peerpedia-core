# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Delete an article from DB and git."""

from __future__ import annotations

from peerpedia_core.storage.db import Session
from peerpedia_core.exceptions import NotFoundError
from peerpedia_core.policies.articles import assert_can_delete_article
from peerpedia_core.storage.db.crud_article import (
    delete_article as _delete,
    get_article as _get_article,
)
from peerpedia_core.storage.db.crud_maintainer import get_maintainer_ids
from peerpedia_core.storage.db.crud_user import get_user
from peerpedia_core.storage.git_backend import DEFAULT_ARTICLES_DIR, delete_article_repo
from peerpedia_core.commands.integrity import assert_article_integrity


def delete_article(db: Session, article_id: str, *, user_id: str) -> None:
    """Delete an article from DB and its git repo.

    Only callable from ``draft`` status by an author.  Sedimentation and
    published articles cannot be deleted.
    """
    assert_article_integrity(db, article_id, level="light")

    user = get_user(db, user_id)
    if user is None:
        raise NotFoundError("User not found")
    article = _get_article(db, article_id)
    if article is None:
        raise NotFoundError("Article not found")
    mids = get_maintainer_ids(db, article_id)
    assert_can_delete_article(article, mids, user)

    _delete(db, article_id)
    # TODO(fork-count-decrement): decrement fork_count on the original article
    # when a fork is deleted.  Currently only increment_fork_count exists
    # (called at fork creation); deletes never decrement.  Over time fork_count
    # becomes inflated — it counts "forks ever created" not "active forks".
    delete_article_repo(DEFAULT_ARTICLES_DIR / article_id)
