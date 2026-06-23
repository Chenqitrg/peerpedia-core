# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Tests for social discovery HTTP transport functions."""

from unittest.mock import patch

import httpx
import pytest

from peerpedia_core.exceptions import TransportError
from peerpedia_core.transport.http_client import (
    fetch_articles,
    fetch_followers,
    fetch_following,
)


class TestFetchFollowing:
    def test_success(self):
        mock_resp = httpx.Response(200, json=[{"id": "bob", "name": "Bob"}])
        with patch("peerpedia_core.transport.http_client.httpx.get", return_value=mock_resp):
            result = fetch_following("http://peer:8080", "alice")
        assert result == [{"id": "bob", "name": "Bob"}]

    def test_404_returns_none(self):
        mock_resp = httpx.Response(404)
        with patch("peerpedia_core.transport.http_client.httpx.get", return_value=mock_resp):
            result = fetch_following("http://peer:8080", "alice")
        assert result is None

    def test_network_error_raises_transport_error(self):
        with patch("peerpedia_core.transport.http_client.httpx.get",
                   side_effect=httpx.ConnectError("Connection refused")):
            with pytest.raises(TransportError, match="fetch_following failed"):
                fetch_following("http://peer:8080", "alice")

    def test_non_http_error_propagates(self):
        """Programming errors (not httpx.HTTPError) propagate — fail fast."""
        with patch("peerpedia_core.transport.http_client.httpx.get",
                   side_effect=TypeError("unhashable")):
            with pytest.raises(TypeError):
                fetch_following("http://peer:8080", "alice")


class TestFetchFollowers:
    def test_success(self):
        mock_resp = httpx.Response(200, json=[{"id": "carol", "name": "Carol"}])
        with patch("peerpedia_core.transport.http_client.httpx.get", return_value=mock_resp):
            result = fetch_followers("http://peer:8080", "bob")
        assert result == [{"id": "carol", "name": "Carol"}]


class TestFetchArticles:
    def test_pagination_params(self):
        mock_resp = httpx.Response(200, json=[])
        with patch("peerpedia_core.transport.http_client.httpx.get") as mock_get:
            mock_get.return_value = mock_resp
            fetch_articles("http://peer:8080", "alice", limit=5, offset=10)
            call_kwargs = mock_get.call_args.kwargs
            assert call_kwargs["params"] == {"limit": 5, "offset": 10}

    def test_success(self):
        mock_resp = httpx.Response(200, json=[{"id": "art-1", "title": "Paper", "status": "published"}])
        with patch("peerpedia_core.transport.http_client.httpx.get", return_value=mock_resp):
            result = fetch_articles("http://peer:8080", "alice")
        assert result == [{"id": "art-1", "title": "Paper", "status": "published"}]
