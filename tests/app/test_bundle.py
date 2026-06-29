# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Spec: Bundle commands — sync_status, sync_pull, sync_discover."""

from unittest.mock import patch

import pytest

from peerpedia_core.app.commands.bundle import sync_discover, sync_pull, sync_status
from peerpedia_core.exceptions import (
    ConflictError, NotAuthorizedError, ProtocolError, TransportError,
)
from tests.app.conftest import login


# ═══════════════════════════════════════════════════════════════════════════════
# sync_status
# ═══════════════════════════════════════════════════════════════════════════════


class TestSyncStatus:
    def test_online(self, ctx):
        ctx.transport.is_online.return_value = True
        result = sync_status(ctx, server="peer.example.com")
        assert result.data["online"] is True
        assert result.data["server"] == "peer.example.com"

    def test_offline(self, ctx):
        ctx.transport.is_online.return_value = False
        result = sync_status(ctx, server="peer.example.com")
        assert result.data["online"] is False


# ═══════════════════════════════════════════════════════════════════════════════
# sync_pull
# ═══════════════════════════════════════════════════════════════════════════════


class TestSyncPull:
    def test_unauthenticated_raises(self, ctx):
        with pytest.raises(NotAuthorizedError, match="UNAUTHORIZED"):
            sync_pull(ctx, server="peer.example.com")

    def test_no_local_articles(self, ctx):
        """When no articles exist locally, synced and failed are both empty."""
        alice = login(ctx, "Alice")
        ctx.transport.fetch_search.return_value = []

        with patch("peerpedia_core.app.commands.bundle.sync_article") as mock_sync:
            result = sync_pull(alice, server="peer.example.com")

        assert result.data["synced"] == []
        assert result.data["failed"] == []
        mock_sync.assert_not_called()

    def test_sync_success(self, ctx, articles_dir):
        """Sync each local article — synced list populated on success."""
        from peerpedia_core.app.commands.article import create
        alice = login(ctx, "Alice")
        ctx.transport.fetch_search.return_value = []
        a1 = create(alice, title="Paper A", content="# A")
        a2 = create(alice, title="Paper B", content="# B")

        with patch("peerpedia_core.app.commands.bundle.sync_article") as mock_sync:
            mock_sync.return_value = {"synced": True}
            result = sync_pull(alice, server="peer.example.com")

        assert len(result.data["synced"]) == 2
        assert result.data["failed"] == []
        assert mock_sync.call_count == 2
        # Both article IDs appear (order depends on list_all_article_ids)
        synced_ids = set(result.data["synced"])
        assert a1.data["id"][:8] in synced_ids
        assert a2.data["id"][:8] in synced_ids

    def test_sync_failure(self, ctx, articles_dir):
        """Failed syncs appear in failed list, don't crash the loop."""
        from peerpedia_core.app.commands.article import create
        alice = login(ctx, "Alice")
        ctx.transport.fetch_search.return_value = []
        create(alice, title="Paper A", content="# A")

        with patch("peerpedia_core.app.commands.bundle.sync_article") as mock_sync:
            mock_sync.side_effect = TransportError("timeout")
            result = sync_pull(alice, server="peer.example.com")

        assert result.data["synced"] == []
        assert len(result.data["failed"]) == 1
        assert "timeout" in result.data["failed"][0]

    def test_sync_mixed_results(self, ctx, articles_dir):
        """One succeeds, one fails — both lists populated."""
        from peerpedia_core.app.commands.article import create
        alice = login(ctx, "Alice")
        ctx.transport.fetch_search.return_value = []
        create(alice, title="Good", content="# G")
        create(alice, title="Bad", content="# B")

        call_count = 0

        def _alternating(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return {"synced": True}
            raise ProtocolError("protocol mismatch")

        with patch("peerpedia_core.app.commands.bundle.sync_article") as mock_sync:
            mock_sync.side_effect = _alternating
            result = sync_pull(alice, server="peer.example.com")

        assert len(result.data["synced"]) == 1
        assert len(result.data["failed"]) == 1
        assert "protocol mismatch" in result.data["failed"][0]

    def test_catches_conflict_error(self, ctx, articles_dir):
        """ConflictError is also caught in the sync loop."""
        from peerpedia_core.app.commands.article import create
        alice = login(ctx, "Alice")
        ctx.transport.fetch_search.return_value = []
        create(alice, title="Paper", content="# X")

        with patch("peerpedia_core.app.commands.bundle.sync_article") as mock_sync:
            mock_sync.side_effect = ConflictError("merge conflict")
            result = sync_pull(alice, server="peer.example.com")

        assert len(result.data["failed"]) == 1
        assert "merge conflict" in result.data["failed"][0]

    def test_discovers_new_articles_from_server(self, ctx, articles_dir):
        """Server articles not in local DB are pulled."""
        alice = login(ctx, "Alice")
        ctx.transport.fetch_search.return_value = [
            {"id": "new-article-id", "title": "Remote Paper", "status": "draft",
             "authors": [], "publish_consents": []},
        ]

        with patch("peerpedia_core.app.commands.bundle.sync_article"):
            with patch("peerpedia_core.app.commands.bundle.pull_new_article") as mock_pull:
                sync_pull(alice, server="peer.example.com")

        mock_pull.assert_called_once()
        assert mock_pull.call_args[0][3] == "new-article-id"

    def test_notice_when_synced(self, ctx, articles_dir):
        """When articles are synced, a notice is included."""
        from peerpedia_core.app.commands.article import create
        alice = login(ctx, "Alice")
        ctx.transport.fetch_search.return_value = []
        create(alice, title="Paper", content="# X")

        with patch("peerpedia_core.app.commands.bundle.sync_article") as mock_sync:
            mock_sync.return_value = {"synced": True}
            result = sync_pull(alice, server="peer.example.com")

        assert len(result.notices) == 1
        assert result.notices[0].code == "S_SYNCED_COUNT"
        assert result.notices[0].params["count"] == 1

    def test_no_notice_when_nothing_synced(self, ctx):
        """No notice when sync produced no changes."""
        alice = login(ctx, "Alice")
        ctx.transport.fetch_search.return_value = []

        with patch("peerpedia_core.app.commands.bundle.sync_article") as mock_sync:
            mock_sync.return_value = {"synced": False}
            result = sync_pull(alice, server="peer.example.com")

        assert result.notices == []


# ═══════════════════════════════════════════════════════════════════════════════
# sync_discover
# ═══════════════════════════════════════════════════════════════════════════════


class TestSyncDiscover:
    def test_unauthenticated_raises(self, ctx):
        with pytest.raises(NotAuthorizedError, match="UNAUTHORIZED"):
            sync_discover(ctx, server="peer.example.com")

    def test_passes_result_through(self, ctx):
        alice = login(ctx, "Alice")
        expected = {"users": 3, "articles": 5}

        with patch("peerpedia_core.app.commands.bundle.discover_network") as mock_d:
            mock_d.return_value = expected
            result = sync_discover(alice, server="peer.example.com")

        assert result.data == expected

    def test_passes_depth_and_max_users(self, ctx):
        alice = login(ctx, "Alice")

        with patch("peerpedia_core.app.commands.bundle.discover_network") as mock_d:
            mock_d.return_value = {}
            sync_discover(alice, server="peer.example.com", depth=3, max_users=50)

        call_kwargs = mock_d.call_args[1]
        assert call_kwargs["depth"] == 3
        assert call_kwargs["max_users"] == 50

    def test_passes_signing_context(self, ctx):
        """Signing key and pubkey from session are forwarded."""
        alice = login(ctx, "Alice")

        with patch("peerpedia_core.app.commands.bundle.discover_network") as mock_d:
            mock_d.return_value = {}
            sync_discover(alice, server="peer.example.com")

        call_kwargs = mock_d.call_args[1]
        assert call_kwargs["signing_key_bytes"] == alice.signing_key_bytes
        assert call_kwargs["pubkey_hex"] == alice.pubkey_hex
