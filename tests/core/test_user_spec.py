# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Spec: User lifecycle + social."""

import pytest

from peerpedia_core.exceptions import BadRequestError
from tests.core.conftest import make_user


# ═══════════════════════════════════════════════════════════════════════════════
# S1 — Create + verify
# ═══════════════════════════════════════════════════════════════════════════════


class TestUserCreate:
    def test_create_and_get(self, db):
        from peerpedia_core.core.users import create_user, get_user
        u = create_user(db, name="Alice", public_key="00" * 32)
        fetched = get_user(db, u.id)
        assert fetched.name == "Alice"
        assert fetched.public_key == "00" * 32

    def test_create_with_affiliation(self, db):
        from peerpedia_core.core.users import create_user, get_user
        u = create_user(db, name="Bob", public_key="11" * 32, affiliation="MIT")
        assert get_user(db, u.id).affiliation == "MIT"

    def test_duplicate_name_allowed(self, db):
        from peerpedia_core.core.users import create_user
        u1 = create_user(db, name="Same", public_key="aa" * 32)
        u2 = create_user(db, name="Same", public_key="bb" * 32)
        assert u1.id != u2.id


# ═══════════════════════════════════════════════════════════════════════════════
# S2 — Search + list
# ═══════════════════════════════════════════════════════════════════════════════


class TestUserSearch:
    def test_search_by_name(self, db):
        from peerpedia_core.core.users import create_user, search_users
        create_user(db, name="Alice Johnson", public_key="00" * 32)
        create_user(db, name="Bob Smith", public_key="11" * 32)
        result = search_users(db, query="alice")
        assert len(result) == 1
        assert result[0].name == "Alice Johnson"

    def test_list_newest_first(self, db):
        from peerpedia_core.core.users import create_user, list_users
        create_user(db, name="Older", public_key="00" * 32)
        create_user(db, name="Newer", public_key="11" * 32)
        assert list_users(db)[0].name == "Newer"


# ═══════════════════════════════════════════════════════════════════════════════
# S3 — Soft delete
# ═══════════════════════════════════════════════════════════════════════════════


class TestSoftDelete:
    def test_soft_delete_excludes_from_list(self, db):
        from peerpedia_core.core.users import soft_delete_user
        from peerpedia_core.core import list_users_by_name, get_user
        u = make_user(db, "DeleteMe")
        soft_delete_user(db, u.id)
        assert list_users_by_name(db, "DeleteMe") == []
        # Still findable by ID
        assert get_user(db, u.id).deleted_at is not None


# ═══════════════════════════════════════════════════════════════════════════════
# S4 — Follow / unfollow
# ═══════════════════════════════════════════════════════════════════════════════


class TestFollow:
    def test_follow_and_unfollow(self, db):
        from peerpedia_core.core.users import (
            create_user, follow_user, get_followers, get_following,
            is_following, unfollow_user,
        )
        from peerpedia_core.storage.db.crud_follow import get_follower_count, get_following_count
        alice = create_user(db, name="Alice", public_key="00" * 32)
        bob = create_user(db, name="Bob", public_key="11" * 32)

        follow_user(db, alice.id, bob.id)
        assert is_following(db, alice.id, bob.id)
        assert get_following_count(db, alice.id) == 1
        assert get_follower_count(db, bob.id) == 1

        unfollow_user(db, alice.id, bob.id)
        assert not is_following(db, alice.id, bob.id)
        assert get_following_count(db, alice.id) == 0

    def test_mutual_follow(self, db):
        from peerpedia_core.core.users import create_user, follow_user, get_followers, get_following
        alice = create_user(db, name="Alice", public_key="00" * 32)
        bob = create_user(db, name="Bob", public_key="11" * 32)

        follow_user(db, alice.id, bob.id)
        follow_user(db, bob.id, alice.id)

        assert {u.id for u in get_following(db, alice.id)} == {bob.id}
        assert {u.id for u in get_followers(db, alice.id)} == {bob.id}

    def test_cannot_self_follow(self, db):
        from peerpedia_core.core.users import create_user, follow_user
        alice = create_user(db, name="Alice", public_key="00" * 32)
        with pytest.raises(BadRequestError):
            follow_user(db, alice.id, alice.id)

    def test_top_users_by_followers(self, db):
        from peerpedia_core.core.users import (
            create_user, follow_user, get_top_users_by_followers,
        )
        popular = create_user(db, name="Popular", public_key="00" * 32)
        loner = create_user(db, name="Loner", public_key="11" * 32)
        for i in range(3):
            fan = create_user(db, name=f"Fan{i}", public_key=f"{i:064d}")
            follow_user(db, fan.id, popular.id)

        top = get_top_users_by_followers(db, limit=10)
        assert top[0]["name"] == "Popular"
        assert top[0]["follower_count"] == 3
