# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Tests for commands/discover.py ingest/sync functions + sync/discovery.py."""

from unittest.mock import patch

import pytest
from sqlalchemy.orm import Session

from peerpedia_core.core.discover import (
    ingest_articles, ingest_followers, ingest_following, ingest_users,
    sync_followers, sync_following,
)
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


# ── ingest_users ────────────────────────────────────────────────────────────


class TestIngestUsers:
    def test_adds_new_user(self, db):
        n = ingest_users(db, [{"id": "u1", "name": "Alice", "address": "http://a:8080"}])
        assert n == 1
        u = get_user(db, "u1")
        assert u.name == "Alice"
        assert u.address == "http://a:8080"

    def test_raises_on_address_conflict(self, db):
        """When local and peer both have non-empty addresses that differ → error."""
        _make_user(db, "u1", "Alice")
        get_user(db, "u1").address = "http://existing:8080"
        db.flush()
        with pytest.raises(ValueError, match="address conflict"):
            ingest_users(db, [{"id": "u1", "name": "Alice", "address": "http://a:8080"}])

    def test_address_filled_for_existing_user_without_address(self, db):
        """Existing user without address + peer has address → no conflict, address stays empty."""
        _make_user(db, "u1", "Alice")
        # Old behavior: raised ValueError.  New behavior: address is optional,
        # and conflict is only checked when BOTH sides have a non-empty address.
        n = ingest_users(db, [{"id": "u1", "name": "Alice", "address": "http://n:8080"}])
        assert n == 0  # existing user, skipped

    def test_skips_existing_user_with_same_address(self, db):
        _make_user(db, "u1", "Alice")
        get_user(db, "u1").address = "http://same:8080"
        db.flush()
        n = ingest_users(db, [{"id": "u1", "name": "Alice", "address": "http://same:8080"}])
        assert n == 0

    def test_address_is_optional(self, db):
        """Address is optional — not all users run their own server."""
        n = ingest_users(db, [{"id": "u1", "name": "Alice"}])
        assert n == 1
        u = get_user(db, "u1")
        assert u.address == ""

    def test_empty_address_accepted(self, db):
        """Empty address is accepted (treated as no address)."""
        n = ingest_users(db, [{"id": "u1", "name": "Alice", "address": ""}])
        assert n == 1
        u = get_user(db, "u1")
        assert u.address == ""


# ── ingest_following / sync_following ────────────────────────────────────────


class TestIngestFollowing:
    def test_adds_new_follow(self, db):
        _make_user(db, "alice", "Alice")
        _make_user(db, "bob", "Bob")
        n = ingest_following(db, "alice", [{"id": "bob"}])
        assert n == 1
        assert is_following(db, "alice", "bob")

    def test_skips_duplicate(self, db):
        _make_user(db, "alice", "Alice")
        _make_user(db, "bob", "Bob")
        ingest_following(db, "alice", [{"id": "bob"}])
        n = ingest_following(db, "alice", [{"id": "bob"}])
        assert n == 0

    def test_raises_on_self_follow(self, db):
        _make_user(db, "alice", "Alice")
        with pytest.raises(ValueError, match="self-follow"):
            ingest_following(db, "alice", [{"id": "alice"}])

    def test_mixed_new_and_existing(self, db):
        _make_user(db, "alice", "Alice")
        _make_user(db, "bob", "Bob")
        _make_user(db, "carol", "Carol")
        ingest_following(db, "alice", [{"id": "bob"}])
        n = ingest_following(db, "alice", [{"id": "bob"}, {"id": "carol"}])
        assert n == 1
        assert is_following(db, "alice", "carol")

    def test_sync_deletes_missing(self, db):
        """sync_following soft-deletes local follows not in remote list."""
        _make_user(db, "alice", "Alice")
        _make_user(db, "bob", "Bob")
        _make_user(db, "carol", "Carol")
        _make_user(db, "dave", "Dave")
        # Local: alice follows bob, carol, dave
        ingest_following(db, "alice", [{"id": "bob"}, {"id": "carol"}, {"id": "dave"}])

        # Authoritative pull: remote only has bob and carol — dave is gone.
        sync_following(db, "alice", [{"id": "bob"}, {"id": "carol"}])

        assert is_following(db, "alice", "bob")
        assert is_following(db, "alice", "carol")
        assert not is_following(db, "alice", "dave"), "dave should be soft-deleted"

    def test_ingest_only_adds(self, db):
        """ingest_following never deletes local follows."""
        _make_user(db, "alice", "Alice")
        _make_user(db, "bob", "Bob")
        _make_user(db, "carol", "Carol")
        # Local: alice follows bob
        ingest_following(db, "alice", [{"id": "bob"}])

        # Non-authoritative pull: remote has carol but NOT bob.
        ingest_following(db, "alice", [{"id": "carol"}])

        assert is_following(db, "alice", "bob"), "bob should still be followed"
        assert is_following(db, "alice", "carol"), "carol should be added"


