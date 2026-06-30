# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

r"""Spec: Sync and network journey tests.

STATUS: LOCKED

Tests peer-to-peer sync workflows through the Transport boundary.
Mocks the Transport dataclass callbacks (the network edge), not
deep-internal functions like ``sync_article``.

Each test tells a complete P2P story: multi-peer sync, clock skew,
peer discovery, announcement, backoff, and error recovery.
"""

from unittest.mock import Mock, patch

import pytest

from tests.app.conftest import login
from peerpedia_core.app.commands.sync import (
    announce_to_peers,
    sync_all,
    sync_all_peers,
    sync_and_discover,
    sync_one,
)
from peerpedia_core.app.commands.bundle import (
    sync_discover,
    sync_pull,
    sync_status,
)
from peerpedia_core.exceptions import (
    ConflictError, ProtocolError, TransportError,
)
from peerpedia_core.time import REPLAY_WINDOW_SECONDS


# ── Helpers ────────────────────────────────────────────────────────────────

def _make_transport(**overrides):
    """Build a Transport with sensible defaults, override as needed."""
    defaults = dict(
        ancestor_probe=Mock(return_value=None),
        fetch_head=Mock(return_value=None),
        push_bundle=Mock(),
        fetch_bundle=Mock(return_value=None),
        fetch_repo=Mock(return_value=None),
        push_repo=Mock(return_value=True),
        fetch_source=Mock(return_value=None),
        fetch_following=Mock(return_value=[]),
        fetch_followers=Mock(return_value=[]),
        fetch_shares=Mock(return_value=[]),
        fetch_notifications=Mock(return_value=[]),
        fetch_user_articles=Mock(return_value=[]),
        fetch_search=Mock(return_value=[]),
        fetch_meta=Mock(return_value=None),
        fetch_peers=Mock(return_value=[]),
        fetch_school=Mock(return_value=[]),
        fetch_user=Mock(return_value=None),
        push_peer_registration=Mock(return_value=True),
        push_follow=Mock(return_value=True),
        push_unfollow=Mock(return_value=True),
        push_key_rotation=Mock(return_value=True),
        push_share=Mock(return_value=True),
        push_share_remove=Mock(return_value=True),
        is_online=Mock(return_value=True),
        check_clock_skew=Mock(return_value=0),
    )
    defaults.update(overrides)
    from peerpedia_core.transport import Transport
    return Transport(**defaults)


def _create_and_publish(ctx, title="Paper", content="# P"):
    """Create article, publish, return (ctx, article_id)."""
    from peerpedia_core.app.commands.article import create, publish
    a = create(ctx, title=title, content=content)
    publish(ctx, article_ref=a.data["id"],
            scores_str="orig=4,rigor=4,comp=4,ped=4,imp=4")
    return a.data["id"]


# ═══════════════════════════════════════════════════════════════════════════════
# J38 — Single peer sync: online → sync → verify transport calls
# ═══════════════════════════════════════════════════════════════════════════════


class TestSyncOnePeer:
    """Sync one article to one peer, exercising the transport layer."""

    def test_sync_one_success(self, db, articles_dir):
        """sync_one calls sync_article → commits → returns True."""
        transport = _make_transport(
            fetch_head=Mock(return_value={"hash": "abc123"}),
            ancestor_probe=Mock(return_value=True),
            fetch_bundle=Mock(return_value=b"fake-bundle"),
        )

        with patch("peerpedia_core.app.commands.sync.sync_article") as mock_sa:
            mock_sa.return_value = {"synced": True}
            result = sync_one(db, transport, "peer.example.com", "art-1")

        assert result is True
        mock_sa.assert_called_once_with(db, transport, "peer.example.com", "art-1")

    def test_sync_one_no_change(self, db, articles_dir):
        """sync_article returns synced=False → sync_one returns False."""
        transport = _make_transport()

        with patch("peerpedia_core.app.commands.sync.sync_article") as mock_sa:
            mock_sa.return_value = {"synced": False}
            result = sync_one(db, transport, "peer.example.com", "art-1")

        assert result is False

    def test_sync_one_transport_error(self, db, articles_dir):
        """Network error → False, no crash."""
        transport = _make_transport()

        with patch("peerpedia_core.app.commands.sync.sync_article") as mock_sa:
            mock_sa.side_effect = TransportError("connection refused")
            result = sync_one(db, transport, "peer.example.com", "art-1")

        assert result is False

    def test_sync_one_conflict_error(self, db, articles_dir):
        """ConflictError is caught and returns False."""
        transport = _make_transport()

        with patch("peerpedia_core.app.commands.sync.sync_article") as mock_sa:
            mock_sa.side_effect = ConflictError("merge conflict")
            result = sync_one(db, transport, "peer.example.com", "art-1")

        assert result is False

    def test_sync_one_protocol_error(self, db, articles_dir):
        """ProtocolError is caught and returns False."""
        transport = _make_transport()

        with patch("peerpedia_core.app.commands.sync.sync_article") as mock_sa:
            mock_sa.side_effect = ProtocolError("bad version")
            result = sync_one(db, transport, "peer.example.com", "art-1")

        assert result is False


