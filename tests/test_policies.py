# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Tests for article permission policy functions."""

import pytest

from peerpedia_core.exceptions import ConflictError, NotAuthorizedError, NotFoundError
from peerpedia_core.policies.articles import (
    FORKABLE_STATUSES,
    PUBLIC_READABLE_STATUSES,
    assert_can_delete_article,
    assert_can_download_content,
    assert_can_edit_article,
    assert_can_extend_sink,
    assert_can_fork_article,
    assert_can_publish_article,
    assert_can_read_article,
    assert_can_rollback_article,
    assert_can_sync_article,
    get_article_or_raise,
    visible_statuses_for_user,
)
from peerpedia_core.storage.db.engine import get_session
from peerpedia_core.storage.db.models import Article, ArticleAuthor, User


def _user(**kwargs):
    """Create a User with required fields filled in."""
    defaults = {"password_hash": "", "name": "Test User", "anonymous_name": "anon", "affiliation": "Test"}
    defaults.update(kwargs)
    return User(**defaults)


class TestVisibilityRules:
    def test_public_readable_includes_sedimentation_and_published(self):
        assert PUBLIC_READABLE_STATUSES == {"sedimentation", "published"}

    def test_forkable_statuses_is_published_only(self):
        assert FORKABLE_STATUSES == {"published"}

    def test_visible_statuses_anonymous(self):
        result = visible_statuses_for_user(None)
        assert result == {"sedimentation", "published"}

    def test_visible_statuses_authenticated(self):
        u = _user(username="test")
        result = visible_statuses_for_user(u)
        assert result == {"draft", "sedimentation", "published"}


class TestGetArticleOrRaise:
    def test_returns_article_when_exists(self, db_engine):
        s = get_session(db_engine)
        a = Article(id="a-exists", status="draft", fork_count=0)
        s.add(a)
        s.commit()

        result = get_article_or_raise(s, "a-exists")
        assert result.id == "a-exists"

    def test_raises_not_found_when_missing(self, db_engine):
        import pytest

        s = get_session(db_engine)
        with pytest.raises(NotFoundError, match="Article not found"):
            get_article_or_raise(s, "nonexistent")


class TestReadPermissions:
    def test_can_read_published_article(self, db_engine):
        s = get_session(db_engine)
        a = Article(id="a-pub", status="published", fork_count=0)
        s.add(a)
        s.commit()

        result = assert_can_read_article(s, "a-pub", None)
        assert result.id == "a-pub"

    def test_can_read_own_draft(self, db_engine):
        s = get_session(db_engine)
        u = _user(id="u-draft", username="draft_user")
        s.add(u)
        a = Article(id="a-draft", status="draft", fork_count=0)
        s.add(a)
        s.flush()
        s.add(ArticleAuthor(article_id="a-draft", author_id="u-draft", position=0))
        s.commit()

        result = assert_can_read_article(s, "a-draft", u)
        assert result.id == "a-draft"

    def test_cannot_read_others_draft(self, db_engine):
        import pytest

        s = get_session(db_engine)
        u = _user(id="u-other", username="other")
        s.add(u)
        a = Article(id="a-other-draft", status="draft", fork_count=0)
        s.add(a)
        s.commit()

        with pytest.raises(NotAuthorizedError, match="Article is private"):
            assert_can_read_article(s, "a-other-draft", u)


class TestWritePermissions:
    def test_author_can_sync(self, db_engine):
        s = get_session(db_engine)
        u = _user(id="u-sync", username="sync_user")
        s.add(u)
        a = Article(id="a-sync", status="draft", fork_count=0)
        s.add(a)
        s.flush()
        s.add(ArticleAuthor(article_id="a-sync", author_id="u-sync", position=0))
        s.commit()

        result = assert_can_sync_article(s, "a-sync", u)
        assert result.id == "a-sync"

    def test_non_author_cannot_sync(self, db_engine):
        import pytest

        s = get_session(db_engine)
        u = _user(id="u-nosync", username="no_sync")
        s.add(u)
        a = Article(id="a-nosync", status="draft", fork_count=0)
        s.add(a)
        s.commit()

        with pytest.raises(NotAuthorizedError):
            assert_can_sync_article(s, "a-nosync", u)


class TestForkPermissions:
    def test_can_fork_published(self, db_engine):
        s = get_session(db_engine)
        u = _user(id="u-fork", username="fork_user")
        s.add(u)
        a = Article(id="a-fork", status="published", fork_count=0)
        s.add(a)
        s.commit()

        result = assert_can_fork_article(s, "a-fork", u)
        assert result.id == "a-fork"

    def test_cannot_fork_draft(self, db_engine):
        import pytest

        s = get_session(db_engine)
        u = _user(id="u-nofork", username="no_fork")
        s.add(u)
        a = Article(id="a-nofork", status="draft", fork_count=0)
        s.add(a)
        s.commit()

        with pytest.raises(NotAuthorizedError, match="Only published articles can be forked"):
            assert_can_fork_article(s, "a-nofork", u)

    def test_cannot_fork_twice(self, db_engine):
        import pytest

        s = get_session(db_engine)
        u = _user(id="u-dup", username="dup_fork")
        s.add(u)
        a = Article(id="a-dup-fork", status="published", fork_count=0)
        s.add(a)
        s.flush()
        # Simulate an existing fork by the same user
        fork = Article(
            id="fork-existing",
            status="draft",
            fork_count=0,
            forked_from="a-dup-fork",
        )
        s.add(fork)
        s.flush()
        s.add(ArticleAuthor(article_id="fork-existing", author_id="u-dup", position=0))
        s.commit()

        with pytest.raises(ConflictError, match="Already forked"):
            assert_can_fork_article(s, "a-dup-fork", u)