# ── ingest_followers / sync_followers ────────────────────────────────────────


class TestIngestFollowers:
    """Mirrors TestIngestFollowing for the reverse direction (who follows me)."""

    def test_adds_new_follower(self, db):
        _make_user(db, "alice", "Alice")
        _make_user(db, "bob", "Bob")
        n = ingest_followers(db, "bob", [{"id": "alice"}])
        assert n == 1
        assert is_following(db, "alice", "bob")

    def test_skips_duplicate(self, db):
        _make_user(db, "alice", "Alice")
        _make_user(db, "bob", "Bob")
        ingest_followers(db, "bob", [{"id": "alice"}])
        n = ingest_followers(db, "bob", [{"id": "alice"}])
        assert n == 0

    def test_raises_on_self_follow(self, db):
        _make_user(db, "alice", "Alice")
        with pytest.raises(ValueError, match="self-follow"):
            ingest_followers(db, "alice", [{"id": "alice"}])

    def test_mixed_new_and_existing(self, db):
        _make_user(db, "alice", "Alice")
        _make_user(db, "bob", "Bob")
        _make_user(db, "carol", "Carol")
        ingest_followers(db, "carol", [{"id": "alice"}])
        n = ingest_followers(db, "carol", [{"id": "alice"}, {"id": "bob"}])
        assert n == 1
        assert is_following(db, "bob", "carol")

    def test_sync_deletes_missing(self, db):
        """sync_followers soft-deletes local followers not in remote list."""
        _make_user(db, "alice", "Alice")
        _make_user(db, "bob", "Bob")
        _make_user(db, "carol", "Carol")
        _make_user(db, "dave", "Dave")
        # Local: alice, bob, dave all follow carol
        ingest_followers(db, "carol", [{"id": "alice"}, {"id": "bob"}, {"id": "dave"}])

        # Authoritative pull: remote only has alice and bob — dave unfollowed.
        sync_followers(db, "carol", [{"id": "alice"}, {"id": "bob"}])

        assert is_following(db, "alice", "carol")
        assert is_following(db, "bob", "carol")
        assert not is_following(db, "dave", "carol"), "dave should be soft-deleted"

    def test_ingest_only_adds(self, db):
        """ingest_followers never deletes local followers."""
        _make_user(db, "alice", "Alice")
        _make_user(db, "bob", "Bob")
        _make_user(db, "carol", "Carol")
        # Local: alice follows carol
        ingest_followers(db, "carol", [{"id": "alice"}])

        # Non-authoritative pull: remote has bob but NOT alice.
        ingest_followers(db, "carol", [{"id": "bob"}])

        assert is_following(db, "alice", "carol"), "alice should still be a follower"
        assert is_following(db, "bob", "carol"), "bob should be added"


# ── ingest_articles ─────────────────────────────────────────────────────────