# ═══════════════════════════════════════════════════════════════════════════════
# J39 — Multi-peer sync with mixed states
# ═══════════════════════════════════════════════════════════════════════════════


class TestMultiPeerSync:
    """Sync across multiple peers — online, offline, clock-skewed."""

    def test_offline_peer_skipped(self, db, articles_dir):
        """Offline peer → on_peer_skip called with 'offline'."""
        transport = _make_transport(is_online=Mock(return_value=False))
        skip_calls = []

        with patch("peerpedia_core.app.commands.sync.get_known_peers") as mock_gp:
            mock_gp.return_value = ["peer-offline.example.com"]
            sync_all_peers(db, transport, on_peer_skip=lambda url, reason: skip_calls.append((url, reason)))

        assert skip_calls == [("peer-offline.example.com", "offline")]

    def test_clock_skewed_peer_skipped(self, db, articles_dir):
        """Peer with large clock skew → on_peer_skip called with 'clock_skew'."""
        transport = _make_transport(
            is_online=Mock(return_value=True),
            check_clock_skew=Mock(return_value=REPLAY_WINDOW_SECONDS + 10),
        )
        skip_calls = []

        with patch("peerpedia_core.app.commands.sync.get_known_peers") as mock_gp:
            mock_gp.return_value = ["peer-skewed.example.com"]
            sync_all_peers(db, transport, on_peer_skip=lambda url, reason: skip_calls.append((url, reason)))

        assert len(skip_calls) == 1
        assert skip_calls[0][1] == "clock_skew"

    def test_clock_within_window_proceeds(self, db, articles_dir):
        """Clock skew within ±30s → sync proceeds."""
        transport = _make_transport(
            is_online=Mock(return_value=True),
            check_clock_skew=Mock(return_value=20),  # within window
        )

        with patch("peerpedia_core.app.commands.sync.get_known_peers") as mock_gp:
            mock_gp.return_value = ["peer-ok.example.com"]
            with patch("peerpedia_core.app.commands.sync.sync_all") as mock_sa:
                mock_sa.return_value = 3
                sync_all_peers(db, transport)

        mock_sa.assert_called_once()

    def test_null_clock_skew_proceeds(self, db, articles_dir):
        """None clock skew (unknown) → proceeds (conservative)."""
        transport = _make_transport(
            is_online=Mock(return_value=True),
            check_clock_skew=Mock(return_value=None),
        )

        with patch("peerpedia_core.app.commands.sync.get_known_peers") as mock_gp:
            mock_gp.return_value = ["peer-null.example.com"]
            with patch("peerpedia_core.app.commands.sync.sync_all") as mock_sa:
                mock_sa.return_value = 0
                sync_all_peers(db, transport)

        mock_sa.assert_called_once()

    def test_mixed_peers_online_offline_skewed(self, db, articles_dir):
        """Three peers: one online, one offline, one skewed.
        Only the online one syncs."""
        # side_effect uses the server name to determine behavior
        def _is_online(server):
            # peer-offline is offline; peer-skewed and peer-online are online
            return server != "peer-offline.example.com"

        def _check_skew(server):
            if server == "peer-skewed.example.com":
                return 999
            return 0

        transport = _make_transport(
            is_online=Mock(side_effect=_is_online),
            check_clock_skew=Mock(side_effect=_check_skew),
        )

        skip_calls = []
        done_calls = []

        with patch("peerpedia_core.app.commands.sync.get_known_peers") as mock_gp:
            mock_gp.return_value = [
                "peer-offline.example.com",
                "peer-skewed.example.com",
                "peer-online.example.com",
            ]
            with patch("peerpedia_core.app.commands.sync.sync_all") as mock_sa:
                mock_sa.return_value = 5
                with patch("peerpedia_core.app.commands.sync.record_peer_result"):
                    sync_all_peers(
                        db, transport,
                        on_peer_skip=lambda url, reason: skip_calls.append((url, reason)),
                        on_peer_done=lambda url, count: done_calls.append((url, count)),
                    )

        # One succeeded, two skipped (one offline, one clock-skewed)
        assert len(done_calls) == 1
        assert done_calls[0] == ("peer-online.example.com", 5)
        assert len(skip_calls) == 2
        reasons = {r for _, r in skip_calls}
        assert reasons == {"offline", "clock_skew"}


