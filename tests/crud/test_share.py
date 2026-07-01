# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Tests for ShareStorage and AliasStorage CRUD."""

import pytest

from peerpedia_core.storage.db.engine import get_session
from peerpedia_core.storage.db.models import ArticleMetaStorage, UserStorage


@pytest.fixture
def db(engine):
    session = get_session(engine)
    yield session
    session.rollback()
    session.close()


def _make_user(db, uid, name="Test"):
    u = UserStorage(id=uid, name=name)
    db.add(u)
    db.flush()
    return u


def _make_article(db, aid, title="Test"):
    a = ArticleMetaStorage(id=aid, title=title, status="draft")
    db.add(a)
    db.flush()
    return a


class TestShareCrud:
    def test_add_share(self, db):
        from peerpedia_core.storage.db.crud_share import add_share, is_shared, get_shares_for_user

        _make_user(db, "u1")
        _make_article(db, "a1")

        s = add_share(db, "u1", "a1", comment="Check this out")
        assert s.sharer_id == "u1"
        assert s.article_id == "a1"
        assert s.comment == "Check this out"
        assert is_shared(db, "u1", "a1")

        shares = get_shares_for_user(db, "u1")
        assert len(shares) == 1

    def test_add_share_with_recipient(self, db):
        from peerpedia_core.storage.db.crud_share import add_share

        _make_user(db, "u1")
        _make_user(db, "u2")
        _make_article(db, "a1")

        s = add_share(db, "u1", "a1", recipient_id="u2")
        assert s.recipient_id == "u2"

    def test_duplicate_share_updates_comment(self, db):
        from peerpedia_core.storage.db.crud_share import add_share

        _make_user(db, "u1")
        _make_article(db, "a1")

        add_share(db, "u1", "a1", comment="First")
        s = add_share(db, "u1", "a1", comment="Updated")
        assert s.comment == "Updated"

    def test_remove_share(self, db):
        from peerpedia_core.storage.db.crud_share import add_share, remove_share, is_shared

        _make_user(db, "u1")
        _make_article(db, "a1")

        add_share(db, "u1", "a1")
        assert is_shared(db, "u1", "a1")
        remove_share(db, "u1", "a1")
        assert not is_shared(db, "u1", "a1")

    def test_remove_nonexistent_noop(self, db):
        from peerpedia_core.storage.db.crud_share import remove_share

        _make_user(db, "u1")
        _make_article(db, "a1")
        remove_share(db, "u1", "a1")  # should not raise

    def test_get_shares_for_user_pagination(self, db):
        from peerpedia_core.storage.db.crud_share import add_share, get_shares_for_user

        _make_user(db, "u1")
        for i in range(3):
            _make_article(db, f"a{i}")
            add_share(db, "u1", f"a{i}")

        page = get_shares_for_user(db, "u1", limit=2, offset=0)
        assert len(page) == 2
        page2 = get_shares_for_user(db, "u1", limit=2, offset=2)
        assert len(page2) == 1

    def test_get_shares_by_followed(self, db):
        from peerpedia_core.storage.db.crud_share import add_share, get_shares_by_followed
        from peerpedia_core.storage.db.crud_follow import follow_user

        _make_user(db, "viewer")
        _make_user(db, "followed1", "Alice")
        _make_user(db, "followed2", "Bob")
        _make_article(db, "a1")
        _make_article(db, "a2")

        follow_user(db, "viewer", "followed1")
        follow_user(db, "viewer", "followed2")
        add_share(db, "followed1", "a1", comment="Good read")
        add_share(db, "followed2", "a2")

        feed = get_shares_by_followed(db, "viewer")
        assert len(feed) == 2

    def test_get_shares_by_followed_empty(self, db):
        from peerpedia_core.storage.db.crud_share import get_shares_by_followed

        _make_user(db, "viewer")
        feed = get_shares_by_followed(db, "viewer")
        assert feed == []