class TestIngestArticles:
    def test_adds_new_article(self, db):
        _make_user(db, "alice", "Alice")
        n = ingest_articles(db, [
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
        n = ingest_articles(db, [{"id": "art-1", "title": "Paper", "status": "published"}])
        assert n == 0

    def test_raises_on_missing_status(self, db):
        with pytest.raises(ValueError, match="missing 'status'"):
            ingest_articles(db, [{"id": "art-1", "title": "Paper"}])


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
        with patch("peerpedia_core.social.exchange.fetch_user_articles", return_value=None):
            with pytest.raises(ProtocolError, match="returned None"):
                discover_articles(db, "http://peer:8080", "alice")

    def test_articles_raises_on_transport_error(self, db):
        """TransportError from fetch → ConnectionError propagated."""
        _make_user(db, "alice", "Alice")
        with patch("peerpedia_core.social.exchange.fetch_user_articles",
                   side_effect=TransportError("timeout")):
            with pytest.raises(ConnectionError, match="Failed to fetch articles"):
                discover_articles(db, "http://peer:8080", "alice")


# ── Peer Backoff ────────────────────────────────────────────────────────────


class TestPeerBackoff:
    """Backoff state management: exponential backoff for dead peers."""

    def test_no_backoff_for_unknown_peer(self):
        from peerpedia_core.social.discovery import _is_peer_backoff
        assert not _is_peer_backoff("https://unknown.example.com")

    def test_backoff_after_failure(self):
        from peerpedia_core.social.discovery import (
            _is_peer_backoff, _peer_failed, _peer_succeeded,
        )

        url = "https://fail.example.com"
        _peer_failed(url)
        assert _is_peer_backoff(url)
        _peer_succeeded(url)

    def test_backoff_increments(self):
        from peerpedia_core.social.discovery import (
            _is_peer_backoff, _peer_failed, _peer_succeeded,
        )

        url = "https://multi-fail.example.com"
        _peer_failed(url)
        _peer_failed(url)
        _peer_failed(url)
        assert _is_peer_backoff(url)
        _peer_failed(url)
        _peer_failed(url)
        assert _is_peer_backoff(url)
        _peer_succeeded(url)

    def test_success_resets_backoff(self):
        from peerpedia_core.social.discovery import (
            _is_peer_backoff, _peer_failed, _peer_succeeded,
        )

        url = "https://recover.example.com"
        _peer_failed(url)
        _peer_failed(url)
        assert _is_peer_backoff(url)
        _peer_succeeded(url)
        assert not _is_peer_backoff(url)

    def test_record_peer_result(self):
        from peerpedia_core.social.discovery import (
            _is_peer_backoff, record_peer_result,
        )

        url = "https://record.example.com"
        record_peer_result(url, success=False)
        assert _is_peer_backoff(url)
        record_peer_result(url, success=True)
        assert not _is_peer_backoff(url)

    def test_backoff_expired(self):
        """Backoff expires after the delay window passes."""
        import time
        from peerpedia_core.social.discovery import (
            _is_peer_backoff, _backoff, _peer_succeeded,
        )

        url = "https://expire.example.com"
        _backoff[url] = {"fail_count": 1, "last_failed_at": time.time() - 61}
        assert not _is_peer_backoff(url)
        _peer_succeeded(url)

    def test_seed_peers_never_skipped(self):
        """Seed peers are always included even if in backoff."""
        from peerpedia_core.social.discovery import get_known_peers, _peer_failed, _peer_succeeded
        from peerpedia_core.config.params import params

        seeds = list(params.discovery.seed_peers)
        if not seeds:
            return
        _peer_failed(seeds[0])
        peers = get_known_peers()
        assert seeds[0] in peers
        _peer_succeeded(seeds[0])


# ── discover_network ────────────────────────────────────────────────────────


class TestDiscoverNetwork:
    """BFS network discovery orchestration."""

    def test_empty_following_returns_zero(self, db):
        """User follows nobody → zero results."""
        _make_user(db, "alice", "Alice")
        with patch("peerpedia_core.social.exchange.fetch_following", return_value=[]):
            from peerpedia_core.social.exchange import discover_network
            result = discover_network(db, "http://peer:8080", "alice", depth=1)
            assert result["users_discovered"] == 0
            assert result["articles_discovered"] == 0
            assert result["follows_added"] == 0

    def test_depth_1_discovers_follows(self, db):
        """Single-level BFS finds followed users and their articles."""
        _make_user(db, "alice", "Alice")
        following = [{"id": "bob", "name": "Bob"}, {"id": "carol", "name": "Carol"}]
        with patch("peerpedia_core.social.exchange.fetch_following",
                   return_value=following):
            with patch("peerpedia_core.social.exchange.discover_articles",
                       return_value=1):
                from peerpedia_core.social.exchange import discover_network
                result = discover_network(db, "http://peer:8080", "alice", depth=1)
                assert result["users_discovered"] == 2
                assert result["follows_added"] == 2

    def test_visited_dedup(self, db):
        """Cyclic follow graph — dedup by user_id."""
        _make_user(db, "alice", "Alice")
        with patch("peerpedia_core.social.exchange.fetch_following",
                   side_effect=[
                       [{"id": "bob", "name": "Bob"}],
                       [{"id": "alice", "name": "Alice"}],
                   ]):
            with patch("peerpedia_core.social.exchange.discover_articles",
                       return_value=1):
                from peerpedia_core.social.exchange import discover_network
                result = discover_network(db, "http://peer:8080", "alice", depth=2)
                assert result["users_discovered"] == 1  # only bob

    def test_max_users_cap(self, db):
        """max_users=2 stops after 2 users discovered."""
        _make_user(db, "alice", "Alice")
        following = [{"id": f"user{i}", "name": f"U{i}"} for i in range(10)]
        with patch("peerpedia_core.social.exchange.fetch_following",
                   return_value=following):
            with patch("peerpedia_core.social.exchange.discover_articles",
                       return_value=1):
                from peerpedia_core.social.exchange import discover_network
                result = discover_network(db, "http://peer:8080", "alice",
                                          depth=1, max_users=2)
                assert result["users_discovered"] <= 2

    def test_fetch_failure_skips_user(self, db):
        """One user's fetch fails → skip that user, continue BFS."""
        _make_user(db, "alice", "Alice")
        _make_user(db, "bob", "Bob")
        with patch("peerpedia_core.social.exchange.fetch_following",
                   return_value=[{"id": "bob", "name": "Bob"}]):
            with patch("peerpedia_core.social.exchange.discover_articles",
                       return_value=0):
                from peerpedia_core.social.exchange import discover_network
                result = discover_network(db, "http://peer:8080", "alice", depth=1)
                assert result["users_discovered"] == 1

    def test_depth_2_multi_level(self, db):
        """Two-level BFS discovers transitive follows."""
        _make_user(db, "alice", "Alice")
        with patch("peerpedia_core.social.exchange.fetch_following",
                   side_effect=[
                       [{"id": "bob", "name": "Bob"}, {"id": "carol", "name": "Carol"}],
                       [{"id": "dave", "name": "Dave"}],
                       [],
                   ]):
            with patch("peerpedia_core.social.exchange.discover_articles",
                       return_value=1):
                from peerpedia_core.social.exchange import discover_network
                result = discover_network(db, "http://peer:8080", "alice", depth=2)
                assert result["users_discovered"] == 3

    def test_returns_stats_dict(self, db):
        """Returns well-formed stats dict."""
        _make_user(db, "alice", "Alice")
        with patch("peerpedia_core.social.exchange.fetch_following", return_value=[]):
            from peerpedia_core.social.exchange import discover_network
            result = discover_network(db, "http://peer:8080", "alice")
            assert set(result.keys()) == {"users_discovered", "articles_discovered",
                                          "follows_added", "depth_reached", "errors"}
            assert result["errors"] == []


# ── _fetch_with_auth_fallback ────────────────────────────────────────────────


class TestFetchWithAuthFallback:
    """Auth fallback: unauthenticated → Ed25519 on 401/403."""

    def test_returns_data_without_auth(self):
        """Successful unauthenticated fetch returns data immediately."""
        expected = [{"id": "u1"}]
        fetch_fn = lambda s, uid, **kw: expected
        from peerpedia_core.transport._http_core import _fetch_with_auth_fallback
        result = _fetch_with_auth_fallback(fetch_fn, "http://s", "u1")
        assert result == expected

    def test_retries_with_auth_on_401(self):
        """401 ProtocolError triggers Ed25519 auth retry."""
        from peerpedia_core.exceptions import ProtocolError

        call_count = [0]

        def fetch_fn(server, user_id, **kw):
            call_count[0] += 1
            if "private_key_bytes" not in kw:
                raise ProtocolError("unauthorized", status_code=401)
            return [{"id": "u1"}]

        from peerpedia_core.transport._http_core import _fetch_with_auth_fallback
        result = _fetch_with_auth_fallback(
            fetch_fn, "http://s", "u1",
            private_key_bytes=b"\x00" * 32,
            pubkey_hex="00" * 32,
        )
        assert result == [{"id": "u1"}]
        assert call_count[0] == 2

    def test_returns_none_on_transport_error(self):
        """TransportError (network failure) → None (no auth retry)."""
        from peerpedia_core.exceptions import TransportError

        def fetch_fn(server, user_id, **kw):
            raise TransportError("down")

        from peerpedia_core.transport._http_core import _fetch_with_auth_fallback
        result = _fetch_with_auth_fallback(
            fetch_fn, "http://s", "u1",
            private_key_bytes=b"\x00" * 32,
            pubkey_hex="00" * 32,
        )
        assert result is None

    def test_returns_none_on_404(self):
        """404 (None return) → None immediately (no auth retry)."""
        call_count = [0]

        def fetch_fn(server, user_id, **kw):
            call_count[0] += 1
            return None

        from peerpedia_core.transport._http_core import _fetch_with_auth_fallback
        result = _fetch_with_auth_fallback(
            fetch_fn, "http://s", "u1",
            private_key_bytes=b"\x00" * 32,
            pubkey_hex="00" * 32,
        )
        assert result is None
        assert call_count[0] == 1  # No retry — 404 isn't fixed by auth

    def test_no_auth_kwargs_returns_none_on_failure(self):
        """No auth kwargs available → returns None after first failure."""
        from peerpedia_core.exceptions import ProtocolError

        def fetch_fn(server, user_id, **kw):
            raise ProtocolError("unauthorized", status_code=401)

        from peerpedia_core.transport._http_core import _fetch_with_auth_fallback
        result = _fetch_with_auth_fallback(fetch_fn, "http://s", "u1")
        assert result is None
