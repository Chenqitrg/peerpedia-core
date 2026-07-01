# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Tests for UserStorage and FollowStorage CRUD."""

import pytest

from peerpedia_core.exceptions import BadRequestError, NotFoundError
from peerpedia_core.storage.db.engine import get_session
from peerpedia_core.storage.db.models import FollowStorage, UserStorage
from tests.crud.conftest import make_article, make_user


# ═══════════════════════════════════════════════════════════════════════════════
# User CRUD
# ═══════════════════════════════════════════════════════════════════════════════


class TestUserCRUD:
    def test_create_user(self, engine):
        from peerpedia_core.storage.db.crud_user import create_user

        session = get_session(engine)
        u = create_user(session, name="新用户",
                        public_key="0000000000000000000000000000000000000000000000000000000000000000",
                        affiliation="某大学")
        assert u.id is not None
        assert u.name == "新用户"
        session.close()

    def test_get_user_by_id(self, engine):
        from peerpedia_core.storage.db.crud_user import create_user, get_user_by_id

        session = get_session(engine)
        u = create_user(session, name="test",
                        public_key="0000000000000000000000000000000000000000000000000000000000000000")
        assert get_user_by_id(session, u.id).name == "test"
        assert get_user_by_id(session, "nonexistent") is None
        session.close()

    def test_list_active_users(self, engine):
        from peerpedia_core.storage.db.crud_user import create_user, list_active_users

        session = get_session(engine)
        create_user(session, name="张三",
                    public_key="0000000000000000000000000000000000000000000000000000000000000000")
        create_user(session, name="李四",
                    public_key="0000000000000000000000000000000000000000000000000000000000000000")
        assert len(list_active_users(session)) == 2
        session.close()

    def test_update_user_reputation(self, engine):
        from peerpedia_core.storage.db.crud_user import create_user, get_user_by_id, update_user_reputation

        session = get_session(engine)
        u = create_user(session, name="rep_user",
                        public_key="0000000000000000000000000000000000000000000000000000000000000000")
        rep = {"professionalism": 4.0, "objectivity": 3.5, "collaboration": 4.5, "pedagogy": 4.0}
        update_user_reputation(session, u.id, rep)
        assert get_user_by_id(session, u.id).reputation == rep
        session.close()

    def test_get_user_by_name_returns_list(self, engine):
        from peerpedia_core.storage.db.crud_user import create_user, list_users_by_name

        session = get_session(engine)
        create_user(session, name="alice",
                    public_key="0000000000000000000000000000000000000000000000000000000000000000")
        result = list_users_by_name(session, "alice")
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0].name == "alice"
        assert list_users_by_name(session, "nonexistent") == []
        session.close()

    def test_duplicate_names_allowed(self, engine):
        from peerpedia_core.storage.db.crud_user import create_user, list_users_by_name

        session = get_session(engine)
        u1 = create_user(session, name="同名",
                         public_key="aaaa00000000000000000000000000000000000000000000000000000000000000")
        u2 = create_user(session, name="同名",
                         public_key="bbbb00000000000000000000000000000000000000000000000000000000000000")
        assert u1.id != u2.id
        result = list_users_by_name(session, "同名")
        assert len(result) == 2
        assert {u.id for u in result} == {u1.id, u2.id}
        session.close()


# ═══════════════════════════════════════════════════════════════════════════════
# Follow CRUD
# ═══════════════════════════════════════════════════════════════════════════════


