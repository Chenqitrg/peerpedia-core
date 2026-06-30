# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Tests for cli/session.py — session file I/O."""

import json
import os
from pathlib import Path
from unittest.mock import patch


# ═══════════════════════════════════════════════════════════════════════════════
# _read_session
# ═══════════════════════════════════════════════════════════════════════════════


class TestReadSession:
    def test_reads_valid_session(self, tmp_path):
        """Valid JSON session file → returns dict."""
        from peerpedia_core.cli.session import _read_session

        sf = tmp_path / "session.json"
        sf.write_text(json.dumps({"user_id": "test-id", "name": "Alice"}))

        with patch("peerpedia_core.cli.session.SESSION_FILE", sf):
            result = _read_session()
            assert result == {"user_id": "test-id", "name": "Alice"}

    def test_no_file_returns_none(self, tmp_path):
        """Missing session file → returns None, no crash."""
        from peerpedia_core.cli.session import _read_session

        sf = tmp_path / "nonexistent.json"
        with patch("peerpedia_core.cli.session.SESSION_FILE", sf):
            assert _read_session() is None

    def test_corrupt_file_returns_none(self, tmp_path):
        """Corrupt JSON → returns None, no crash."""
        from peerpedia_core.cli.session import _read_session

        sf = tmp_path / "session.json"
        sf.write_text("not-valid-json")
        with patch("peerpedia_core.cli.session.SESSION_FILE", sf):
            assert _read_session() is None


# ═══════════════════════════════════════════════════════════════════════════════
# _write_session
# ═══════════════════════════════════════════════════════════════════════════════


class TestWriteSession:
    def test_writes_json_with_chmod(self, tmp_path):
        """Session file written with user_id, name, key; chmod 0o600."""
        from peerpedia_core.cli.session import _write_session

        sf = tmp_path / "session.json"
        with patch("peerpedia_core.cli.session.SESSION_FILE", sf):
            with patch("os.chmod") as mock_chmod:
                _write_session("uid-1", "Alice", "00ff" * 16)
                mock_chmod.assert_called_once()

        data = json.loads(sf.read_text())
        assert data["user_id"] == "uid-1"
        assert data["name"] == "Alice"
        assert "private_key_hex" in data


# ═══════════════════════════════════════════════════════════════════════════════
# _get_session_key / _get_session_pubkey
# ═══════════════════════════════════════════════════════════════════════════════


class TestGetSessionKey:
    def test_returns_key_bytes(self):
        """Valid session → returns private key bytes."""
        from peerpedia_core.cli.session import _get_session_key

        with patch("peerpedia_core.cli.session._read_session") as mock_read:
            mock_read.return_value = {
                "user_id": "uid", "name": "A",
                "private_key_hex": "00" * 32,
            }
            result = _get_session_key()
            assert isinstance(result, bytes)

    def test_no_session_returns_none(self):
        """No session → returns None."""
        from peerpedia_core.cli.session import _get_session_key

        with patch("peerpedia_core.cli.session._read_session", return_value=None):
            assert _get_session_key() is None

    def test_get_session_pubkey_no_session_returns_empty(self):
        """No session → _get_session_pubkey returns empty string."""
        from peerpedia_core.cli.session import _get_session_pubkey

        with patch("peerpedia_core.cli.session._get_session_key", return_value=None):
            assert _get_session_pubkey() == ""
