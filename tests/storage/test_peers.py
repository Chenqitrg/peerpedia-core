# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Tests for storage/peers.py — P2P peer discovery and backoff management."""

import json
import time

import pytest


# ═══════════════════════════════════════════════════════════════════════════════
# Global state reset — peers module uses module-level _backoff dict
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture(autouse=True)
def _reset_peers_globals():
    """Reset peers.py module-level globals between tests to prevent state leakage."""
    from peerpedia_core.storage import peers
    peers._backoff.clear()
    peers._backoff_hydrated = False


# ── Helper to redirect PEERS_FILE ────────────────────────────────────────────


def _set_peers_file(tmp_path, monkeypatch):
    """Redirect PEERS_FILE to a temporary location."""
    pf = tmp_path / "peers.json"
    monkeypatch.setattr("peerpedia_core.storage.peers.PEERS_FILE", pf)
    return pf


# ═══════════════════════════════════════════════════════════════════════════════
# get_known_peers
# ═══════════════════════════════════════════════════════════════════════════════


class TestGetKnownPeers:
    def test_empty_file_returns_seeds(self, tmp_path, monkeypatch):
        """When peers.json doesn't exist or is empty, seed peers are returned."""
        from peerpedia_core.storage.peers import get_known_peers

        _set_peers_file(tmp_path, monkeypatch)
        result = get_known_peers()
        # Should include seed peers defined in config/params.py
        from peerpedia_core.config.params import params
        for sp in params.discovery.seed_peers:
            assert sp in result

    def test_from_file_returns_saved_peers(self, tmp_path, monkeypatch):
        """Saved peer URLs from peers.json are returned alongside seeds."""
        from peerpedia_core.storage.peers import get_known_peers

        pf = _set_peers_file(tmp_path, monkeypatch)
        pf.write_text(json.dumps(["https://peer1.example.com", "https://peer2.example.com"]))
        result = get_known_peers(skip_backoff=False)
        assert "https://peer1.example.com" in result
        assert "https://peer2.example.com" in result

    def test_skips_backoff_peers(self, tmp_path, monkeypatch):
        """Peers in exponential backoff are excluded when skip_backoff=True (default)."""
        from peerpedia_core.storage.peers import _peer_failed, _save_peers_raw

        pf = _set_peers_file(tmp_path, monkeypatch)
        # Manually simulate a peer with backoff
        from peerpedia_core.storage import peers
        peers._backoff["https://bad-peer.example.com"] = {
            "fail_count": 3, "last_failed_at": time.time(),
        }
        _save_peers_raw([
            {"url": "https://good-peer.example.com"},
            {"url": "https://bad-peer.example.com", "fail_count": 3, "last_failed_at": time.time()},
        ])

        from peerpedia_core.storage.peers import get_known_peers
        result = get_known_peers(skip_backoff=True)
        assert "https://good-peer.example.com" in result
        assert "https://bad-peer.example.com" not in result

    def test_seeds_never_backoff(self, tmp_path, monkeypatch):
        """Seed peers are always included regardless of backoff state."""
        from peerpedia_core.storage.peers import get_known_peers

        _set_peers_file(tmp_path, monkeypatch)
        from peerpedia_core.config.params import params
        seeds = list(params.discovery.seed_peers)
        if seeds:
            # Seed peers should always be present
            result = get_known_peers(skip_backoff=True)
            for sp in seeds:
                assert sp in result


# ═══════════════════════════════════════════════════════════════════════════════
# add_peer
# ═══════════════════════════════════════════════════════════════════════════════


class TestAddPeer:
    def test_idempotent(self, tmp_path, monkeypatch):
        """Adding the same peer twice doesn't create duplicates."""
        from peerpedia_core.storage.peers import add_peer, get_known_peers

        pf = _set_peers_file(tmp_path, monkeypatch)
        add_peer("https://peer1.example.com")
        add_peer("https://peer1.example.com")
        result = get_known_peers(skip_backoff=False)
        # Count occurrences of the peer URL
        assert result.count("https://peer1.example.com") == 1

    def test_inserts_at_front(self, tmp_path, monkeypatch):
        """New peer is inserted at position 0 — most recent first."""
        from peerpedia_core.storage.peers import add_peer, get_known_peers

        pf = _set_peers_file(tmp_path, monkeypatch)
        # Write existing peers
        pf.write_text(json.dumps(["https://old.example.com"]))
        add_peer("https://new.example.com")
        result = get_known_peers(skip_backoff=False)
        # new peer should be before old peers (seeds are appended last)
        new_idx = result.index("https://new.example.com")
        old_idx = result.index("https://old.example.com")
        assert new_idx < old_idx


# ═══════════════════════════════════════════════════════════════════════════════
# record_peer_result
# ═══════════════════════════════════════════════════════════════════════════════


class TestRecordPeerResult:
    def test_success_resets_backoff(self, tmp_path, monkeypatch):
        """Successful connection removes the peer from backoff state."""
        from peerpedia_core.storage.peers import _peer_failed, record_peer_result

        pf = _set_peers_file(tmp_path, monkeypatch)
        url = "https://peer.example.com"
        # First fail
        _peer_failed(url)
        from peerpedia_core.storage import peers
        assert url in peers._backoff

        # Then succeed — backoff should be cleared
        record_peer_result(url, success=True)
        assert url not in peers._backoff

    def test_failure_increments_count(self, tmp_path, monkeypatch):
        """Each failure increments fail_count — capped at 5."""
        from peerpedia_core.storage.peers import record_peer_result

        pf = _set_peers_file(tmp_path, monkeypatch)
        url = "https://peer.example.com"

        for i in range(7):  # 7 failures, should cap at 5
            record_peer_result(url, success=False)

        from peerpedia_core.storage import peers
        assert peers._backoff[url]["fail_count"] == 5  # capped


# ═══════════════════════════════════════════════════════════════════════════════
# merge_peers
# ═══════════════════════════════════════════════════════════════════════════════


class TestMergePeers:
    def test_discovers_new_peers(self, tmp_path, monkeypatch):
        """New peers from a transport fetch are added to the local list."""
        from unittest.mock import MagicMock
        from peerpedia_core.storage.peers import merge_peers, get_known_peers

        pf = _set_peers_file(tmp_path, monkeypatch)
        pf.write_text(json.dumps(["https://existing.example.com"]))

        mock_transport = MagicMock()
        mock_transport.fetch_peers.return_value = [
            "https://existing.example.com",
            "https://new-peer.example.com",
        ]
        count = merge_peers(mock_transport, "https://server.example.com")
        assert count == 1

        result = get_known_peers(skip_backoff=False)
        assert "https://new-peer.example.com" in result

    def test_transport_fails_gracefully(self, tmp_path, monkeypatch):
        """Transport exception → returns 0, doesn't crash."""
        from unittest.mock import MagicMock
        from peerpedia_core.storage.peers import merge_peers

        pf = _set_peers_file(tmp_path, monkeypatch)
        pf.write_text(json.dumps(["https://existing.example.com"]))

        mock_transport = MagicMock()
        mock_transport.fetch_peers.side_effect = ConnectionError("unreachable")
        count = merge_peers(mock_transport, "https://server.example.com")
        assert count == 0