class TestFollowCRUD:
    def test_follow_unfollow(self, engine):
        from peerpedia_core.storage.db.crud_user import create_user
        from peerpedia_core.storage.db.crud_follow import (
            follow_user, is_following, unfollow_user,
        )

        session = get_session(engine)
        a = create_user(session, name="A",
                        public_key="0000000000000000000000000000000000000000000000000000000000000000")
        b = create_user(session, name="B",
                        public_key="0000000000000000000000000000000000000000000000000000000000000000")
        follow_user(session, a.id, b.id)
        assert is_following(session, a.id, b.id) is True
        assert is_following(session, b.id, a.id) is False
        unfollow_user(session, a.id, b.id)
        assert is_following(session, a.id, b.id) is False
        session.close()

    def test_get_followers_following(self, engine):
        from peerpedia_core.storage.db.crud_user import create_user
        from peerpedia_core.storage.db.crud_follow import (
            follow_user, get_follower_count, get_followers,
            get_following, get_following_count,
        )

        session = get_session(engine)
        a = create_user(session, name="A",
                        public_key="0000000000000000000000000000000000000000000000000000000000000000")
        b = create_user(session, name="B",
                        public_key="0000000000000000000000000000000000000000000000000000000000000000")
        c = create_user(session, name="C",
                        public_key="0000000000000000000000000000000000000000000000000000000000000000")
        follow_user(session, b.id, a.id)
        follow_user(session, c.id, a.id)
        assert get_follower_count(session, a.id) == 2
        assert get_following_count(session, b.id) == 1
        followers = get_followers(session, a.id)
        assert len(followers) == 2
        following = get_following(session, c.id)
        assert len(following) == 1
        session.close()

    def test_follow_user_rejects_self_follow(self, engine):
        from peerpedia_core.storage.db.crud_user import create_user; from peerpedia_core.storage.db.crud_follow import follow_user

        session = get_session(engine)
        a = create_user(session, name="A",
                        public_key="0000000000000000000000000000000000000000000000000000000000000000")
        with pytest.raises(BadRequestError, match="CANNOT_SELF_ACTION"):
            follow_user(session, a.id, a.id)
        session.close()

    def test_unfollow_soft_deletes(self, engine):
        from peerpedia_core.storage.db.crud_user import create_user
        from peerpedia_core.storage.db.crud_follow import (
            follow_user, is_following, unfollow_user,
        )

        session = get_session(engine)
        a = create_user(session, name="A", public_key="00" * 32)
        b = create_user(session, name="B", public_key="00" * 32)
        follow_user(session, a.id, b.id)
        unfollow_user(session, a.id, b.id)

        assert is_following(session, a.id, b.id) is False
        f = session.query(FollowStorage).filter(
            FollowStorage.follower_id == a.id, FollowStorage.followed_id == b.id,
        ).first()
        assert f is not None
        assert f.deleted_at is not None
        session.close()

    def test_follow_restores_soft_deleted(self, engine):
        from peerpedia_core.storage.db.crud_user import create_user
        from peerpedia_core.storage.db.crud_follow import (
            follow_user, is_following, unfollow_user,
        )

        session = get_session(engine)
        a = create_user(session, name="A", public_key="00" * 32)
        b = create_user(session, name="B", public_key="00" * 32)
        follow_user(session, a.id, b.id)
        unfollow_user(session, a.id, b.id)
        follow_user(session, a.id, b.id)

        assert is_following(session, a.id, b.id) is True
        f = session.query(FollowStorage).filter(
            FollowStorage.follower_id == a.id, FollowStorage.followed_id == b.id,
        ).first()
        assert f.deleted_at is None
        session.close()


# ═══════════════════════════════════════════════════════════════════════════════
# User queries — get_user, list_users_by_name, list_users, search_users, list_users_by_ids
# ═══════════════════════════════════════════════════════════════════════════════


