# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Tests for transport/http/_core.py — HTTP client helpers."""

import json

import pytest


# ═══════════════════════════════════════════════════════════════════════════════
# Path builders
# ═══════════════════════════════════════════════════════════════════════════════


class TestPathBuilders:
    def test_article_path_no_action(self):
        """Without action → /api/v1/articles/{id}."""
        from peerpedia_core.transport.http._core import _article_path
        assert _article_path("art-1") == "/api/v1/articles/art-1"

    def test_article_path_with_action(self):
        """With action → /api/v1/articles/{id}/{action}."""
        from peerpedia_core.transport.http._core import _article_path
        assert _article_path("art-1", "head") == "/api/v1/articles/art-1/head"

    def test_user_path_no_action(self):
        """Without action → /api/v1/users/{id}."""
        from peerpedia_core.transport.http._core import _user_path
        assert _user_path("user-1") == "/api/v1/users/user-1"

    def test_user_path_with_action(self):
        """With action → /api/v1/users/{id}/{action}."""
        from peerpedia_core.transport.http._core import _user_path
        assert _user_path("user-1", "following") == "/api/v1/users/user-1/following"

    def test_api_path(self):
        """API root path → /api/v1/{action}."""
        from peerpedia_core.transport.http._core import _api_path
        assert _api_path("health") == "/api/v1/health"
        assert _api_path("peers") == "/api/v1/peers"


# ═══════════════════════════════════════════════════════════════════════════════
# Body encoding
# ═══════════════════════════════════════════════════════════════════════════════


class TestEncodeBody:
    def test_encodes_dict_to_json_bytes(self):
        """JSON-serialized bytes — ready for HTTP request body."""
        from peerpedia_core.transport.http._core import _encode_body
        result = _encode_body({"key": "value"})
        assert isinstance(result, bytes)
        assert json.loads(result) == {"key": "value"}

    def test_encodes_nested_structures(self):
        """Nested dicts and lists are serialized correctly."""
        from peerpedia_core.transport.http._core import _encode_body
        data = {"ids": ["a", "b"], "meta": {"count": 3}}
        result = _encode_body(data)
        assert json.loads(result) == data
