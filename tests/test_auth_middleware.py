# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Tests for AuthMiddleware public-path matching.

Verifies that public routes are correctly identified and that
substring false-positives (like "/repo" matching "/report") are
prevented.
"""

import pytest

from peerpedia_core.transport.middleware.auth import AuthMiddleware


def _is_public(path: str) -> bool:
    """Replicate the dispatch method's public-path logic."""
    mw = AuthMiddleware(app=None)
    if path.startswith(mw._PUBLIC_PREFIXES):  # noqa: SLF001
        return True
    if path.endswith(mw._PUBLIC_SUFFIXES):  # noqa: SLF001
        return True
    for fragment in mw._PUBLIC_CONTAINS:  # noqa: SLF001
        if fragment in path:
            return True
    return False


class TestAuthMiddlewarePublicPaths:
    """Auth middleware must let public git-bundle paths through unauthenticated,
    but must NOT let unrelated paths through due to substring false-positives."""

    # ── paths that MUST be public ──────────────────────────────────────

    def test_health_is_public(self):
        assert _is_public("/health")

    def test_head_suffix_is_public(self):
        """GET /api/v1/articles/{id}/head skips auth."""
        assert _is_public("/api/v1/articles/abc123/head")

    def test_bundle_suffix_is_public(self):
        """GET /api/v1/articles/{id}/bundle skips auth."""
        assert _is_public("/api/v1/articles/abc123/bundle")

    def test_sync_suffix_is_public(self):
        """POST /api/v1/articles/{id}/sync skips auth."""
        assert _is_public("/api/v1/articles/abc123/sync")

    def test_ancestor_contains_is_public(self):
        """GET /api/v1/articles/{id}/ancestor/{hash} skips auth."""
        assert _is_public("/api/v1/articles/abc123/ancestor/def456")

    def test_repo_suffix_is_public(self):
        """GET /api/v1/articles/{id}/repo skips auth."""
        assert _is_public("/api/v1/articles/abc123/repo")

    # ── paths that MUST NOT be public (false-positive prevention) ──────

    def test_repo_does_not_match_report(self):
        """"/repo" suffix must NOT match /api/v1/report."""
        assert not _is_public("/api/v1/report")

    def test_repo_does_not_match_repository(self):
        """"/repo" suffix must NOT match /repository."""
        assert not _is_public("/repository")

    def test_sync_does_not_match_async(self):
        """"/sync" suffix must NOT match /api/v1/async."""
        assert not _is_public("/api/v1/async")

    def test_head_does_not_match_ahead(self):
        """"/head" suffix must NOT match /ahead."""
        assert not _is_public("/ahead")

    def test_normal_api_route_requires_auth(self):
        """GET /api/v1/peers requires auth (not in any public list)."""
        assert not _is_public("/api/v1/peers")

    def test_user_endpoint_requires_auth(self):
        """GET /api/v1/users requires auth."""
        assert not _is_public("/api/v1/users")