class TestUserQueries:
    # ── get_user ─────────────────────────────────────────────────────────

    def test_get_user_found(self, engine):
        from peerpedia_core.storage.db.crud_user import create_user, get_user_by_id

        session = get_session(engine)
        u = create_user(session, name="Alice",
                        public_key="0000000000000000000000000000000000000000000000000000000000000000")
        assert get_user_by_id(session, u.id).name == "Alice"
        session.close()

    def test_get_user_not_found_returns_none(self, engine):
        from peerpedia_core.storage.db.crud_user import get_user_by_id

        session = get_session(engine)
        assert get_user_by_id(session, "nonexistent") is None
        session.close()

    def test_get_user_soft_deleted_is_still_findable_by_id(self, engine):
        """Soft-deleted users can still be loaded by ID (references intact)."""
        from peerpedia_core.storage.db.crud_user import create_user, get_user_by_id, soft_delete_user

        session = get_session(engine)
        u = create_user(session, name="ToDelete",
                        public_key="0000000000000000000000000000000000000000000000000000000000000000")
        soft_delete_user(session, u.id)
        session.commit()
        # By-ID lookup still works — needed for FK resolution
        assert get_user_by_id(session, u.id).deleted_at is not None
        session.close()

    # ── list_users_by_name ──────────────────────────────────────────────────

    def test_get_user_by_name_exact_match(self, engine):
        from peerpedia_core.storage.db.crud_user import create_user, list_users_by_name

        session = get_session(engine)
        create_user(session, name="Charlie",
                    public_key="0000000000000000000000000000000000000000000000000000000000000000")
        result = list_users_by_name(session, "Charlie")
        assert len(result) == 1
        assert result[0].name == "Charlie"
        session.close()

    def test_get_user_by_name_no_match_returns_empty(self, engine):
        from peerpedia_core.storage.db.crud_user import list_users_by_name

        session = get_session(engine)
        assert list_users_by_name(session, "Nobody") == []
        session.close()

    def test_get_user_by_name_excludes_soft_deleted(self, engine):
        from peerpedia_core.storage.db.crud_user import (
            create_user, list_users_by_name, soft_delete_user,
        )

        session = get_session(engine)
        u = create_user(session, name="Gone",
                        public_key="0000000000000000000000000000000000000000000000000000000000000000")
        soft_delete_user(session, u.id)
        session.commit()
        assert list_users_by_name(session, "Gone") == []
        session.close()

    def test_get_user_by_name_duplicates(self, engine):
        from peerpedia_core.storage.db.crud_user import create_user, list_users_by_name

        session = get_session(engine)
        create_user(session, name="Dup",
                    public_key="aaaa00000000000000000000000000000000000000000000000000000000000000")
        create_user(session, name="Dup",
                    public_key="bbbb00000000000000000000000000000000000000000000000000000000000000")
        result = list_users_by_name(session, "Dup")
        assert len(result) == 2
        session.close()

    # ── list_active_users / list_recent_users ──────────────────────────────

    def test_list_recent_users_respects_limit(self, engine):
        from peerpedia_core.storage.db.crud_user import create_user, list_recent_users

        session = get_session(engine)
        for i in range(5):
            create_user(session, name=f"User{i}",
                        public_key=f"{i:064d}")
        result = list_recent_users(session, limit=3)
        assert len(result) == 3
        session.close()

    def test_list_active_users_excludes_soft_deleted(self, engine):
        from peerpedia_core.storage.db.crud_user import (
            create_user, list_active_users, soft_delete_user,
        )

        session = get_session(engine)
        u = create_user(session, name="Visible",
                        public_key="0000000000000000000000000000000000000000000000000000000000000000")
        create_user(session, name="Hidden",
                    public_key="1111111111111111111111111111111111111111111111111111111111111111")
        soft_delete_user(session, u.id)
        session.commit()
        result = list_active_users(session)
        assert len(result) == 1
        assert result[0].name == "Hidden"
        session.close()

    def test_list_recent_users_ordered_newest_first(self, engine):
        from peerpedia_core.storage.db.crud_user import create_user, list_recent_users

        session = get_session(engine)
        create_user(session, name="Older",
                    public_key="0000000000000000000000000000000000000000000000000000000000000000")
        create_user(session, name="Newer",
                    public_key="1111111111111111111111111111111111111111111111111111111111111111")
        result = list_recent_users(session, limit=10)
        assert result[0].name == "Newer"
        session.close()

    # ── search_users ──────────────────────────────────────────────────────

    def test_search_by_name_ilike(self, engine):
        from peerpedia_core.storage.db.crud_user import create_user, search_users

        session = get_session(engine)
        create_user(session, name="Alice Johnson",
                    public_key="0000000000000000000000000000000000000000000000000000000000000000")
        create_user(session, name="Bob Smith",
                    public_key="1111111111111111111111111111111111111111111111111111111111111111")
        create_user(session, name="Charlie Alice",  # "Alice" in surname position
                    public_key="2222222222222222222222222222222222222222222222222222222222222222")
        result = search_users(session, query="alice")
        assert {r.name for r in result} == {"Alice Johnson", "Charlie Alice"}
        session.close()

    def test_search_by_name_no_match(self, engine):
        from peerpedia_core.storage.db.crud_user import create_user, search_users

        session = get_session(engine)
        create_user(session, name="Alice",
                    public_key="0000000000000000000000000000000000000000000000000000000000000000")
        assert search_users(session, query="zzz_nonexistent") == []
        session.close()

    def test_search_by_id_prefix(self, engine):
        from peerpedia_core.storage.db.crud_user import search_users

        session = get_session(engine)
        # Use make_user directly with known IDs
        session.add(UserStorage(
            id="aaaa1111-0000-0000-0000-000000000001", name="A1",
            public_key="00" * 32, affiliation=""))
        session.add(UserStorage(
            id="aaaa1111-0000-0000-0000-000000000002", name="A2",
            public_key="00" * 32, affiliation=""))
        session.add(UserStorage(
            id="bbbb2222-0000-0000-0000-000000000003", name="B1",
            public_key="00" * 32, affiliation=""))
        session.commit()
        result = search_users(session, id_prefix="aaaa1111")
        assert len(result) == 2
        assert {r.name for r in result} == {"A1", "A2"}
        session.close()

    def test_search_by_id_prefix_no_match(self, engine):
        from peerpedia_core.storage.db.crud_user import create_user, search_users

        session = get_session(engine)
        create_user(session, name="Test",
                    public_key="0000000000000000000000000000000000000000000000000000000000000000")
        assert search_users(session, id_prefix="zzzzzzzz") == []
        session.close()

    def test_search_with_limit_offset(self, engine):
        from peerpedia_core.storage.db.crud_user import create_user, search_users

        session = get_session(engine)
        for i in range(5):
            create_user(session, name=f"SearchUser{i}",
                        public_key=f"{i:064d}")
        page = search_users(session, query="SearchUser", limit=2, offset=1)
        assert len(page) == 2
        session.close()

    def test_search_excludes_soft_deleted(self, engine):
        from peerpedia_core.storage.db.crud_user import (
            create_user, search_users, soft_delete_user,
        )

        session = get_session(engine)
        u = create_user(session, name="DelSearch",
                        public_key="0000000000000000000000000000000000000000000000000000000000000000")
        soft_delete_user(session, u.id)
        session.commit()
        assert search_users(session, query="DelSearch") == []
        session.close()

    def test_search_empty_query_and_prefix_returns_all(self, engine):
        from peerpedia_core.storage.db.crud_user import create_user, search_users

        session = get_session(engine)
        create_user(session, name="X",
                    public_key="0000000000000000000000000000000000000000000000000000000000000000")
        create_user(session, name="Y",
                    public_key="1111111111111111111111111111111111111111111111111111111111111111")
        # Neither query nor id_prefix → no additional filter
        result = search_users(session)
        assert len(result) == 2
        session.close()

    # ── list_users_by_ids ──────────────────────────────────────────────────

    def test_get_users_by_ids_batch(self, engine):
        from peerpedia_core.storage.db.crud_user import create_user, list_users_by_ids

        session = get_session(engine)
        u1 = create_user(session, name="Batch1",
                         public_key="0000000000000000000000000000000000000000000000000000000000000000")
        u2 = create_user(session, name="Batch2",
                         public_key="1111111111111111111111111111111111111111111111111111111111111111")
        result = list_users_by_ids(session, {u1.id, u2.id})
        assert len(result) == 2
        assert {r.name for r in result} == {"Batch1", "Batch2"}
        session.close()

    def test_get_users_by_ids_empty_set(self, engine):
        from peerpedia_core.storage.db.crud_user import list_users_by_ids

        session = get_session(engine)
        assert list_users_by_ids(session, set()) == []
        session.close()


    # ── get_top_users_by_followers ────────────────────────────────────────

    def test_get_top_users_by_followers(self, engine):
        from peerpedia_core.storage.db.crud_user import create_user
        from peerpedia_core.storage.db.crud_follow import (
            follow_user, get_top_users_by_followers,
        )

        session = get_session(engine)
        a = create_user(session, name="MostPopular",
                        public_key="00" * 32)
        b = create_user(session, name="LessPopular",
                        public_key="00" * 32)
        c = create_user(session, name="Loner",
                        public_key="00" * 32)
        # Make some followers
        for i in range(3):
            fan = create_user(session, name=f"Fan{i}",
                              public_key=f"{i:064d}")
            follow_user(session, fan.id, a.id)
        fan = create_user(session, name="FanX",
                          public_key="99" * 32)
        follow_user(session, fan.id, b.id)
        session.commit()

        top = get_top_users_by_followers(session, limit=10)
        # MostPopular (3) > LessPopular (1) > Loner (0) + all the fans (0)
        assert top[0]["name"] == "MostPopular"
        assert top[0]["follower_count"] == 3
        assert top[1]["name"] == "LessPopular"
        assert top[1]["follower_count"] == 1
        session.close()

    def test_get_top_users_includes_zero_followers(self, engine):
        from peerpedia_core.storage.db.crud_user import create_user; from peerpedia_core.storage.db.crud_follow import get_top_users_by_followers

        session = get_session(engine)
        create_user(session, name="Nobody",
                    public_key="0000000000000000000000000000000000000000000000000000000000000000")
        session.commit()
        top = get_top_users_by_followers(session)
        assert len(top) == 1
        assert top[0]["name"] == "Nobody"
        assert top[0]["follower_count"] == 0
        session.close()


