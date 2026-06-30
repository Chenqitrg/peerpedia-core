# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Tests for transport/guards.py — auth header verification."""

import time

import pytest

from peerpedia_core.crypto import derive_key_pair, sha256_hex, sign_detached
from peerpedia_core.transport.auth import AuthResult


# ── Helper ───────────────────────────────────────────────────────────────────


def _test_keypair():
    import hashlib
    salt = hashlib.sha256(b"test-guards@peerpedia").hexdigest()[:32]
    priv, pub = derive_key_pair("test-password-123", salt)
    return priv, pub.hex()


def _make_valid_header(method="GET", path="/test", user_id="user-1", body=b"") -> str:
    """Build a valid Peerpedia auth header for testing verification."""
    priv, pub = _test_keypair()
    ts = str(int(time.time()))
    body_hash = sha256_hex(body)
    message = f"{method}:{path}:{user_id}:{ts}:{body_hash}".encode("utf-8")
    sig = sign_detached(priv, message)
    return f"Peerpedia {user_id}:{pub}:{ts}:{body_hash}:{sig.hex()}"


# ═══════════════════════════════════════════════════════════════════════════════
# verify_auth_header
# ═══════════════════════════════════════════════════════════════════════════════


class TestVerifyAuthHeader:
    def test_valid_header_passes(self):
        """A correctly signed header verifies ok — returns user_id and pubkey."""
        from peerpedia_core.transport.guards import verify_auth_header

        header = _make_valid_header()
        result = verify_auth_header(header, "GET", "/test")
        assert result.ok is True
        assert result.user_id == "user-1"
        assert len(result.pubkey_hex) == 64

    def test_wrong_scheme_fails(self):
        """Non-Peerpedia scheme returns ok=False."""
        from peerpedia_core.transport.guards import verify_auth_header

        result = verify_auth_header("Bearer token123", "GET", "/")
        assert result.ok is False
        assert "scheme" in result.reason.lower()

    def test_malformed_header_fails(self):
        """Garbage header returns ok=False — doesn't crash."""
        from peerpedia_core.transport.guards import verify_auth_header

        result = verify_auth_header("not-even-a-valid-header", "GET", "/")
        assert result.ok is False

    def test_wrong_field_count_fails(self):
        """Header with wrong number of colon fields returns ok=False."""
        from peerpedia_core.transport.guards import verify_auth_header

        result = verify_auth_header("Peerpedia a:b:c:d", "GET", "/")  # only 4 fields
        assert result.ok is False
        assert "5" in result.reason  # expects exactly 5

    def test_body_hash_mismatch_fails(self):
        """Body hash in header doesn't match actual body → ok=False."""
        from peerpedia_core.transport.guards import verify_auth_header

        header = _make_valid_header(body=b"original")
        result = verify_auth_header(header, "GET", "/test", body=b"modified")
        assert result.ok is False

    def test_method_mismatch_fails(self):
        """Signature covers method — verifying with wrong method fails."""
        from peerpedia_core.transport.guards import verify_auth_header

        header = _make_valid_header(method="POST")
        result = verify_auth_header(header, "GET", "/test")
        assert result.ok is False
        assert "Signature" in result.reason

    def test_path_mismatch_fails(self):
        """Signature covers path — verifying with wrong path fails."""
        from peerpedia_core.transport.guards import verify_auth_header

        header = _make_valid_header(path="/a")
        result = verify_auth_header(header, "GET", "/b")
        assert result.ok is False
        assert "Signature" in result.reason

    def test_expired_timestamp_fails(self):
        """Timestamp outside ± tolerance window returns ok=False."""
        from peerpedia_core.transport.guards import verify_auth_header

        priv, pub = _test_keypair()
        ts = str(int(time.time()) - 3600)  # 1 hour ago
        body_hash = sha256_hex(b"")
        message = f"GET:/test:user-1:{ts}:{body_hash}".encode("utf-8")
        sig = sign_detached(priv, message)
        header = f"Peerpedia user-1:{pub}:{ts}:{body_hash}:{sig.hex()}"

        result = verify_auth_header(header, "GET", "/test")
        assert result.ok is False

    def test_invalid_signature_fails(self):
        """Tampered signature returns ok=False."""
        from peerpedia_core.transport.guards import verify_auth_header

        priv, pub = _test_keypair()
        ts = str(int(time.time()))
        body_hash = sha256_hex(b"")
        message = f"GET:/test:user-1:{ts}:{body_hash}".encode("utf-8")
        sig = sign_detached(priv, message)
        # Tamper with the signature
        tampered_sig = "aa" + sig.hex()[2:]
        header = f"Peerpedia user-1:{pub}:{ts}:{body_hash}:{tampered_sig}"

        result = verify_auth_header(header, "GET", "/test")
        assert result.ok is False

    def test_invalid_pubkey_fails(self):
        """Non-hex pubkey returns ok=False."""
        from peerpedia_core.transport.guards import verify_auth_header

        priv, pub = _test_keypair()
        ts = str(int(time.time()))
        body_hash = sha256_hex(b"")
        message = f"GET:/test:user-1:{ts}:{body_hash}".encode("utf-8")
        sig = sign_detached(priv, message)
        # Garbage pubkey
        header = f"Peerpedia user-1:nothex:{ts}:{body_hash}:{sig.hex()}"

        result = verify_auth_header(header, "GET", "/test")
        assert result.ok is False
