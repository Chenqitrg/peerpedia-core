# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Tests for transport/auth.py — Ed25519 auth header signing."""

import time

import pytest

from peerpedia_core.crypto import derive_key_pair


# ── Helper ───────────────────────────────────────────────────────────────────


def _test_keypair():
    """Derive a deterministic Ed25519 keypair for testing."""
    import hashlib
    salt = hashlib.sha256(b"test-auth@peerpedia").hexdigest()[:32]
    priv, pub = derive_key_pair("test-password-123", salt)
    return priv, pub.hex()


# ═══════════════════════════════════════════════════════════════════════════════
# sign_auth_header
# ═══════════════════════════════════════════════════════════════════════════════


class TestSignAuthHeader:
    def test_format_has_correct_scheme(self):
        """Header starts with 'Peerpedia ' — the protocol scheme."""
        from peerpedia_core.transport.auth import sign_auth_header

        priv, pub = _test_keypair()
        header = sign_auth_header("POST", "/api/v1/test", "user-1", priv, pub)
        assert header.startswith("Peerpedia ")

    def test_format_has_five_colon_separated_fields(self):
        """Header value after scheme contains exactly 5 colon-separated fields:
        uid:pubkey:ts:body_hash:sig."""
        from peerpedia_core.transport.auth import sign_auth_header

        priv, pub = _test_keypair()
        header = sign_auth_header("GET", "/api/v1/test", "user-1", priv, pub)
        payload = header.split(" ", 1)[1]
        parts = payload.split(":")
        assert len(parts) == 5
        assert parts[0] == "user-1"
        assert parts[1] == pub

    def test_ts_is_epoch_seconds(self):
        """Timestamp field is within ±2s of now."""
        from peerpedia_core.transport.auth import sign_auth_header

        priv, pub = _test_keypair()
        header = sign_auth_header("GET", "/", "u", priv, pub)
        parts = header.split(" ", 1)[1].split(":")
        ts = int(parts[2])
        assert abs(ts - int(time.time())) <= 2

    def test_body_hash_is_sha256_hex(self):
        """Body hash is 64 hex characters — SHA-256 digest."""
        from peerpedia_core.transport.auth import sign_auth_header

        priv, pub = _test_keypair()
        header = sign_auth_header("POST", "/", "u", priv, pub, body=b"hello")
        parts = header.split(" ", 1)[1].split(":")
        body_hash = parts[3]
        assert len(body_hash) == 64

    def test_empty_body_hash(self):
        """Empty body produces the SHA-256 of empty bytes, not a placeholder."""
        from peerpedia_core.transport.auth import sign_auth_header
        from peerpedia_core.crypto import sha256_hex

        priv, pub = _test_keypair()
        header = sign_auth_header("GET", "/", "u", priv, pub)
        parts = header.split(" ", 1)[1].split(":")
        assert parts[3] == sha256_hex(b"")

    def test_sig_is_deterministic(self):
        """Same inputs produce same signature — Ed25519 is deterministic."""
        from peerpedia_core.transport.auth import sign_auth_header

        priv, pub = _test_keypair()
        h1 = sign_auth_header("GET", "/a", "u", priv, pub, body=b"x")
        h2 = sign_auth_header("GET", "/a", "u", priv, pub, body=b"x")
        assert h1 == h2

    def test_different_method_produces_different_sig(self):
        """Different HTTP method changes the signed message → different sig."""
        from peerpedia_core.transport.auth import sign_auth_header

        priv, pub = _test_keypair()
        h1 = sign_auth_header("GET", "/a", "u", priv, pub)
        h2 = sign_auth_header("POST", "/a", "u", priv, pub)
        assert h1 != h2


# ═══════════════════════════════════════════════════════════════════════════════
# build_auth_header
# ═══════════════════════════════════════════════════════════════════════════════


class TestBuildAuthHeader:
    def test_returns_dict_with_authorization_key(self):
        """Returns a dict suitable for passing as HTTP headers."""
        from peerpedia_core.transport.auth import build_auth_header

        priv, pub = _test_keypair()
        result = build_auth_header("GET", "/", "u", priv, pub)
        assert isinstance(result, dict)
        assert "Authorization" in result
        assert result["Authorization"].startswith("Peerpedia ")

    def test_returns_empty_dict_when_no_key(self):
        """When private_key_bytes is None, returns {} — no credentials to sign."""
        from peerpedia_core.transport.auth import build_auth_header

        _, pub = _test_keypair()
        result = build_auth_header("GET", "/", "u", None, pub)
        assert result == {}
