# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Tests for ScriptMaintainer seed logic in article lifecycle operations.

Verifies the seed rules:
- create_article_with_content: all author_ids → also maintainers
- fork_article: only the forker → sole maintainer
- accept_merge: merge author → ArticleAuthor, NOT maintainer
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch

from sqlalchemy.orm import Session

from peerpedia_core.commands.articles import create_article_with_content, fork_article
from peerpedia_core.commands.merge import accept_merge
from peerpedia_core.storage.db.crud_maintainer import get_maintainer_ids, is_maintainer
from peerpedia_core.storage.db.crud_merge import create_merge_proposal
from peerpedia_core.storage.db.crud_user import get_user
from peerpedia_core.storage.db.engine import get_session
from peerpedia_core.storage.db.models import User
from peerpedia_core.storage.git_backend import DEFAULT_ARTICLES_DIR, init_article_repo, commit_article
import peerpedia_core.storage.git_backend as git_backend


def _register_user(db: Session, user_id: str, name: str = "Test Author") -> User:
    u = User(id=user_id, password_hash="$2b$12$test", name=name)
    db.add(u)
    db.flush()
    return u


# ── create_article_with_content — maintainer seed ────────────────────────


class TestCreateSeedsMaintainers:
    def test_all_authors_become_maintainers(self, db_engine):
        db = get_session(db_engine)
        _register_user(db, "alice", "Alice")
        _register_user(db, "bob", "Bob")

        result = create_article_with_content(
            db,
            title="Co-authored Paper",
            content="# Abstract\n\nJoint work.",
            author_ids=["alice", "bob"],
        )
        db.commit()

        assert is_maintainer(db, result["id"], "alice")
        assert is_maintainer(db, result["id"], "bob")
        assert get_maintainer_ids(db, result["id"]) == ["alice", "bob"]

    def test_single_author_is_sole_maintainer(self, db_engine):
        db = get_session(db_engine)
        _register_user(db, "alice", "Alice")

        result = create_article_with_content(
            db,
            title="Solo Paper",
            content="# Abstract\n\nSolo work.",
            author_ids=["alice"],
        )
        db.commit()

        assert get_maintainer_ids(db, result["id"]) == ["alice"]


# ── fork_article — maintainer seed ───────────────────────────────────────


class TestForkSeedsMaintainer:
    def test_forker_is_sole_maintainer(self, db_engine):
        db = get_session(db_engine)
        _register_user(db, "alice", "Alice")
        _register_user(db, "bob", "Bob")

        # Alice creates and publishes an article
        create_result = create_article_with_content(
            db,
            title="Original",
            content="# Original",
            author_ids=["alice"],
        )

        from peerpedia_core.commands.articles import publish_article

        publish_article(
            db,
            create_result["id"],
            "alice",
            {"originality": 4, "rigor": 3, "completeness": 4, "pedagogy": 3, "impact": 4},
        )
        db.commit()

        # Set status to published (publish_article puts it in sedimentation)
        from peerpedia_core.storage.db.crud_article import update_article_status
        update_article_status(db, create_result["id"], "published")
        db.commit()

        # Bob forks it
        fork_result = fork_article(db, create_result["id"], "bob")
        db.commit()

        # Bob is the sole maintainer of the fork
        assert is_maintainer(db, fork_result["id"], "bob")
        assert get_maintainer_ids(db, fork_result["id"]) == ["bob"]

    def test_original_authors_not_maintainers_on_fork(self, db_engine):
        db = get_session(db_engine)
        _register_user(db, "alice", "Alice")
        _register_user(db, "bob", "Bob")

        create_result = create_article_with_content(
            db,
            title="Original",
            content="# Original",
            author_ids=["alice"],
        )

        from peerpedia_core.commands.articles import publish_article

        publish_article(
            db,
            create_result["id"],
            "alice",
            {"originality": 4, "rigor": 3, "completeness": 4, "pedagogy": 3, "impact": 4},
        )
        db.commit()

        from peerpedia_core.storage.db.crud_article import update_article_status
        update_article_status(db, create_result["id"], "published")
        db.commit()

        fork_result = fork_article(db, create_result["id"], "bob")
        db.commit()

        # Alice (original author) is NOT a maintainer of Bob's fork
        assert not is_maintainer(db, fork_result["id"], "alice")


# ── accept_merge — maintainer NOT auto-seeded ────────────────────────────


class TestMergeAuthorNotMaintainer:
    def test_merge_author_not_maintainer(self, db_engine):
        """Merge author becomes ArticleAuthor but NOT ScriptMaintainer."""
        db = get_session(db_engine)
        _register_user(db, "alice", "Alice")
        _register_user(db, "bob", "Bob")

        # Alice creates and publishes an article
        create_result = create_article_with_content(
            db,
            title="Original",
            content="# Original",
            author_ids=["alice"],
        )

        from peerpedia_core.commands.articles import publish_article

        publish_article(
            db,
            create_result["id"],
            "alice",
            {"originality": 4, "rigor": 3, "completeness": 4, "pedagogy": 3, "impact": 4},
        )
        db.commit()

        from peerpedia_core.storage.db.crud_article import update_article_status
        update_article_status(db, create_result["id"], "published")
        db.commit()

        # Bob forks Alice's article and edits it
        fork_result = fork_article(db, create_result["id"], "bob")
        db.commit()

        from peerpedia_core.commands.articles import update_article_content

        update_article_content(
            db,
            fork_result["id"],
            content="# Bob's improvements",
            message="Improved the paper",
            user_id="bob",
        )
        db.commit()

        # Bob proposes merge back to Alice
        mp = create_merge_proposal(db, fork_result["id"], create_result["id"], "bob")
        db.commit()

        # Alice accepts the merge
        result = accept_merge(db, create_result["id"], mp.id, "alice")

        # Bob contributed content → ArticleAuthor, but NOT maintainer
        assert not result.get("status") == "conflict"
        assert not is_maintainer(db, create_result["id"], "bob")
