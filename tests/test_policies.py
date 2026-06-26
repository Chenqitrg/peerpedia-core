# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Tests for article permission policy functions.

All policy functions are now pure — they take pre-fetched data.
Tests create model objects directly (no session needed for policy calls).
"""

import uuid

import pytest

from peerpedia_core.exceptions import ConflictError, NotAuthorizedError
from peerpedia_core.policies.articles import (
    FORKABLE_STATUSES,
    PUBLIC_READABLE_STATUSES,
    assert_can_delete_article,
    assert_can_access_content,
    assert_can_edit_article,
    assert_can_extend_sink,
    assert_can_fork_article,
    assert_can_publish_article,
    assert_can_read_article,
    assert_can_rollback_article,
    assert_can_sync_article,
    visible_statuses_for_user,
)
from peerpedia_core.storage.db.models import Article, User


def _article(**kwargs):
    defaults = {"id": str(uuid.uuid4()), "title": "", "status": "draft", "fork_count": 0}
    defaults.update(kwargs)
    return Article(**defaults)


def _user(**kwargs):
    defaults = {"id": str(uuid.uuid4()), "public_key": "0000000000000000000000000000000000000000000000000000000000000000", "name": "Test User", "affiliation": "Test"}
    defaults.update(kwargs)
    return User(**defaults)


# ═══════════════════════════════════════════════════════════════════════════════
# Visibility rules
# ═══════════════════════════════════════════════════════════════════════════════


class TestVisibilityRules:
    def test_public_readable_includes_sedimentation_and_published(self):
        assert PUBLIC_READABLE_STATUSES == {"sedimentation", "published", "rejected"}

    def test_forkable_statuses_includes_draft_published_and_rejected(self):
        assert FORKABLE_STATUSES == {"draft", "published", "rejected"}

    def test_visible_statuses_anonymous(self):
        result = visible_statuses_for_user(None)
        assert result == {"sedimentation", "published", "rejected"}

    def test_visible_statuses_authenticated(self):
        u = _user()
        result = visible_statuses_for_user(u)
        assert result == {"draft", "sedimentation", "published", "rejected"}


# ═══════════════════════════════════════════════════════════════════════════════
# Read permissions
# ═══════════════════════════════════════════════════════════════════════════════


class TestReadPermissions:
    def test_can_read_published_article(self):
        a = _article(id="a-pub", status="published")
        result = assert_can_read_article(a, [], None)
        assert result.id == "a-pub"

    def test_can_read_own_draft(self):
        u = _user(id="u-draft")
        a = _article(id="a-draft", status="draft")
        result = assert_can_read_article(a, ["u-draft"], u)
        assert result.id == "a-draft"

    def test_cannot_read_others_draft(self):
        u = _user(id="u-other")
        a = _article(id="a-other-draft", status="draft")
        with pytest.raises(NotAuthorizedError, match="Article is private"):
            assert_can_read_article(a, [], u)


# ═══════════════════════════════════════════════════════════════════════════════
# Write permissions — maintainer-gated
# ═══════════════════════════════════════════════════════════════════════════════


class TestWritePermissions:
    def test_maintainer_can_sync(self):
        u = _user(id="u-sync")
        a = _article(id="a-sync", status="draft")
        result = assert_can_sync_article(a, ["u-sync"], u)
        assert result.id == "a-sync"

    def test_non_maintainer_cannot_sync(self):
        u = _user(id="u-nosync")
        a = _article(id="a-nosync", status="draft")
        with pytest.raises(NotAuthorizedError, match="is not a maintainer"):
            assert_can_sync_article(a, [], u)

    def test_can_edit_sedimentation_article(self):
        """P0-3: Sedimentation articles are now editable by maintainers."""
        u = _user(id="u-edit-sed")
        a = _article(id="a-edit-sed", status="sedimentation")
        result = assert_can_edit_article(a, ["u-edit-sed"], u)
        assert result == a


# ═══════════════════════════════════════════════════════════════════════════════
# Fork permissions
# ═══════════════════════════════════════════════════════════════════════════════


class TestForkPermissions:
    def test_can_fork_published(self):
        """Anyone can fork a published article."""
        a = _article(id="a-fork", status="published")
        result = assert_can_fork_article(a, None)
        assert result.id == "a-fork"

    def test_maintainer_can_fork_draft(self):
        """A maintainer can fork their own draft article."""
        u = _user(id="u-maint")
        a = _article(id="a-draft", status="draft")
        result = assert_can_fork_article(a, None, user=u, maintainer_ids=[u.id])
        assert result.id == "a-draft"

    def test_non_maintainer_cannot_fork_draft(self):
        """A non-maintainer cannot fork someone else's draft."""
        u = _user(id="u-stranger")
        a = _article(id="a-draft", status="draft")
        with pytest.raises(NotAuthorizedError, match="Only maintainers can fork a draft"):
            assert_can_fork_article(a, None, user=u, maintainer_ids=["someone-else"])

    def test_cannot_fork_sedimentation(self):
        """Articles in sedimentation cannot be forked by anyone."""
        a = _article(id="a-sed", status="sedimentation")
        with pytest.raises(NotAuthorizedError, match="cannot be forked"):
            assert_can_fork_article(a, None)

    def test_cannot_fork_twice(self):
        u = _user(id="u-dup")
        a = _article(id="a-dup-fork", status="published")
        existing_fork = _article(id="fork-existing", status="draft", forked_from="a-dup-fork")
        with pytest.raises(ConflictError, match="Already forked"):
            assert_can_fork_article(a, existing_fork, user=u, maintainer_ids=[u.id])


