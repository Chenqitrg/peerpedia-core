# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Tests for commands/discover.py merge functions + sync/discovery.py."""

from unittest.mock import patch

import pytest
from sqlalchemy.orm import Session

from peerpedia_core.commands.discover import merge_article_meta, merge_follows, merge_users
from peerpedia_core.exceptions import ProtocolError, TransportError
from peerpedia_core.storage.db.crud_article import create_article, get_article
from peerpedia_core.storage.db.crud_user import get_user, is_following
from peerpedia_core.storage.db.engine import get_session
from peerpedia_core.storage.db.models import User
from peerpedia_core.social.exchange import discover_articles, discover_followers, discover_following


@pytest.fixture
def db(engine):
    session = get_session(engine)
    yield session
    session.rollback()
    session.close()


def _make_user(db: Session, uid: str, name: str):
    u = User(id=uid, name=name, public_key="00" * 32)
    db.add(u)
    db.flush()
    return u


# ── merge_users ──────────────────────────────────────────────────────────────


class TestMergeUsers:
    def test_adds_new_user(self, db):
        n = merge_users(db, [{"id": "u1", "name": "Alice", "address": "http://a:8080"}])
        assert n == 1
        u = get_user(db, "u1")
        assert u.name == "Alice"
        assert u.address == "http://a:8080"

    def test_skips_existing_user(self, db):
        _make_user(db, "u1", "Alice")
        get_user(db, "u1").address = "http://existing:8080"
        db.flush()
        n = merge_users(db, [{"id": "u1", "name": "Alice", "address": "http://a:8080"}])
        assert n == 0

    def test_raises_on_missing_address_for_existing_user(self, db):
        """Existing user without address + peer has address → data inconsistency."""
        _make_user(db, "u1", "Alice")
        with pytest.raises(ValueError, match="has no address"):
            merge_users(db, [{"id": "u1", "name": "Alice", "address": "http://n:8080"}])

    def test_does_not_overwrite_existing_address(self, db):
        _make_user(db, "u1", "Alice")
        get_user(db, "u1").address = "http://original:8080"
        db.flush()
        merge_users(db, [{"id": "u1", "name": "Alice", "address": "http://attacker:8080"}])
        assert get_user(db, "u1").address == "http://original:8080"

    def test_raises_on_missing_address(self, db):
        with pytest.raises(ValueError, match="missing 'address'"):
            merge_users(db, [{"id": "u1", "name": "Alice"}])

    def test_raises_on_empty_address(self, db):
        with pytest.raises(ValueError, match="missing 'address'"):
            merge_users(db, [{"id": "u1", "name": "Alice", "address": ""}])


# ── merge_follows ────────────────────────────────────────────────────────────


class TestMergeFollows:
    def test_adds_new_follow(self, db):
        _make_user(db, "alice", "Alice")
        _make_user(db, "bob", "Bob")
        n = merge_follows(db, "alice", [{"id": "bob"}])
        assert n == 1
        assert is_following(db, "alice", "bob")

    def test_skips_duplicate(self, db):
        _make_user(db, "alice", "Alice")
        _make_user(db, "bob", "Bob")
        merge_follows(db, "alice", [{"id": "bob"}])
        n = merge_follows(db, "alice", [{"id": "bob"}])
        assert n == 0

    def test_raises_on_self_follow(self, db):
        _make_user(db, "alice", "Alice")
        with pytest.raises(ValueError, match="self-follow"):
            merge_follows(db, "alice", [{"id": "alice"}])

    def test_mixed_new_and_existing(self, db):
        _make_user(db, "alice", "Alice")
        _make_user(db, "bob", "Bob")
        _make_user(db, "carol", "Carol")
        merge_follows(db, "alice", [{"id": "bob"}])
        n = merge_follows(db, "alice", [{"id": "bob"}, {"id": "carol"}])
        assert n == 1
        assert is_following(db, "alice", "carol")


# ── merge_article_meta ───────────────────────────────────────────────────────


class TestMergeArticleMeta:
    def test_adds_new_article(self, db):
        _make_user(db, "alice", "Alice")
        n = merge_article_meta(db, [
            {"id": "art-1", "title": "Paper", "status": "published"}
        ])
        assert n == 1
        a = get_article(db, "art-1")
        assert a.title == "Paper"
        assert a.status == "published"

    def test_skips_existing_article(self, db):
        _make_user(db, "alice", "Alice")
        create_article(db, id="art-1", title="Paper", authors=[], status="published")
        db.flush()
        n = merge_article_meta(db, [{"id": "art-1", "title": "Paper", "status": "published"}])
        assert n == 0

    def test_raises_on_missing_status(self, db):
        with pytest.raises(ValueError, match="missing 'status'"):
            merge_article_meta(db, [{"id": "art-1", "title": "Paper"}])


# ── discover_* — orchestration with mocked transport ─────────────────────────


class TestDiscoverOrchestration:
    def test_following_none_raises(self, db):
        """None from fetch (not found) → ProtocolError (fail fast)."""
        _make_user(db, "alice", "Alice")
        with patch("peerpedia_core.social.exchange.fetch_following", return_value=None):
            with pytest.raises(ProtocolError, match="returned None"):
                discover_following(db, "http://peer:8080", "alice")

    def test_following_raises_on_transport_error(self, db):
        """TransportError from fetch → ConnectionError propagated."""
        _make_user(db, "alice", "Alice")
        with patch("peerpedia_core.social.exchange.fetch_following",
                   side_effect=TransportError("timeout")):
            with pytest.raises(ConnectionError, match="Failed to fetch following"):
                discover_following(db, "http://peer:8080", "alice")

    def test_following_empty_list_returns_zero(self, db):
        _make_user(db, "alice", "Alice")
        with patch("peerpedia_core.social.exchange.fetch_following", return_value=[]):
            n = discover_following(db, "http://peer:8080", "alice")
            assert n == 0

    def test_followers_none_raises(self, db):
        """None from fetch (not found) → ProtocolError (fail fast)."""
        _make_user(db, "alice", "Alice")
        with patch("peerpedia_core.social.exchange.fetch_followers", return_value=None):
            with pytest.raises(ProtocolError, match="returned None"):
                discover_followers(db, "http://peer:8080", "alice")

    def test_followers_raises_on_transport_error(self, db):
        """TransportError from fetch → ConnectionError propagated."""
        _make_user(db, "alice", "Alice")
        with patch("peerpedia_core.social.exchange.fetch_followers",
                   side_effect=TransportError("timeout")):
            with pytest.raises(ConnectionError, match="Failed to fetch followers"):
                discover_followers(db, "http://peer:8080", "alice")

    def test_articles_none_raises(self, db):
        """None from fetch (not found) → ProtocolError (fail fast)."""
        _make_user(db, "alice", "Alice")
        with patch("peerpedia_core.social.exchange.fetch_articles", return_value=None):
            with pytest.raises(ProtocolError, match="returned None"):
                discover_articles(db, "http://peer:8080", "alice")

    def test_articles_raises_on_transport_error(self, db):
        """TransportError from fetch → ConnectionError propagated."""
        _make_user(db, "alice", "Alice")
        with patch("peerpedia_core.social.exchange.fetch_articles",
                   side_effect=TransportError("timeout")):
            with pytest.raises(ConnectionError, match="Failed to fetch articles"):
                discover_articles(db, "http://peer:8080", "alice")