# ═══════════════════════════════════════════════════════════════════════════════
# J40 — Network error during peer sync
# ═══════════════════════════════════════════════════════════════════════════════


class TestSyncNetworkErrors:
    """Network errors at various stages don't crash the peer loop."""

    def test_is_online_crash_calls_error_handler(self, db, articles_dir):
        """is_online throws → on_peer_error called."""
        transport = _make_transport(
            is_online=Mock(side_effect=TransportError("network down")),
        )
        error_calls = []

        with patch("peerpedia_core.app.commands.sync.get_known_peers") as mock_gp:
            mock_gp.return_value = ["peer1.example.com"]
            with patch("peerpedia_core.app.commands.sync.record_peer_result"):
                sync_all_peers(db, transport,
                               on_peer_error=lambda e: error_calls.append(e))

        assert len(error_calls) == 1
        assert isinstance(error_calls[0], TransportError)

    def test_sync_all_crash_calls_error_handler(self, db, articles_dir):
        """sync_all throws mid-sync → on_peer_error called."""
        transport = _make_transport(
            is_online=Mock(return_value=True),
            check_clock_skew=Mock(return_value=0),
        )
        error_calls = []

        with patch("peerpedia_core.app.commands.sync.get_known_peers") as mock_gp:
            mock_gp.return_value = ["peer1.example.com"]
            with patch("peerpedia_core.app.commands.sync.sync_all") as mock_sa:
                mock_sa.side_effect = ProtocolError("protocol mismatch")
                with patch("peerpedia_core.app.commands.sync.record_peer_result"):
                    sync_all_peers(db, transport,
                                   on_peer_error=lambda e: error_calls.append(e))

        assert len(error_calls) == 1
        assert isinstance(error_calls[0], ProtocolError)

    def test_discover_error_does_not_crash_peer_loop(self, db, articles_dir):
        """Discover fails on one peer → other peers still sync."""
        transport = _make_transport(
            is_online=Mock(return_value=True),
            check_clock_skew=Mock(return_value=0),
        )

        with patch("peerpedia_core.app.commands.sync.get_known_peers") as mock_gp:
            mock_gp.return_value = ["peer1.example.com", "peer2.example.com"]
            with patch("peerpedia_core.app.commands.sync.sync_all") as mock_sa:
                mock_sa.return_value = 0
                with patch("peerpedia_core.app.commands.sync.discover_articles") as mock_disc:
                    mock_disc.side_effect = TransportError("discover failed")
                    with patch("peerpedia_core.app.commands.sync.record_peer_result"):
                        sync_all_peers(db, transport, user_id="u1")

        # Both peers attempted despite discover errors
        assert mock_sa.call_count == 2

    def test_second_peer_still_syncs_after_first_fails(self, db, articles_dir):
        """First peer throws, second peer syncs normally."""
        def _is_online(server):
            if server == "bad.example.com":
                raise TransportError("unreachable")
            return True

        transport = _make_transport(is_online=Mock(side_effect=_is_online))
        done_calls = []

        with patch("peerpedia_core.app.commands.sync.get_known_peers") as mock_gp:
            mock_gp.return_value = ["bad.example.com", "good.example.com"]
            with patch("peerpedia_core.app.commands.sync.sync_all") as mock_sa:
                mock_sa.return_value = 3
                with patch("peerpedia_core.app.commands.sync.record_peer_result"):
                    sync_all_peers(db, transport,
                                   on_peer_done=lambda url, count: done_calls.append((url, count)))

        assert len(done_calls) == 1
        assert done_calls[0][0] == "good.example.com"


