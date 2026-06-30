# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Tests for storage/db/crawler.py — BFS graph crawler for social discovery."""

from unittest.mock import MagicMock

from peerpedia_core.storage.db.engine import get_session
from peerpedia_core.types.entities import FollowExchange, UserExchange

from tests.crud.conftest import make_user


# ═══════════════════════════════════════════════════════════════════════════════
# _fetch_ingest_node
# ═══════════════════════════════════════════════════════════════════════════════


class TestFetchIngestNode:
    def test_success_returns_data(self, engine):
        """Mocked fetch + discover callbacks return neighbors, follows, articles."""
        from peerpedia_core.storage.db.crawler import _fetch_ingest_node

        session = get_session(engine)
        u1 = make_user(session, "alice")

        mock_fetch = MagicMock(return_value=[
            {"id": "peer-bob", "name": "Bob"},
            {"id": "peer-carol", "name": "Carol"},
        ])
        mock_discover = MagicMock(return_value=3)

        result = _fetch_ingest_node(session, "http://server", u1.id,
                                     mock_fetch, mock_discover, [])
        assert result is not None
        assert len(result["neighbors"]) == 2
        assert "peer-bob" in result["neighbors"]
        assert "peer-carol" in result["neighbors"]
        assert result["follows"] == 2
        # discover_fn returns 3 for each of the 2 neighbors → 6 total
        assert result["articles"] == 6
        session.close()

    def test_fetch_fails_returns_none(self, engine):
        """Fetch callback exception → returns None, error recorded."""
        from peerpedia_core.storage.db.crawler import _fetch_ingest_node

        session = get_session(engine)
        u1 = make_user(session, "alice")

        mock_fetch = MagicMock(side_effect=ConnectionError("timeout"))
        mock_discover = MagicMock()
        errors: list[dict[str, str]] = []

        result = _fetch_ingest_node(session, "http://server", u1.id,
                                     mock_fetch, mock_discover, errors)
        assert result is None
        assert len(errors) == 1
        assert errors[0]["stage"] == "following"
        assert errors[0]["error"] == "fetch_failed"
        session.close()

    def test_empty_data_returns_none(self, engine):
        """Empty fetch data (not an error, just no follows) → returns None."""
        from peerpedia_core.storage.db.crawler import _fetch_ingest_node

        session = get_session(engine)
        u1 = make_user(session, "alice")

        mock_fetch = MagicMock(return_value=[])
        mock_discover = MagicMock()

        result = _fetch_ingest_node(session, "http://server", u1.id,
                                     mock_fetch, mock_discover, [])
        assert result is None  # empty data → no node to process
        session.close()


# ═══════════════════════════════════════════════════════════════════════════════
# _bfs_walk
# ═══════════════════════════════════════════════════════════════════════════════


class TestBfsWalk:
    def test_traverses_graph(self, engine):
        """BFS from start user reaches configured depth and collects results."""
        from peerpedia_core.storage.db.crawler import _bfs_walk

        session = get_session(engine)
        alice = make_user(session, "alice")

        # Mock: alice follows bob; bob follows carol (depth-2 chain)
        call_count = 0
        def mock_fetch(server, user_id):
            nonlocal call_count
            call_count += 1
            if call_count == 1:  # alice → bob
                return [{"id": "peer-bob", "name": "Bob"}]
            elif call_count == 2:  # bob → carol
                return [{"id": "peer-carol", "name": "Carol"}]
            return []

        mock_discover = MagicMock(return_value=0)

        result = _bfs_walk(
            session, "http://server", alice.id,
            depth=2, max_users=10,
            fetch_following_fn=mock_fetch,
            discover_articles_fn=mock_discover,
        )
        assert result["users_discovered"] >= 1
        assert result["depth_reached"] >= 1
        assert result["follows_added"] >= 1
        session.close()

    def test_errors_collected(self, engine):
        """Multiple fetch failures are all captured in the errors list."""
        from peerpedia_core.storage.db.crawler import _bfs_walk

        session = get_session(engine)
        alice = make_user(session, "alice")

        mock_fetch = MagicMock(side_effect=ConnectionError("always fails"))
        mock_discover = MagicMock()

        result = _bfs_walk(
            session, "http://server", alice.id,
            depth=1, max_users=10,
            fetch_following_fn=mock_fetch,
            discover_articles_fn=mock_discover,
        )
        assert len(result["errors"]) >= 1
        assert result["users_discovered"] >= 1  # the start user is counted
        session.close()
