# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

r"""Executable specifications for the CRUD layer.

STATUS: LOCKED — these define product behavior.  Implementation must conform.

Each specification is a multi-step workflow that exercises several CRUD
functions together, using only the public CRUD API.  No direct SQL, no
ORM model construction, no internal helpers — the CRUD layer IS the
interface under specification.

Specification inventory
-----------------------
User lifecycle
    S1 — create → get back → soft-delete → excluded from queries → still findable by ID
Social loop
    S2 — create two → A follows B → B follows A → mutual → A unfollows B → verify counts
Article author loop
    S3 — create with authors → get author list → append author → verify position ordering
"""

import uuid

import pytest

from peerpedia_core.exceptions import NotFoundError
from peerpedia_core.storage.db.engine import get_session

# ═══════════════════════════════════════════════════════════════════════════════
# Helpers — minimal, zero-IO factories that use only the CRUD public API
# ═══════════════════════════════════════════════════════════════════════════════

_PK = "0000000000000000000000000000000000000000000000000000000000000000"


def _uid() -> str:
    return str(uuid.uuid4())


def _create_user(session, /, *, name="", public_key=_PK, affiliation=""):
    """Thin wrapper — all spec tests call the real ``create_user`` via this."""
    from peerpedia_core.storage.db.crud_user import create_user
    return create_user(session, name=name, public_key=public_key, affiliation=affiliation)


# ═══════════════════════════════════════════════════════════════════════════════
# S1 — User lifecycle
# ═══════════════════════════════════════════════════════════════════════════════


class TestUserLifecycle:
    """Create → retrieve → soft-delete → excluded from queries → findable by ID."""

    def test_create_and_retrieve(self, engine):
        """A created user MUST be retrievable by ID with all fields intact."""
        from peerpedia_core.storage.db.crud_user import get_user

        session = get_session(engine)
        u = _create_user(session, name="Ada", affiliation="MIT")

        found = get_user(session, u.id)
        assert found is not None
        assert found.name == "Ada"
        assert found.affiliation == "MIT"
        assert found.deleted_at is None
        session.close()

    def test_soft_delete_excludes_from_queries(self, engine):
        """After soft-delete, the user MUST NOT appear in name search or listings."""
        from peerpedia_core.storage.db.crud_user import (
            list_users_by_name, list_users, search_users, soft_delete_user,
        )

        session = get_session(engine)
        u = _create_user(session, name="DeleteMe")
        soft_delete_user(session, u.id)
        session.commit()

        assert list_users_by_name(session, "DeleteMe") == []
        assert u.id not in {r.id for r in list_users(session)}
        assert search_users(session, query="DeleteMe") == []
        session.close()

    def test_soft_deleted_still_findable_by_id(self, engine):
        """Soft-deleted users MUST still be retrievable by ID for FK resolution."""
        from peerpedia_core.storage.db.crud_user import get_user, soft_delete_user

        session = get_session(engine)
        u = _create_user(session, name="Ghost")
        soft_delete_user(session, u.id)
        session.commit()

        ghost = get_user(session, u.id)
        assert ghost is not None
        assert ghost.deleted_at is not None
        session.close()

    def test_delete_nonexistent_raises(self, engine):
        """Soft-deleting a nonexistent user MUST raise NotFoundError."""
        from peerpedia_core.storage.db.crud_user import soft_delete_user

        session = get_session(engine)
        with pytest.raises(NotFoundError):
            soft_delete_user(session, "nonexistent-id")
        session.close()


# ═══════════════════════════════════════════════════════════════════════════════
# S2 — Social loop
# ═══════════════════════════════════════════════════════════════════════════════