# ═══════════════════════════════════════════════════════════════════════════════
# J41 — Pull new articles from server (discovery during sync)
# ═══════════════════════════════════════════════════════════════════════════════


class TestPullNewArticles:
    """Server has articles we don't → pull them."""

    def test_pulls_new_article_not_in_local_db(self, ctx, articles_dir):
        """fetch_search returns article not in DB → pull_new_article called."""
        alice = login(ctx, "AlicePull")
        ctx.transport.fetch_search.return_value = [
            {"id": "remote-article-1", "title": "Remote Paper",
             "status": "draft", "authors": [], "publish_consents": []},
        ]

        with patch("peerpedia_core.app.commands.bundle.pull_new_article") as mock_pull:
            with patch("peerpedia_core.app.commands.bundle.sync_article"):
                sync_pull(alice, server="peer.example.com")

        mock_pull.assert_called_once()
        assert mock_pull.call_args[0][3] == "remote-article-1"

    def test_skips_article_already_in_local_db(self, ctx, articles_dir):
        """Article already in DB → not pulled again."""
        from peerpedia_core.app.commands.article import create
        alice = login(ctx, "AliceSkip")
        a = create(alice, title="Local Paper", content="# L")
        local_id = a.data["id"]

        ctx.transport.fetch_search.return_value = [
            {"id": local_id, "title": "Local Paper",
             "status": "draft", "authors": [], "publish_consents": []},
        ]

        with patch("peerpedia_core.app.commands.bundle.pull_new_article") as mock_pull:
            with patch("peerpedia_core.app.commands.bundle.sync_article"):
                sync_pull(alice, server="peer.example.com")

        mock_pull.assert_not_called()

    def test_empty_search_no_pull(self, ctx):
        """Empty search results → no pull attempted."""
        alice = login(ctx, "AliceEmpty")
        ctx.transport.fetch_search.return_value = []

        with patch("peerpedia_core.app.commands.bundle.pull_new_article") as mock_pull:
            with patch("peerpedia_core.app.commands.bundle.sync_article"):
                sync_pull(alice, server="peer.example.com")

        mock_pull.assert_not_called()

    def test_none_search_no_pull(self, ctx):
        """None search results → no pull attempted."""
        alice = login(ctx, "AliceNone")
        ctx.transport.fetch_search.return_value = None

        with patch("peerpedia_core.app.commands.bundle.pull_new_article") as mock_pull:
            with patch("peerpedia_core.app.commands.bundle.sync_article"):
                sync_pull(alice, server="peer.example.com")

        mock_pull.assert_not_called()


# ═══════════════════════════════════════════════════════════════════════════════
# J42 — sync_status: online/offline detection
# ═══════════════════════════════════════════════════════════════════════════════


class TestSyncStatus:
    """Check online/offline status through transport."""

    def test_server_online(self, ctx):
        ctx.transport.is_online.return_value = True
        result = sync_status(ctx, server="peer.example.com")
        assert result.data["online"] is True
        assert result.data["server"] == "peer.example.com"

    def test_server_offline(self, ctx):
        ctx.transport.is_online.return_value = False
        result = sync_status(ctx, server="peer.example.com")
        assert result.data["online"] is False

    def test_server_timeout_treated_offline(self, ctx):
        """Timeout → is_online returns False → offline reported."""
        ctx.transport.is_online.return_value = False
        result = sync_status(ctx, server="slow-peer.example.com")
        assert result.data["online"] is False


# ═══════════════════════════════════════════════════════════════════════════════
# J43 — Peer discovery: merge peers from server
# ═══════════════════════════════════════════════════════════════════════════════