class TestAliasCrud:
    def test_set_alias_requires_follow(self, db):
        from peerpedia_core.storage.db.guards import require_following_for_alias

        _make_user(db, "owner")
        _make_user(db, "target")

        from peerpedia_core.exceptions import BadRequestError
        with pytest.raises(BadRequestError, match="MUST_FOLLOW_FOR_ALIAS"):
            require_following_for_alias(db, "owner", "target")

    def test_set_alias_empty_raises(self, db):
        from peerpedia_core.storage.db.guards import require_following_for_alias
        from peerpedia_core.storage.db.crud_alias import set_alias
        from peerpedia_core.storage.db.crud_follow import follow_user

        _make_user(db, "owner")
        _make_user(db, "target")
        follow_user(db, "owner", "target")

        with pytest.raises(ValueError, match="ALIAS_EMPTY"):
            set_alias(db, "owner", "target", "  ")

    def test_set_and_get_alias(self, db):
        from peerpedia_core.storage.db.guards import require_following_for_alias
        from peerpedia_core.storage.db.crud_alias import set_alias, get_alias_for
        from peerpedia_core.storage.db.crud_follow import follow_user

        _make_user(db, "owner")
        _make_user(db, "target")
        follow_user(db, "owner", "target")

        set_alias(db, "owner", "target", "bob")
        assert get_alias_for(db, "owner", "target") == "bob"

    def test_set_alias_upserts(self, db):
        from peerpedia_core.storage.db.guards import require_following_for_alias
        from peerpedia_core.storage.db.crud_alias import set_alias, get_alias_for
        from peerpedia_core.storage.db.crud_follow import follow_user

        _make_user(db, "owner")
        _make_user(db, "target")
        follow_user(db, "owner", "target")

        set_alias(db, "owner", "target", "first")
        set_alias(db, "owner", "target", "second")
        assert get_alias_for(db, "owner", "target") == "second"

    def test_remove_alias(self, db):
        from peerpedia_core.storage.db.crud_alias import (
            set_alias, remove_alias, get_alias_for, list_aliases,
        )
        from peerpedia_core.storage.db.crud_follow import follow_user

        _make_user(db, "owner")
        _make_user(db, "target")
        follow_user(db, "owner", "target")

        set_alias(db, "owner", "target", "bob")
        remove_alias(db, "owner", "target")
        assert get_alias_for(db, "owner", "target") is None
        assert list_aliases(db, "owner") == []

    def test_remove_nonexistent_alias_noop(self, db):
        from peerpedia_core.storage.db.crud_alias import remove_alias

        _make_user(db, "owner")
        _make_user(db, "target")
        remove_alias(db, "owner", "target")  # should not raise

    def test_list_aliases(self, db):
        from peerpedia_core.storage.db.guards import require_following_for_alias
        from peerpedia_core.storage.db.crud_alias import set_alias, list_aliases
        from peerpedia_core.storage.db.crud_follow import follow_user

        _make_user(db, "owner")
        _make_user(db, "t1")
        _make_user(db, "t2")
        follow_user(db, "owner", "t1")
        follow_user(db, "owner", "t2")

        set_alias(db, "owner", "t1", "alice")
        set_alias(db, "owner", "t2", "bob")
        aliases = list_aliases(db, "owner")
        assert len(aliases) == 2
        assert aliases[0].alias == "alice"  # sorted

    def test_search_users_by_name_or_alias(self, db):
        from peerpedia_core.storage.db.crud_alias import (
            search_users_by_name_or_alias, set_alias,
        )
        from peerpedia_core.storage.db.crud_follow import follow_user

        _make_user(db, "owner")
        _make_user(db, "target", "RealName")
        follow_user(db, "owner", "target")
        set_alias(db, "owner", "target", "nick")

        users = search_users_by_name_or_alias(db, name="RealName")
        assert len(users) == 1
        assert users[0].id == "target"

        users = search_users_by_name_or_alias(db, alias="nick", owner_id="owner")
        assert len(users) == 1
        assert users[0].id == "target"

        users = search_users_by_name_or_alias(db, name="nobody")
        assert len(users) == 0

    def test_search_alias_scoped_to_owner(self, db):
        from peerpedia_core.storage.db.crud_alias import search_users_by_name_or_alias, set_alias
        from peerpedia_core.storage.db.crud_follow import follow_user

        _make_user(db, "owner")
        _make_user(db, "other")
        _make_user(db, "target", "RealName")
        follow_user(db, "owner", "target")
        set_alias(db, "owner", "target", "nick")

        users = search_users_by_name_or_alias(db, alias="nick", owner_id="other")
        assert len(users) == 0