# ═══════════════════════════════════════════════════════════════════════════════
# Download permissions
# ═══════════════════════════════════════════════════════════════════════════════


class TestDownloadPermissions:
    def test_anyone_can_download_published(self, db_engine):
        s = get_session(db_engine)
        a = Article(id="a-dl-pub", status="published", fork_count=0)
        s.add(a)
        s.commit()

        result = assert_can_download_content(s, "a-dl-pub", None)
        assert result.id == "a-dl-pub"

    def test_author_can_download_draft(self, db_engine):
        s = get_session(db_engine)
        u = _user(id="u-dl-author", username="dl_author")
        s.add(u)
        a = Article(id="a-dl-draft", status="draft", fork_count=0)
        s.add(a)
        s.flush()
        s.add(ArticleAuthor(article_id="a-dl-draft", author_id="u-dl-author", position=0))
        s.commit()

        result = assert_can_download_content(s, "a-dl-draft", u)
        assert result.id == "a-dl-draft"

    def test_non_author_cannot_download_draft(self, db_engine):
        s = get_session(db_engine)
        u = _user(id="u-dl-nonauth", username="dl_nonauth")
        s.add(u)
        a = Article(id="a-dl-draft2", status="draft", fork_count=0)
        s.add(a)
        s.commit()

        with pytest.raises(NotAuthorizedError, match="Content download not available"):
            assert_can_download_content(s, "a-dl-draft2", u)

    def test_raises_not_found_for_missing(self, db_engine):
        s = get_session(db_engine)
        with pytest.raises(NotFoundError, match="Article not found"):
            assert_can_download_content(s, "nonexistent", None)


# ═══════════════════════════════════════════════════════════════════════════════
# Anonymous read edge case
# ═══════════════════════════════════════════════════════════════════════════════


class TestAnonymousRead:
    def test_anonymous_cannot_read_draft(self, db_engine):
        s = get_session(db_engine)
        a = Article(id="a-anon-draft", status="draft", fork_count=0)
        s.add(a)
        s.commit()

        with pytest.raises(NotAuthorizedError, match="Article is private"):
            assert_can_read_article(s, "a-anon-draft", None)

    def test_anonymous_can_read_published(self, db_engine):
        s = get_session(db_engine)
        a = Article(id="a-anon-pub", status="published", fork_count=0)
        s.add(a)
        s.commit()

        result = assert_can_read_article(s, "a-anon-pub", None)
        assert result.id == "a-anon-pub"

    def test_anonymous_can_read_sedimentation(self, db_engine):
        s = get_session(db_engine)
        a = Article(id="a-anon-sed", status="sedimentation", fork_count=0)
        s.add(a)
        s.commit()

        result = assert_can_read_article(s, "a-anon-sed", None)
        assert result.id == "a-anon-sed"


# ═══════════════════════════════════════════════════════════════════════════════
# Author-only wrappers — parametrized smoke test
# ═══════════════════════════════════════════════════════════════════════════════


class TestAllAuthorOnlyWrappers:
    """Every assert_can_{edit,delete,rollback,publish,extend_sink}
    delegates to the same _assert_is_author helper.  A parametrized
    smoke test ensures each wrapper dispatches correctly.
    """

    @pytest.mark.parametrize(
        "func,action",
        [
            (assert_can_edit_article, "edit"),
            (assert_can_delete_article, "delete"),
            (assert_can_rollback_article, "rollback"),
            (assert_can_publish_article, "publish"),
            (assert_can_extend_sink, "extend sink"),
        ],
    )
    def test_non_author_raises(self, db_engine, func, action):
        s = get_session(db_engine)
        u = _user(id=f"u-{action}", username=f"user_{action}")
        s.add(u)
        a = Article(id=f"a-{action}", status="draft", fork_count=0)
        s.add(a)
        s.commit()

        with pytest.raises(NotAuthorizedError, match=f"Only authors can {action}"):
            func(s, f"a-{action}", u)

    @pytest.mark.parametrize(
        "func",
        [
            assert_can_edit_article,
            assert_can_delete_article,
            assert_can_rollback_article,
            assert_can_publish_article,
        ],
    )
    def test_author_succeeds(self, db_engine, func):
        s = get_session(db_engine)
        u = _user(id="u-auth-all", username="auth_all")
        s.add(u)
        a = Article(id="a-auth-all", status="draft", fork_count=0)
        s.add(a)
        s.flush()
        s.add(ArticleAuthor(article_id="a-auth-all", author_id="u-auth-all", position=0))
        s.commit()

        result = func(s, "a-auth-all", u)
        assert result.id == "a-auth-all"

    def test_author_can_extend_sink_on_sedimentation(self, db_engine):
        """extend-sink requires sedimentation status (the pool period)."""
        s = get_session(db_engine)
        u = _user(id="u-ext-sink", username="ext_sink")
        s.add(u)
        a = Article(id="a-ext-sink", status="sedimentation", fork_count=0)
        s.add(a)
        s.flush()
        s.add(ArticleAuthor(article_id="a-ext-sink", author_id="u-ext-sink", position=0))
        s.commit()

        result = assert_can_extend_sink(s, "a-ext-sink", u)
        assert result.id == "a-ext-sink"