class TestPeerDiscovery:
    """Discover and merge peers from the network."""

    def test_merge_peers_adds_new(self):
        """New peers from remote → added to local list."""
        transport = _make_transport(
            fetch_peers=Mock(return_value=["https://new-peer.example.com"]),
        )

        with patch("peerpedia_core.storage.peers._load_peers_raw") as mock_load:
            mock_load.return_value = []
            with patch("peerpedia_core.storage.peers._save_peers_raw") as mock_save:
                from peerpedia_core.storage.peers import merge_peers
                count = merge_peers(transport, "seed.example.com")

        assert count == 1
        mock_save.assert_called_once()

    def test_merge_peers_skips_duplicates(self):
        """Already-known peers → not added again."""
        transport = _make_transport(
            fetch_peers=Mock(return_value=["https://known.example.com"]),
        )

        with patch("peerpedia_core.storage.peers._load_peers_raw") as mock_load:
            mock_load.return_value = ["https://known.example.com"]
            with patch("peerpedia_core.storage.peers._save_peers_raw") as mock_save:
                from peerpedia_core.storage.peers import merge_peers
                count = merge_peers(transport, "seed.example.com")

        assert count == 0

    def test_merge_peers_network_error_returns_zero(self):
        """Transport fails → return 0, don't crash."""
        transport = _make_transport(
            fetch_peers=Mock(side_effect=TransportError("timeout")),
        )

        from peerpedia_core.storage.peers import merge_peers
        count = merge_peers(transport, "seed.example.com")
        assert count == 0


# ═══════════════════════════════════════════════════════════════════════════════
# J44 — Announce to peers: register server URL with known peers
# ═══════════════════════════════════════════════════════════════════════════════


class TestAnnounceToPeers:
    """Server announces itself to seed and known peers."""

    def test_announce_merges_seeds_and_registers(self):
        """Both seed merge and peer registration happen."""
        transport = _make_transport(
            fetch_peers=Mock(return_value=["https://other.example.com"]),
            push_peer_registration=Mock(return_value=True),
        )

        with patch("peerpedia_core.app.commands.sync.get_known_peers") as mock_gp:
            mock_gp.return_value = ["https://peer1.example.com"]
            seeds_merged, peers_announced = announce_to_peers(
                transport, "https://me.example.com")

        # Seeds merged depends on seed_peers config
        assert isinstance(seeds_merged, int)
        assert peers_announced == 1

    def test_announce_peer_registration_failure_is_silent(self):
        """If push_peer_registration fails for one peer, others still tried."""
        def _push(peer, url):
            if "bad" in peer:
                raise TransportError("refused")
            return True

        transport = _make_transport(
            push_peer_registration=Mock(side_effect=_push),
        )

        with patch("peerpedia_core.app.commands.sync.get_known_peers") as mock_gp:
            mock_gp.return_value = [
                "https://bad.example.com",
                "https://good.example.com",
            ]
            seeds_merged, peers_announced = announce_to_peers(
                transport, "https://me.example.com")

        assert peers_announced == 1

    def test_announce_no_peers(self):
        """No known peers → 0 announced."""
        transport = _make_transport()

        with patch("peerpedia_core.app.commands.sync.get_known_peers") as mock_gp:
            mock_gp.return_value = []
            seeds_merged, peers_announced = announce_to_peers(
                transport, "https://me.example.com")

        assert peers_announced == 0


# ═══════════════════════════════════════════════════════════════════════════════
# J45 — sync_and_discover: sync then discover in one call
# ═══════════════════════════════════════════════════════════════════════════════


