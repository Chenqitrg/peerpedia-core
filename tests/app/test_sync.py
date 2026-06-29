# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Spec: Sync orchestration — sync_one, sync_all, sync_and_discover, sync_all_peers."""

from unittest.mock import Mock, patch

import pytest

from peerpedia_core.app.commands.sync import (
    _iter_local_syncable,
    _skip_if_unknown,
    sync_all,
    sync_all_peers,
    sync_and_discover,
    sync_one,
)
from peerpedia_core.exceptions import ConflictError, ProtocolError, TransportError


# ═══════════════════════════════════════════════════════════════════════════════
# _iter_local_syncable
# ═══════════════════════════════════════════════════════════════════════════════


class TestIterLocalSyncable:
    def test_empty_dir(self, articles_dir):
        with patch("peerpedia_core.app.commands.sync.ARTICLES_DIR", articles_dir):
            assert _iter_local_syncable() == []

    def test_includes_dirs_with_dotgit(self, articles_dir):
        (articles_dir / "art-1" / ".git").mkdir(parents=True)
        (articles_dir / "art-2" / ".git").mkdir(parents=True)
        (articles_dir / "not-an-article").mkdir()
        with patch("peerpedia_core.app.commands.sync.ARTICLES_DIR", articles_dir):
            result = _iter_local_syncable()
        assert set(result) == {"art-1", "art-2"}

    def test_excludes_dirs_without_dotgit(self, articles_dir):
        (articles_dir / "plain-dir").mkdir()
        with patch("peerpedia_core.app.commands.sync.ARTICLES_DIR", articles_dir):
            assert _iter_local_syncable() == []


# ═══════════════════════════════════════════════════════════════════════════════
# _skip_if_unknown
# ═══════════════════════════════════════════════════════════════════════════════


class TestSkipIfUnknown:
    def test_article_unknown_on_server(self, transport):
        """fetch_head returns None → skip (return True)."""
        transport.fetch_head.return_value = None
        assert _skip_if_unknown(transport, "srv", "art-1") is True

    def test_article_known_on_server(self, transport):
        """fetch_head returns data → don't skip (return False)."""
        transport.fetch_head.return_value = {"hash": "abc123"}
        assert _skip_if_unknown(transport, "srv", "art-1") is False

    def test_network_error_is_treated_as_unknown(self, transport):
        """Any network error → skip (return True)."""
        transport.fetch_head.side_effect = TransportError("timeout")
        assert _skip_if_unknown(transport, "srv", "art-1") is True

    def test_connection_error_is_treated_as_unknown(self, transport):
        transport.fetch_head.side_effect = ConnectionError("refused")
        assert _skip_if_unknown(transport, "srv", "art-1") is True

    def test_os_error_is_treated_as_unknown(self, transport):
        transport.fetch_head.side_effect = OSError("network down")
        assert _skip_if_unknown(transport, "srv", "art-1") is True


# ═══════════════════════════════════════════════════════════════════════════════
# sync_one
# ═══════════════════════════════════════════════════════════════════════════════


class TestSyncOne:
    def test_synced_commits_and_returns_true(self, db, transport):
        with patch("peerpedia_core.app.commands.sync.sync_article") as mock_s:
            mock_s.return_value = {"synced": True}
            result = sync_one(db, transport, "srv", "art-1")

        assert result is True
        mock_s.assert_called_once_with(db, transport, "srv", "art-1")

    def test_not_synced_returns_false(self, db, transport):
        with patch("peerpedia_core.app.commands.sync.sync_article") as mock_s:
            mock_s.return_value = {"synced": False}
            result = sync_one(db, transport, "srv", "art-1")

        assert result is False

    def test_transport_error_returns_false(self, db, transport):
        with patch("peerpedia_core.app.commands.sync.sync_article") as mock_s:
            mock_s.side_effect = TransportError("timeout")
            result = sync_one(db, transport, "srv", "art-1")

        assert result is False

    def test_protocol_error_returns_false(self, db, transport):
        with patch("peerpedia_core.app.commands.sync.sync_article") as mock_s:
            mock_s.side_effect = ProtocolError("bad protocol")
            result = sync_one(db, transport, "srv", "art-1")

        assert result is False

    def test_conflict_error_returns_false(self, db, transport):
        with patch("peerpedia_core.app.commands.sync.sync_article") as mock_s:
            mock_s.side_effect = ConflictError("merge conflict")
            result = sync_one(db, transport, "srv", "art-1")

        assert result is False


# ═══════════════════════════════════════════════════════════════════════════════
# sync_all
# ═══════════════════════════════════════════════════════════════════════════════


