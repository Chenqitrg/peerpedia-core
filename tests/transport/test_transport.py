# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Spec: Transport facade — mock callbacks verify orchestration contracts.

The ``Transport`` dataclass is a pure interface.  Tests replace real HTTP
callbacks with mocks to verify the call sequences that ``core/`` functions
expect — without needing a running server.
"""

from unittest.mock import Mock

from peerpedia_core.transport import Transport
from peerpedia_core.transport.http.factory import from_http


# ═══════════════════════════════════════════════════════════════════════════════
# Factory smoke test
# ═══════════════════════════════════════════════════════════════════════════════


class TestTransportFactory:
    def test_from_http_returns_transport(self):
        """from_http() MUST return a Transport with all callbacks wired."""
        t = from_http()
        assert isinstance(t, Transport)
        # Every callback slot is filled
        assert callable(t.fetch_head)
        assert callable(t.push_bundle)
        assert callable(t.fetch_bundle)
        assert callable(t.is_online)
        assert callable(t.check_clock_skew)


# ═══════════════════════════════════════════════════════════════════════════════
# Mock callbacks — verify the abstraction is swappable
# ═══════════════════════════════════════════════════════════════════════════════


class TestMockTransport:
    def test_swap_all_callbacks(self):
        """Every callback MUST be replaceable — no hidden coupling to HTTP."""
        m = Mock()
        t = Transport(
            ancestor_probe=m.ancestor_probe,
            fetch_head=m.fetch_head,
            push_bundle=m.push_bundle,
            fetch_bundle=m.fetch_bundle,
            fetch_repo=m.fetch_repo,
            push_repo=m.push_repo,
            fetch_source=m.fetch_source,
            fetch_following=m.fetch_following,
            fetch_followers=m.fetch_followers,
            fetch_shares=m.fetch_shares,
            fetch_notifications=m.fetch_notifications,
            fetch_user_articles=m.fetch_user_articles,
            fetch_search=m.fetch_search,
            fetch_meta=m.fetch_meta,
            fetch_peers=m.fetch_peers,
            fetch_school=m.fetch_school,
            fetch_user=m.fetch_user,
            push_peer_registration=m.push_peer_registration,
            push_follow=m.push_follow,
            push_unfollow=m.push_unfollow,
            push_key_rotation=m.push_key_rotation,
            push_share=m.push_share,
            push_share_remove=m.push_share_remove,
            is_online=m.is_online,
            check_clock_skew=m.check_clock_skew,
        )
        # Call a few and verify they delegate
        t.is_online("http://peer:8080")
        m.is_online.assert_called_once_with("http://peer:8080")

        t.fetch_head("http://peer:8080", "article-1")
        m.fetch_head.assert_called_once_with("http://peer:8080", "article-1")

        t.push_bundle("http://peer:8080", "article-1", b"data")
        m.push_bundle.assert_called_once_with("http://peer:8080", "article-1", b"data")

    def test_first_time_push_when_server_has_no_article(self):
        """Server 404 → local pushes full bundle (first-time upload)."""
        t, m = _mock_transport()
        m.fetch_head.return_value = None
        m.check_clock_skew.return_value = 0

        _simulate_sync(t, "http://s:8080", "a1")
        m.fetch_head.assert_called_once()
        m.push_bundle.assert_called_once()
        m.fetch_bundle.assert_not_called()

    def test_fetch_when_server_ahead(self):
        """Server has newer commits → local fetches bundle from server."""
        t, m = _mock_transport()
        m.fetch_head.return_value = "server-head-hash"
        m.ancestor_probe.return_value = True
        m.fetch_bundle.return_value = b"bundle-data"
        m.check_clock_skew.return_value = 0

        _simulate_sync(t, "http://s:8080", "a1")
        m.fetch_head.assert_called_once()
        m.ancestor_probe.assert_called_once()
        m.fetch_bundle.assert_called_once()
        m.push_bundle.assert_not_called()

    def test_clock_skew_aborts_sync(self):
        """Clock skew >30s MUST abort — no push or fetch happens."""
        t, m = _mock_transport()
        m.check_clock_skew.return_value = 120  # 2 min skew

        _simulate_sync(t, "http://s:8080", "a1")
        m.check_clock_skew.assert_called_once()
        m.fetch_head.assert_not_called()
        m.push_bundle.assert_not_called()
        m.fetch_bundle.assert_not_called()

    def test_peer_offline_skipped(self):
        """When is_online returns False, the peer MUST be skipped entirely."""
        t, m = _mock_transport()
        m.is_online.return_value = False

        _simulate_sync(t, "http://offline:8080", "a1")
        m.is_online.assert_called()
        m.check_clock_skew.assert_not_called()
        m.fetch_head.assert_not_called()

    def test_push_key_rotation(self):
        """After key rotation, push_key_rotation MUST be called with correct args."""
        t, m = _mock_transport()
        t.push_key_rotation("http://peer:8080", "user-1", "new-pubkey-hex")
        m.push_key_rotation.assert_called_once_with(
            "http://peer:8080", "user-1", "new-pubkey-hex")

    def test_social_discover_sequence(self):
        """Discover followers + following MUST call both fetch callbacks."""
        t, m = _mock_transport()
        m.fetch_followers.return_value = [{"id": "u2", "name": "Bob"}]
        m.fetch_following.return_value = [{"id": "u3", "name": "Carol"}]

        followers = t.fetch_followers("http://peer:8080", "u1")
        following = t.fetch_following("http://peer:8080", "u1")

        assert len(followers) == 1
        assert followers[0]["name"] == "Bob"
        assert len(following) == 1
        assert following[0]["name"] == "Carol"
        m.fetch_followers.assert_called_once_with("http://peer:8080", "u1")
        m.fetch_following.assert_called_once_with("http://peer:8080", "u1")

    def test_ancestor_probe_common_ancestor(self):
        """When probe finds common ancestor, fetch_bundle is used for incremental sync."""
        t, m = _mock_transport()
        m.ancestor_probe.return_value = True  # found common ancestor
        m.fetch_head.return_value = "head"
        m.fetch_bundle.return_value = b"incremental"
        m.check_clock_skew.return_value = 0

        _simulate_sync(t, "http://s:8080", "a1")
        # With common ancestor: incremental fetch
        m.fetch_bundle.assert_called_once_with("http://s:8080", "a1", "head")
        m.push_bundle.assert_not_called()

    def test_ancestor_probe_no_common_ancestor(self):
        """When probe finds nothing, full sync (push) happens."""
        t, m = _mock_transport()
        m.ancestor_probe.return_value = False  # no common ancestor
        m.fetch_head.return_value = "head"
        m.check_clock_skew.return_value = 0

        _simulate_sync(t, "http://s:8080", "a1")
        # No common ancestor: full push
        m.ancestor_probe.assert_called_once()
        m.push_bundle.assert_called_once()


# ═══════════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════════

_SERVER = "http://peer:8080"
_ARTICLE = "article-1"


def _mock_transport():
    """Return (Transport, Mock) with all callbacks mocked and is_online=True."""
    m = Mock()
    m.is_online.return_value = True
    m.check_clock_skew.return_value = 0
    m.fetch_head.return_value = None
    t = Transport(
        ancestor_probe=m.ancestor_probe,
        fetch_head=m.fetch_head,
        push_bundle=m.push_bundle,
        fetch_bundle=m.fetch_bundle,
        fetch_repo=m.fetch_repo,
        push_repo=m.push_repo,
        fetch_source=m.fetch_source,
        fetch_following=m.fetch_following,
        fetch_followers=m.fetch_followers,
        fetch_shares=m.fetch_shares,
        fetch_notifications=m.fetch_notifications,
        fetch_user_articles=m.fetch_user_articles,
        fetch_search=m.fetch_search,
        fetch_meta=m.fetch_meta,
        fetch_peers=m.fetch_peers,
        fetch_school=m.fetch_school,
        fetch_user=m.fetch_user,
        push_peer_registration=m.push_peer_registration,
        push_follow=m.push_follow,
        push_unfollow=m.push_unfollow,
        push_key_rotation=m.push_key_rotation,
        push_share=m.push_share,
        push_share_remove=m.push_share_remove,
        is_online=m.is_online,
        check_clock_skew=m.check_clock_skew,
    )
    return t, m


def _simulate_sync(t, server, article_id):
    """Simulate core/sync_article's callback sequence."""
    if not t.is_online(server):
        return
    skew = t.check_clock_skew(server)
    if skew and abs(skew) > 30:
        return  # hard block
    head = t.fetch_head(server, article_id)
    if head is None:
        t.push_bundle(server, article_id, b"bundle-data")
        return
    if t.ancestor_probe(server, article_id, head):
        t.fetch_bundle(server, article_id, head)
    else:
        t.push_bundle(server, article_id, b"bundle-data")