class TestSocialLoop:
    """Create → follow → list followers → mutual follow → unfollow → verify counts."""

    def test_follow_and_show_followers(self, engine):
        """A follows B → B MUST appear in A's following and A in B's followers."""
        from peerpedia_core.storage.db.crud_user import (
            follow_user, get_follower_count, get_followers,
            get_following, get_following_count, is_following,
        )

        session = get_session(engine)
        alice = _create_user(session, name="Alice")
        bob = _create_user(session, name="Bob")

        follow_user(session, alice.id, bob.id)

        # Observable state
        assert is_following(session, alice.id, bob.id) is True
        assert is_following(session, bob.id, alice.id) is False
        assert get_following_count(session, alice.id) == 1
        assert get_follower_count(session, bob.id) == 1
        assert get_followers(session, bob.id)[0].name == "Alice"
        assert get_following(session, alice.id)[0].name == "Bob"
        session.close()

    def test_mutual_follow(self, engine):
        """A follows B and B follows A → both MUST show each other in followers/following."""
        from peerpedia_core.storage.db.crud_user import (
            follow_user, get_followers, get_following,
        )

        session = get_session(engine)
        alice = _create_user(session, name="Alice")
        bob = _create_user(session, name="Bob")

        follow_user(session, alice.id, bob.id)
        follow_user(session, bob.id, alice.id)

        alice_following = {u.id for u in get_following(session, alice.id)}
        alice_followers = {u.id for u in get_followers(session, alice.id)}
        assert alice_following == {bob.id}
        assert alice_followers == {bob.id}
        session.close()

    def test_unfollow_reduces_counts(self, engine):
        """After unfollow, counts MUST decrement and is_following MUST return False."""
        from peerpedia_core.storage.db.crud_user import (
            follow_user, get_follower_count, get_following_count,
            is_following, unfollow_user,
        )

        session = get_session(engine)
        alice = _create_user(session, name="Alice")
        bob = _create_user(session, name="Bob")

        follow_user(session, alice.id, bob.id)
        assert get_following_count(session, alice.id) == 1

        unfollow_user(session, alice.id, bob.id)
        assert is_following(session, alice.id, bob.id) is False
        assert get_following_count(session, alice.id) == 0
        assert get_follower_count(session, bob.id) == 0
        session.close()

    def test_unfollow_then_refollow_restores(self, engine):
        """Unfollow + follow MUST restore the relationship (soft-delete reuse)."""
        from peerpedia_core.storage.db.crud_user import (
            follow_user, is_following, unfollow_user,
        )

        session = get_session(engine)
        alice = _create_user(session, name="Alice")
        bob = _create_user(session, name="Bob")

        follow_user(session, alice.id, bob.id)
        unfollow_user(session, alice.id, bob.id)
        follow_user(session, alice.id, bob.id)

        assert is_following(session, alice.id, bob.id) is True
        session.close()

    def test_cannot_self_follow(self, engine):
        """Following yourself MUST raise BadRequestError."""
        from peerpedia_core.exceptions import BadRequestError
        from peerpedia_core.storage.db.crud_user import follow_user

        session = get_session(engine)
        alice = _create_user(session, name="Alice")

        with pytest.raises(BadRequestError):
            follow_user(session, alice.id, alice.id)
        session.close()


# ═══════════════════════════════════════════════════════════════════════════════
# S3 — Article author loop
# ═══════════════════════════════════════════════════════════════════════════════


class TestArticleAuthorLoop:
    """Create with authors → get author list → append author → verify ordering."""

    def test_create_article_with_authors(self, engine):
        """An article created with authors MUST return them in order."""
        from peerpedia_core.storage.db.crud_article import create_article, list_author_ids

        session = get_session(engine)
        lead = _create_user(session, name="Lead Author")
        second = _create_user(session, name="Second Author")

        article = create_article(session, title="A Study", authors=[lead.id, second.id])

        author_ids = list_author_ids(session, article.id)
        assert author_ids == [lead.id, second.id], "author order must match creation order"
        session.close()

    def test_get_author_ids_empty_for_no_authors(self, engine):
        """An article with no author rows MUST return an empty list."""
        from peerpedia_core.storage.db.crud_article import create_article, list_author_ids

        session = get_session(engine)
        article = create_article(session, title="Solo", authors=[])
        assert list_author_ids(session, article.id) == []
        session.close()

    def test_replace_authors(self, engine):
        """Replacing all authors MUST produce exactly the new list in order."""
        from peerpedia_core.storage.db.crud_article import list_author_ids, set_article_authors

        session = get_session(engine)
        a1 = _create_user(session, name="A1")
        a2 = _create_user(session, name="A2")
        a3 = _create_user(session, name="A3")

        # Create article with list_author_ids via create_article
        from peerpedia_core.storage.db.crud_article import create_article
        article = create_article(session, title="", authors=[a1.id])

        # Replace
        set_article_authors(session, article.id, [a2.id, a3.id])
        assert list_author_ids(session, article.id) == [a2.id, a3.id]
        session.close()

    def test_append_author_preserves_position_order(self, engine):
        """Adding an author later MUST place them after existing authors."""
        from peerpedia_core.storage.db.crud_article import add_article_authors, list_author_ids

        session = get_session(engine)
        lead = _create_user(session, name="Lead")
        late = _create_user(session, name="Latecomer")

        # Create article with one author via create_article
        from peerpedia_core.storage.db.crud_article import create_article
        article = create_article(session, title="", authors=[lead.id])

        # Later, add another author
        add_article_authors(session, article.id, [late.id])

        authors = list_author_ids(session, article.id)
        assert authors[0] == lead.id, "lead author must stay at position 0"
        assert authors[1] == late.id, "appended author must be at position 1"
        session.close()

    def test_duplicate_author_violates_constraint_on_flush(self, engine):
        """The DB MUST reject duplicate (article_id, author_id) on flush.
        Callers are expected to deduplicate before calling add_article_authors."""
        from sqlalchemy.exc import IntegrityError

        from peerpedia_core.storage.db.crud_article import add_article_authors, create_article

        session = get_session(engine)
        author = _create_user(session, name="Dup")
        article = create_article(session, title="", authors=[author.id])

        # DB-level guard: duplicate insert violates unique constraint
        add_article_authors(session, article.id, [author.id])
        with pytest.raises(IntegrityError):
            session.flush()
        session.rollback()
        session.close()