class TestSyncAll:
    def test_no_articles_returns_zero(self, db, transport):
        with patch("peerpedia_core.app.commands.sync._iter_local_syncable") as mock_iter:
            mock_iter.return_value = []
            result = sync_all(db, transport, "srv")

        assert result == 0

    def test_syncs_each_article(self, db, transport):
        with patch("peerpedia_core.app.commands.sync._iter_local_syncable") as mock_iter:
            mock_iter.return_value = ["art-1", "art-2"]
            with patch("peerpedia_core.app.commands.sync.sync_one") as mock_one:
                mock_one.return_value = True
                result = sync_all(db, transport, "srv", pre_check=False)

        assert result == 2
        assert mock_one.call_count == 2

    def test_pre_check_skips_unknown(self, db, transport):
        """With pre_check=True, unknown articles are skipped before sync_one."""
        with patch("peerpedia_core.app.commands.sync._iter_local_syncable") as mock_iter:
            mock_iter.return_value = ["art-1", "art-2"]
            with patch("peerpedia_core.app.commands.sync.sync_one") as mock_one:
                mock_one.return_value = True
                with patch("peerpedia_core.app.commands.sync._skip_if_unknown") as mock_skip:
                    # art-1 unknown → skip, art-2 known → sync
                    mock_skip.side_effect = [True, False]
                    result = sync_all(db, transport, "srv", pre_check=True)

        assert result == 1
        mock_one.assert_called_once_with(db, transport, "srv", "art-2")

    def test_calls_on_synced_callback(self, db, transport):
        cb = Mock()
        with patch("peerpedia_core.app.commands.sync._iter_local_syncable") as mock_iter:
            mock_iter.return_value = ["art-1", "art-2", "art-3"]
            with patch("peerpedia_core.app.commands.sync.sync_one") as mock_one:
                mock_one.side_effect = [True, False, True]
                sync_all(db, transport, "srv", pre_check=False, on_synced=cb)

        # Called with cumulative count after each success: 1, then 2
        assert cb.call_args_list == [((1,),), ((2,),)]

    def test_counts_only_successful_syncs(self, db, transport):
        with patch("peerpedia_core.app.commands.sync._iter_local_syncable") as mock_iter:
            mock_iter.return_value = ["art-1", "art-2", "art-3"]
            with patch("peerpedia_core.app.commands.sync.sync_one") as mock_one:
                mock_one.side_effect = [True, True, False]
                result = sync_all(db, transport, "srv", pre_check=False)

        assert result == 2


# ═══════════════════════════════════════════════════════════════════════════════
# sync_and_discover
# ═══════════════════════════════════════════════════════════════════════════════


class TestSyncAndDiscover:
    def test_syncs_then_discovers(self, db, transport):
        with patch("peerpedia_core.app.commands.sync.sync_all") as mock_sync:
            mock_sync.return_value = 3
            with patch("peerpedia_core.app.commands.sync.discover_articles") as mock_disc:
                mock_disc.return_value = 5
                sync_and_discover(db, transport, "srv", user_id="u1")

        mock_sync.assert_called_once()
        mock_disc.assert_called_once_with(db, transport, "srv", "u1")

    def test_passes_on_synced_to_sync_all(self, db, transport):
        """on_synced callback is forwarded to sync_all."""
        cb = Mock()
        with patch("peerpedia_core.app.commands.sync.sync_all") as mock_sync:
            mock_sync.return_value = 3
            with patch("peerpedia_core.app.commands.sync.discover_articles") as mock_disc:
                mock_disc.return_value = 0
                sync_and_discover(db, transport, "srv", user_id="u1", on_synced=cb)

        # Verify on_synced was passed through to sync_all
        assert mock_sync.call_args[1]["on_synced"] is cb

    def test_calls_on_discovered(self, db, transport):
        cb = Mock()
        with patch("peerpedia_core.app.commands.sync.sync_all") as mock_sync:
            mock_sync.return_value = 0
            with patch("peerpedia_core.app.commands.sync.discover_articles") as mock_disc:
                mock_disc.return_value = 7
                sync_and_discover(db, transport, "srv", user_id="u1", on_discovered=cb)

        cb.assert_called_once_with(7)

    def test_no_discover_callback_when_zero_discovered(self, db, transport):
        cb = Mock()
        with patch("peerpedia_core.app.commands.sync.sync_all") as mock_sync:
            mock_sync.return_value = 0
            with patch("peerpedia_core.app.commands.sync.discover_articles") as mock_disc:
                mock_disc.return_value = 0
                sync_and_discover(db, transport, "srv", user_id="u1", on_discovered=cb)

        cb.assert_not_called()

    def test_network_error_calls_on_error(self, db, transport):
        cb = Mock()
        with patch("peerpedia_core.app.commands.sync.sync_all") as mock_sync:
            mock_sync.side_effect = TransportError("timeout")
            sync_and_discover(db, transport, "srv", user_id="u1", on_error=cb)

        cb.assert_called_once()
        assert isinstance(cb.call_args[0][0], TransportError)