# ═══════════════════════════════════════════════════════════════════════════════
# Download permissions
# ═══════════════════════════════════════════════════════════════════════════════


class TestDownloadPermissions:
    def test_anyone_can_download_published(self):
        a = _article(id="a-dl-pub", status="published")
        result = assert_can_access_content(a, [], None)
        assert result.id == "a-dl-pub"

    def test_author_can_download_draft(self):
        u = _user(id="u-dl-author")
        a = _article(id="a-dl-draft", status="draft")
        result = assert_can_access_content(a, ["u-dl-author"], u)
        assert result.id == "a-dl-draft"

    def test_non_author_cannot_download_draft(self):
        u = _user(id="u-dl-nonauth")
        a = _article(id="a-dl-draft2", status="draft")
        with pytest.raises(NotAuthorizedError, match="Content download not available"):
            assert_can_access_content(a, [], u)


# ═══════════════════════════════════════════════════════════════════════════════
# Anonymous read
# ═══════════════════════════════════════════════════════════════════════════════


class TestAnonymousRead:
    def test_anonymous_cannot_read_draft(self):
        a = _article(id="a-anon-draft", status="draft")
        with pytest.raises(NotAuthorizedError, match="Article is private"):
            assert_can_read_article(a, [], None)

    def test_anonymous_can_read_published(self):
        a = _article(id="a-anon-pub", status="published")
        result = assert_can_read_article(a, [], None)
        assert result.id == "a-anon-pub"

    def test_anonymous_can_read_sedimentation(self):
        a = _article(id="a-anon-sed", status="sedimentation")
        result = assert_can_read_article(a, [], None)
        assert result.id == "a-anon-sed"


# ═══════════════════════════════════════════════════════════════════════════════
# Maintainer-gated — parametrized smoke test
# ═══════════════════════════════════════════════════════════════════════════════


class TestAllMaintainerWrappers:
    """Every assert_can_{edit,delete,rollback,publish,extend_sink}
    delegates to the same _assert_maintainer helper.  A parametrized
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
    def test_non_maintainer_raises(self, func, action):
        u = _user(id=f"u-{action}")
        a = _article(id=f"a-{action}", status="draft")
        with pytest.raises(NotAuthorizedError, match="is not a maintainer"):
            func(a, [], u)

    @pytest.mark.parametrize(
        "func",
        [
            assert_can_edit_article,
            assert_can_delete_article,
            assert_can_rollback_article,
            assert_can_publish_article,
        ],
    )
    def test_maintainer_succeeds(self, func):
        u = _user(id="u-auth-all")
        a = _article(id="a-auth-all", status="draft")
        result = func(a, ["u-auth-all"], u)
        assert result.id == "a-auth-all"

    def test_maintainer_can_extend_sink_on_sedimentation(self):
        """extend-sink requires sedimentation status (the pool period)."""
        u = _user(id="u-ext-sink")
        a = _article(id="a-ext-sink", status="sedimentation")
        result = assert_can_extend_sink(a, ["u-ext-sink"], u)
        assert result.id == "a-ext-sink"

    def test_delete_only_allows_draft(self):
        """Delete is only allowed in draft status."""
        u = _user(id="u-del-pub")
        a = _article(id="a-del-pub", status="published")
        with pytest.raises(NotAuthorizedError, match="Cannot delete"):
            assert_can_delete_article(a, ["u-del-pub"], u)