class TestSyncAndDiscover:
    """Combined sync+discover orchestration."""

    def test_syncs_then_discovers(self, db, articles_dir):
        transport = _make_transport()

        with patch("peerpedia_core.app.commands.sync.sync_all") as mock_sync:
            mock_sync.return_value = 3
            with patch("peerpedia_core.app.commands.sync.discover_articles") as mock_disc:
                mock_disc.return_value = 5
                sync_and_discover(db, transport, "peer.example.com", user_id="u1")

        mock_sync.assert_called_once()
        mock_disc.assert_called_once_with(db, transport, "peer.example.com", "u1")

    def test_on_synced_callback_passed_to_sync_all(self, db, articles_dir):
        """on_synced is forwarded to sync_all.  When an article syncs,
        sync_all invokes the callback with the running count."""
        transport = _make_transport()
        cb = Mock()

        with patch("peerpedia_core.app.commands.sync._iter_local_syncable") as mock_iter:
            mock_iter.return_value = ["art-1", "art-2", "art-3"]
            with patch("peerpedia_core.app.commands.sync.sync_one") as mock_one:
                # All succeed → callback fires 3 times with counts 1,2,3
                mock_one.return_value = True
                sync_all(db, transport, "peer.example.com",
                         pre_check=False, on_synced=cb)

        assert cb.call_count == 3
        assert cb.call_args_list == [((1,),), ((2,),), ((3,),)]

    def test_on_discovered_fires_when_articles_found(self, db, articles_dir):
        transport = _make_transport()
        cb = Mock()

        with patch("peerpedia_core.app.commands.sync.sync_all") as mock_sync:
            mock_sync.return_value = 0
            with patch("peerpedia_core.app.commands.sync.discover_articles") as mock_disc:
                mock_disc.return_value = 7
                sync_and_discover(db, transport, "peer.example.com",
                                  user_id="u1", on_discovered=cb)

        cb.assert_called_once_with(7)

    def test_on_discovered_not_called_when_zero(self, db, articles_dir):
        transport = _make_transport()
        cb = Mock()

        with patch("peerpedia_core.app.commands.sync.sync_all") as mock_sync:
            mock_sync.return_value = 0
            with patch("peerpedia_core.app.commands.sync.discover_articles") as mock_disc:
                mock_disc.return_value = 0
                sync_and_discover(db, transport, "peer.example.com",
                                  user_id="u1", on_discovered=cb)

        cb.assert_not_called()

    def test_network_error_calls_on_error(self, db, articles_dir):
        transport = _make_transport()
        cb = Mock()

        with patch("peerpedia_core.app.commands.sync.sync_all") as mock_sync:
            mock_sync.side_effect = TransportError("timeout")
            sync_and_discover(db, transport, "peer.example.com",
                              user_id="u1", on_error=cb)

        cb.assert_called_once()
        assert isinstance(cb.call_args[0][0], TransportError)


# ═══════════════════════════════════════════════════════════════════════════════
# J46 — Callback orchestration: all callbacks in the right order
# ═══════════════════════════════════════════════════════════════════════════════


class TestCallbackOrchestration:
    """Full lifecycle: start → sync → discover → done."""

    def test_full_callback_order(self, db, articles_dir):
        """Verify on_peer_start → on_peer_discover → on_peer_done in order.
        on_synced is internal to sync_all, not exposed by sync_all_peers."""
        transport = _make_transport(
            is_online=Mock(return_value=True),
            check_clock_skew=Mock(return_value=0),
        )

        events = []

        def _start(server):
            events.append(("start", server))

        def _discover(count):
            if count:
                events.append(("discover", count))

        def _done(server, count):
            events.append(("done", server, count))

        with patch("peerpedia_core.app.commands.sync.get_known_peers") as mock_gp:
            mock_gp.return_value = ["peer.example.com"]
            with patch("peerpedia_core.app.commands.sync.sync_all") as mock_sync:
                mock_sync.return_value = 4
                with patch("peerpedia_core.app.commands.sync.discover_articles") as mock_disc:
                    mock_disc.return_value = 2
                    with patch("peerpedia_core.app.commands.sync.record_peer_result"):
                        sync_all_peers(
                            db, transport, user_id="u1",
                            on_peer_start=_start,
                            on_peer_discover=_discover,
                            on_peer_done=_done,
                        )

        assert events[0] == ("start", "peer.example.com")
        assert ("discover", 2) in events
        assert events[-1] == ("done", "peer.example.com", 4)

    def test_no_discover_when_no_user_id(self, db, articles_dir):
        """Without user_id, discover is skipped entirely."""
        transport = _make_transport(
            is_online=Mock(return_value=True),
            check_clock_skew=Mock(return_value=0),
        )

        with patch("peerpedia_core.app.commands.sync.get_known_peers") as mock_gp:
            mock_gp.return_value = ["peer.example.com"]
            with patch("peerpedia_core.app.commands.sync.sync_all") as mock_sync:
                mock_sync.return_value = 3
                with patch("peerpedia_core.app.commands.sync.discover_articles") as mock_disc:
                    with patch("peerpedia_core.app.commands.sync.record_peer_result"):
                        sync_all_peers(db, transport)  # no user_id

        mock_sync.assert_called_once()
        mock_disc.assert_not_called()