# ═══════════════════════════════════════════════════════════════════════════════
# S4 — Reputation loop
# ═══════════════════════════════════════════════════════════════════════════════


class TestReputationLoop:
    """Set reputation → get back → overwrite → get back."""

    def test_set_and_get_reputation(self, engine):
        """Reputation set on a user MUST be retrievable with exact equality."""
        from peerpedia_core.storage.db.crud_user import get_user, update_user_reputation

        session = get_session(engine)
        u = _create_user(session, name="Scholar")

        scores = {"professionalism": 4.5, "objectivity": 3.0}
        update_user_reputation(session, u.id, scores)

        fetched = get_user(session, u.id)
        assert fetched.reputation == scores
        session.close()

    def test_overwrite_reputation(self, engine):
        """Setting reputation twice MUST replace the previous value completely."""
        from peerpedia_core.storage.db.crud_user import get_user, update_user_reputation

        session = get_session(engine)
        u = _create_user(session, name="Scholar")

        update_user_reputation(session, u.id, {"professionalism": 1.0})
        update_user_reputation(session, u.id, {"professionalism": 5.0, "pedagogy": 4.0})

        fetched = get_user(session, u.id)
        assert fetched.reputation == {"professionalism": 5.0, "pedagogy": 4.0}
        session.close()

    def test_update_reputation_nonexistent_raises(self, engine):
        """Updating reputation for a nonexistent user MUST raise NotFoundError."""
        from peerpedia_core.storage.db.crud_user import update_user_reputation

        session = get_session(engine)
        with pytest.raises(NotFoundError):
            update_user_reputation(session, "no-such-id", {})
        session.close()


# ═══════════════════════════════════════════════════════════════════════════════
# S5 — Public key TOFU
# ═══════════════════════════════════════════════════════════════════════════════


class TestPubkeyTOFU:
    """Trust-On-First-Use semantics for Ed25519 public keys."""

    def test_first_key_is_stored(self, engine):
        """Setting a key on a user with no prior key MUST return 'stored'."""
        from peerpedia_core.storage.db.crud_user import create_user, set_user_pubkey_tofu

        session = get_session(engine)
        # Omit public_key so it defaults to None (no key yet)
        u = create_user(session, name="NewUser", affiliation="")

        result = set_user_pubkey_tofu(session, u.id, _PK)
        assert result == "stored"
        session.close()

    def test_same_key_is_unchanged(self, engine):
        """Setting the same key MUST return 'unchanged'."""
        from peerpedia_core.storage.db.crud_user import set_user_pubkey_tofu

        session = get_session(engine)
        u = _create_user(session, name="KeyHolder", public_key=_PK)

        result = set_user_pubkey_tofu(session, u.id, _PK)
        assert result == "unchanged"
        session.close()

    def test_different_key_is_rotated(self, engine):
        """Setting a different key MUST return 'rotated' and update the stored key."""
        from peerpedia_core.storage.db.crud_user import get_user, set_user_pubkey_tofu

        session = get_session(engine)
        u = _create_user(session, name="KeyRotator", public_key=_PK)

        new_key = "1111111111111111111111111111111111111111111111111111111111111111"
        result = set_user_pubkey_tofu(session, u.id, new_key)
        assert result == "rotated"
        assert get_user(session, u.id).public_key == new_key
        session.close()

    def test_unknown_user(self, engine):
        """TOFU on a nonexistent user MUST return 'unknown_user'."""
        from peerpedia_core.storage.db.crud_user import set_user_pubkey_tofu

        session = get_session(engine)
        result = set_user_pubkey_tofu(session, "nonexistent-id", _PK)
        assert result == "unknown_user"
        session.close()
