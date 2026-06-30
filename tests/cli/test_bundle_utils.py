# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Tests for cli/bundle_utils.py — sync helpers and server URL resolution."""

from unittest.mock import patch

import pytest


# ═══════════════════════════════════════════════════════════════════════════════
# _map_sync_error
# ═══════════════════════════════════════════════════════════════════════════════


class TestMapSyncError:
    def test_transport_error_maps_to_sync_failed(self):
        """TransportError (network) → S_AUTO_SYNC_FAILED."""
        from peerpedia_core.cli.bundle_utils import _map_sync_error
        from peerpedia_core.exceptions import TransportError

        code = _map_sync_error(TransportError("timeout"))
        assert code == "S_AUTO_SYNC_FAILED"

    def test_protocol_error_maps_to_sync_failed(self):
        """ProtocolError (bad response) → S_AUTO_SYNC_FAILED."""
        from peerpedia_core.cli.bundle_utils import _map_sync_error
        from peerpedia_core.exceptions import ProtocolError

        code = _map_sync_error(ProtocolError("bad status"))
        assert code == "S_AUTO_SYNC_FAILED"

    def test_conflict_error_maps_to_conflict(self):
        """ConflictError (divergent history) → S_AUTO_SYNC_CONFLICT."""
        from peerpedia_core.cli.bundle_utils import _map_sync_error
        from peerpedia_core.exceptions import ConflictError

        code = _map_sync_error(ConflictError("history divergence"))
        assert code == "S_AUTO_SYNC_CONFLICT"

    def test_unknown_error_re_raises(self):
        """Unexpected exceptions are re-raised — caller should handle."""
        from peerpedia_core.cli.bundle_utils import _map_sync_error

        with pytest.raises(ValueError):
            _map_sync_error(ValueError("unexpected"))


# ═══════════════════════════════════════════════════════════════════════════════
# _read_saved_server / _save_default_server
# ═══════════════════════════════════════════════════════════════════════════════


class TestServerFile:
    def test_read_saved_server_found(self, tmp_path):
        """Valid server file → returns URL."""
        from peerpedia_core.cli.bundle_utils import _read_saved_server

        sf = tmp_path / "server_default"
        sf.write_text("https://peer.example.com")
        with patch("peerpedia_core.cli.bundle_utils.SERVER_DEFAULT_FILE", sf):
            assert _read_saved_server() == "https://peer.example.com"

    def test_read_saved_server_not_found(self, tmp_path):
        """No server file → returns None."""
        from peerpedia_core.cli.bundle_utils import _read_saved_server

        sf = tmp_path / "nonexistent"
        with patch("peerpedia_core.cli.bundle_utils.SERVER_DEFAULT_FILE", sf):
            assert _read_saved_server() is None

    def test_save_default_server(self, tmp_path):
        """Writes URL to server file."""
        from peerpedia_core.cli.bundle_utils import _save_default_server

        sf = tmp_path / "server_default"
        with patch("peerpedia_core.cli.bundle_utils.SERVER_DEFAULT_FILE", sf):
            _save_default_server("https://saved.example.com")
        assert sf.read_text().strip() == "https://saved.example.com"