# ═══════════════════════════════════════════════════════════════════════════════
# sync_all_peers
# ═══════════════════════════════════════════════════════════════════════════════


class TestSyncAllPeers:
    def test_no_peers_does_nothing(self, db, transport):
        with patch("peerpedia_core.app.commands.sync.get_known_peers") as mock_peers:
            mock_peers.return_value = []
            sync_all_peers(db, transport)

        transport.is_online.assert_not_called()

    def test_offline_peer_skipped(self, db, transport):
        cb_skip = Mock()
        transport.is_online.return_value = False
        with patch("peerpedia_core.app.commands.sync.get_known_peers") as mock_peers:
            mock_peers.return_value = ["peer1"]
            with patch("peerpedia_core.app.commands.sync.record_peer_result"):
                sync_all_peers(db, transport, on_peer_skip=cb_skip)

        cb_skip.assert_called_once_with("peer1", "offline")

    def test_clock_skew_peer_skipped(self, db, transport):
        cb_skip = Mock()
        transport.is_online.return_value = True
        transport.check_clock_skew.return_value = 999  # huge skew
        with patch("peerpedia_core.app.commands.sync.get_known_peers") as mock_peers:
            mock_peers.return_value = ["peer1"]
            with patch("peerpedia_core.app.commands.sync.record_peer_result"):
                sync_all_peers(db, transport, on_peer_skip=cb_skip)

        cb_skip.assert_called_once_with("peer1", "clock_skew")

    def test_successful_sync_calls_on_peer_done(self, db, transport):
        cb_done = Mock()
        transport.is_online.return_value = True
        transport.check_clock_skew.return_value = 0  # no skew
        with patch("peerpedia_core.app.commands.sync.get_known_peers") as mock_peers:
            mock_peers.return_value = ["peer1"]
            with patch("peerpedia_core.app.commands.sync.sync_all") as mock_sync:
                mock_sync.return_value = 5
                with patch("peerpedia_core.app.commands.sync.record_peer_result"):
                    sync_all_peers(db, transport, on_peer_done=cb_done)

        cb_done.assert_called_once_with("peer1", 5)

    def test_network_error_calls_on_peer_error(self, db, transport):
        cb_error = Mock()
        transport.is_online.side_effect = TransportError("timeout")
        with patch("peerpedia_core.app.commands.sync.get_known_peers") as mock_peers:
            mock_peers.return_value = ["peer1"]
            with patch("peerpedia_core.app.commands.sync.record_peer_result"):
                sync_all_peers(db, transport, on_peer_error=cb_error)

        cb_error.assert_called_once()

    def test_calls_on_peer_start(self, db, transport):
        cb_start = Mock()
        transport.is_online.return_value = True
        transport.check_clock_skew.return_value = 0
        with patch("peerpedia_core.app.commands.sync.get_known_peers") as mock_peers:
            mock_peers.return_value = ["peer1"]
            with patch("peerpedia_core.app.commands.sync.sync_all") as mock_sync:
                mock_sync.return_value = 0
                with patch("peerpedia_core.app.commands.sync.record_peer_result"):
                    sync_all_peers(db, transport, on_peer_start=cb_start)

        cb_start.assert_called_once_with("peer1")

    def test_discovers_when_user_id_provided(self, db, transport):
        cb_disc = Mock()
        transport.is_online.return_value = True
        transport.check_clock_skew.return_value = 0
        with patch("peerpedia_core.app.commands.sync.get_known_peers") as mock_peers:
            mock_peers.return_value = ["peer1"]
            with patch("peerpedia_core.app.commands.sync.sync_all") as mock_sync:
                mock_sync.return_value = 0
                with patch("peerpedia_core.app.commands.sync.discover_articles") as mock_disc:
                    mock_disc.return_value = 3
                    with patch("peerpedia_core.app.commands.sync.record_peer_result"):
                        sync_all_peers(db, transport, user_id="u1",
                                       on_peer_discover=cb_disc)

        cb_disc.assert_called_once_with(3)

    def test_discover_error_is_silent(self, db, transport):
        """Discover failure does not crash the peer loop."""
        transport.is_online.return_value = True
        transport.check_clock_skew.return_value = 0
        with patch("peerpedia_core.app.commands.sync.get_known_peers") as mock_peers:
            mock_peers.return_value = ["peer1", "peer2"]
            with patch("peerpedia_core.app.commands.sync.sync_all") as mock_sync:
                mock_sync.return_value = 0
                with patch("peerpedia_core.app.commands.sync.discover_articles") as mock_disc:
                    mock_disc.side_effect = TransportError("discover failed")
                    with patch("peerpedia_core.app.commands.sync.record_peer_result"):
                        sync_all_peers(db, transport, user_id="u1")

        # Both peers were attempted despite discover errors
        assert mock_sync.call_count == 2
