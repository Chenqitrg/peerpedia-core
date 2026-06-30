# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Tests for server/middleware/auth.py — Ed25519 auth middleware.

These tests run with auth ENABLED (no PEERPEDIA_SKIP_AUTH).
"""

import os
import time

import pytest
from starlette.testclient import TestClient

from peerpedia_core.crypto import derive_key_pair, sha256_hex, sign_detached


# ── Helpers ──────────────────────────────────────────────────────────────────


def _test_keypair():
    import hashlib
    salt = hashlib.sha256(b"server-auth-test@peerpedia").hexdigest()[:32]
    priv, pub = derive_key_pair("test-password-123", salt)
    return priv, pub.hex()


def _make_auth_header(method, path, user_id, body=b""):
    priv, pub = _test_keypair()
    ts = str(int(time.time()))
    body_hash = sha256_hex(body)
    message = f"{method}:{path}:{user_id}:{ts}:{body_hash}".encode("utf-8")
    sig = sign_detached(priv, message)
    return f"Peerpedia {user_id}:{pub}:{ts}:{body_hash}:{sig.hex()}"


def _make_client():
    """Create a TestClient without PEERPEDIA_SKIP_AUTH."""
    orig = os.environ.pop("PEERPEDIA_SKIP_AUTH", None)
    from peerpedia_core.server.app import create_app
    # Clear the in-memory health cache between tests
    from peerpedia_core.transport.http.health import clear_health_cache
    clear_health_cache()
    client = TestClient(create_app())
    if orig is not None:
        os.environ["PEERPEDIA_SKIP_AUTH"] = orig
    return client


# ═══════════════════════════════════════════════════════════════════════════════
# Auth required — protected routes reject missing/invalid headers
# ═══════════════════════════════════════════════════════════════════════════════


class TestAuthRequired:
    def test_missing_auth_header_returns_401(self):
        """Protected route without Authorization header → 401."""
        client = _make_client()
        resp = client.get("/api/v1/peers")
        assert resp.status_code == 401
        assert "Authentication required" in resp.json()["error"]

    def test_non_peerpedia_scheme_returns_401(self):
        """Bearer token on a Peerpedia route → 401."""
        client = _make_client()
        resp = client.get("/api/v1/peers", headers={"Authorization": "Bearer token123"})
        assert resp.status_code == 401

    def test_malformed_header_returns_401(self):
        """Garbage auth header → 401."""
        client = _make_client()
        resp = client.get("/api/v1/peers", headers={"Authorization": "Peerpedia garbage"})
        assert resp.status_code == 401

    def test_expired_timestamp_returns_401(self):
        """Timestamp outside ± tolerance → 401."""
        client = _make_client()
        priv, pub = _test_keypair()
        ts = str(int(time.time()) - 3600)  # 1 hour ago
        body_hash = sha256_hex(b"")
        message = f"GET:/api/v1/peers:user-1:{ts}:{body_hash}".encode("utf-8")
        sig = sign_detached(priv, message)
        header = f"Peerpedia user-1:{pub}:{ts}:{body_hash}:{sig.hex()}"

        resp = client.get("/api/v1/peers", headers={"Authorization": header})
        assert resp.status_code == 401

    def test_invalid_signature_returns_401(self):
        """Tampered signature → 401."""
        client = _make_client()
        header = _make_auth_header("GET", "/api/v1/peers", "user-1")
        # Tamper with the last character of the signature
        parts = header.split(":")
        parts[-1] = parts[-1][:-1] + ("f" if parts[-1][-1] != "f" else "0")
        tampered = ":".join(parts)

        resp = client.get("/api/v1/peers", headers={"Authorization": tampered})
        assert resp.status_code == 401

    def test_body_hash_mismatch_returns_401(self):
        """Signed with one body but sent with another → 401."""
        client = _make_client()
        header = _make_auth_header("POST", "/api/v1/peers", "user-1",
                                   body=b'{"url": "https://x.com"}')
        # Send with a different body
        resp = client.post("/api/v1/peers",
                          json={"url": "https://different.com"},
                          headers={"Authorization": header})
        assert resp.status_code == 401


# ═══════════════════════════════════════════════════════════════════════════════
# Public routes — skip auth
# ═══════════════════════════════════════════════════════════════════════════════


class TestPublicRoutesSkipAuth:
    def test_health_is_public(self):
        """GET /health requires no auth."""
        client = _make_client()
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_school_is_public(self):
        """GET /api/v1/school requires no auth — leaderboard is public."""
        client = _make_client()
        resp = client.get("/api/v1/school")
        assert resp.status_code == 200

    def test_head_is_public(self):
        """GET /head is a git-bundle route — no auth needed."""
        client = _make_client()
        resp = client.get("/api/v1/articles/00000000-0000-0000-0000-000000000001/head")
        assert resp.status_code in (200, 404)  # 404 is fine, just not 401

    def test_bundle_is_public(self):
        """GET /bundle is a git-bundle route — no auth needed."""
        client = _make_client()
        resp = client.get("/api/v1/articles/00000000-0000-0000-0000-000000000001/bundle")
        assert resp.status_code != 401

    def test_ancestor_probe_is_public(self):
        """GET /ancestor/ is a git-bundle route — no auth needed."""
        client = _make_client()
        resp = client.get("/api/v1/articles/00000000-0000-0000-0000-000000000001/ancestor/abc123")
        assert resp.status_code != 401

    def test_repo_is_public(self):
        """GET /repo is a git-bundle route — no auth needed."""
        client = _make_client()
        resp = client.get("/api/v1/articles/00000000-0000-0000-0000-000000000001/repo")
        assert resp.status_code != 401

    def test_following_is_public(self):
        """GET /following is public for social discovery."""
        client = _make_client()
        resp = client.get("/api/v1/users/00000000-0000-0000-0000-000000000001/following")
        assert resp.status_code != 401

    def test_followers_is_public(self):
        """GET /followers is public for social discovery."""
        client = _make_client()
        resp = client.get("/api/v1/users/00000000-0000-0000-0000-000000000001/followers")
        assert resp.status_code != 401

    def test_user_articles_is_public(self):
        """GET /articles is public for social discovery."""
        client = _make_client()
        resp = client.get("/api/v1/users/00000000-0000-0000-0000-000000000001/articles")
        assert resp.status_code != 401

    def test_shares_is_public(self):
        """GET /shares is public."""
        client = _make_client()
        resp = client.get("/api/v1/users/00000000-0000-0000-0000-000000000001/shares")
        assert resp.status_code != 401


# ═══════════════════════════════════════════════════════════════════════════════
# Valid auth — TOFU registration
# ═══════════════════════════════════════════════════════════════════════════════


class TestValidAuth:
    def test_valid_auth_accesses_protected_route(self):
        """Valid signature on a protected route → 200 (TOFU creates user stub)."""
        client = _make_client()
        header = _make_auth_header("GET", "/api/v1/peers", "new-user-tofu")
        resp = client.get("/api/v1/peers", headers={"Authorization": header})
        assert resp.status_code == 200