# ═══════════════════════════════════════════════════════════════════════════════
# User error paths
# ═══════════════════════════════════════════════════════════════════════════════


class TestUserErrorPaths:



    def test_follower_count_zero(self, engine):
        from peerpedia_core.storage.db.crud_follow import get_follower_count

        session = get_session(engine)
        assert get_follower_count(session, "nonexistent") == 0
        session.close()

    def test_following_count_zero(self, engine):
        from peerpedia_core.storage.db.crud_follow import get_following_count

        session = get_session(engine)
        assert get_following_count(session, "nonexistent") == 0
        session.close()


# ═══════════════════════════════════════════════════════════════════════════════
# Salt roundtrip — exercises the full production auth path
# ═══════════════════════════════════════════════════════════════════════════════


class TestSaltRoundtrip:
    def test_salt_roundtrip_derives_same_key(self, engine):
        from peerpedia_core.crypto import derive_key_pair, new_salt
        from peerpedia_core.storage.db.crud_user import create_user, get_user_by_id, update_user_salt

        PASSWORD = "roundtrip-test-password"

        session = get_session(engine)
        salt_hex = new_salt()
        assert len(salt_hex) == 32

        priv_bytes, pub_bytes = derive_key_pair(PASSWORD, salt_hex)
        pubkey_hex = pub_bytes.hex()

        u = create_user(session, name="salt_test", public_key=pubkey_hex)
        update_user_salt(session, u.id, salt_hex)
        session.commit()

        u2 = get_user_by_id(session, u.id)
        assert u2.salt == salt_hex, "salt should survive roundtrip"
        priv2, pub2 = derive_key_pair(PASSWORD, u2.salt)

        assert priv2 == priv_bytes
        assert pub2.hex() == pubkey_hex
        assert u2.public_key == pubkey_hex
        session.close()

    def test_different_salt_produces_different_key(self, engine):
        from peerpedia_core.crypto import derive_key_pair, new_salt

        PASSWORD = "test-password"
        salt1 = new_salt()
        salt2 = new_salt()
        assert salt1 != salt2, "salts should be unique"

        _, pub1 = derive_key_pair(PASSWORD, salt1)
        _, pub2 = derive_key_pair(PASSWORD, salt2)
        assert pub1 != pub2, "different salts → different pubkeys"