# ═══════════════════════════════════════════════════════════════════════════════
# J47 — Backoff behavior: failed peers back off, successful ones reset
# ═══════════════════════════════════════════════════════════════════════════════


class TestPeerBackoff:
    """Exponential backoff for failed peers."""

    def test_record_peer_failure_increments_backoff(self):
        """A failed peer enters backoff state."""
        from peerpedia_core.storage.peers import (
            _peer_failed, _peer_succeeded, _is_peer_backoff, _ensure_backoff_hydrated,
        )

        # Hydrate state
        _ensure_backoff_hydrated()

        url = "https://flaky.example.com"
        _peer_succeeded(url)  # ensure clean state

        assert not _is_peer_backoff(url)

        _peer_failed(url)
        assert _is_peer_backoff(url)

        # Cleanup
        _peer_succeeded(url)

    def test_record_peer_success_resets_backoff(self):
        """A successful connection resets backoff."""
        from peerpedia_core.storage.peers import (
            _peer_failed, _peer_succeeded, _is_peer_backoff, _ensure_backoff_hydrated,
        )

        _ensure_backoff_hydrated()

        url = "https://recovery.example.com"
        _peer_succeeded(url)  # clean

        _peer_failed(url)
        assert _is_peer_backoff(url)

        _peer_succeeded(url)
        assert not _is_peer_backoff(url)

    def test_record_peer_result_routes_to_correct_function(self):
        """record_peer_result dispatches to _peer_succeeded or _peer_failed."""
        from peerpedia_core.storage.peers import (
            _peer_succeeded, _peer_failed,
            _is_peer_backoff, _ensure_backoff_hydrated,
            record_peer_result,
        )

        _ensure_backoff_hydrated()

        url = "https://result.example.com"
        _peer_succeeded(url)

        record_peer_result(url, success=False)
        assert _is_peer_backoff(url)

        record_peer_result(url, success=True)
        assert not _is_peer_backoff(url)


# ═══════════════════════════════════════════════════════════════════════════════
# J48 — sync_discover: graph walk depth control
# ═══════════════════════════════════════════════════════════════════════════════


class TestSyncDiscover:
    """Network discovery with depth and user limits."""

    def test_passes_depth_and_max_users(self, ctx):
        alice = login(ctx, "AliceDisc")

        with patch("peerpedia_core.app.commands.bundle.discover_network") as mock_dn:
            mock_dn.return_value = {"users": 5, "articles": 10}
            sync_discover(alice, server="peer.example.com", depth=3, max_users=50)

        kwargs = mock_dn.call_args[1]
        assert kwargs["depth"] == 3
        assert kwargs["max_users"] == 50

    def test_passes_signing_context(self, ctx):
        alice = login(ctx, "AliceSign")

        with patch("peerpedia_core.app.commands.bundle.discover_network") as mock_dn:
            mock_dn.return_value = {}
            sync_discover(alice, server="peer.example.com")

        kwargs = mock_dn.call_args[1]
        assert kwargs["signing_key_bytes"] == alice.signing_key_bytes
        assert kwargs["pubkey_hex"] == alice.pubkey_hex

    def test_requires_authentication(self, ctx):
        with pytest.raises(Exception, match="UNAUTHORIZED"):
            sync_discover(ctx, server="peer.example.com")

    def test_commits_after_discover(self, ctx):
        """DB is committed after successful discover."""
        alice = login(ctx, "AliceCommit")

        with patch("peerpedia_core.app.commands.bundle.discover_network") as mock_dn:
            mock_dn.return_value = {"users": 2, "articles": 3}
            with patch.object(ctx.db, "commit") as mock_commit:
                sync_discover(alice, server="peer.example.com")

        mock_commit.assert_called_once()
