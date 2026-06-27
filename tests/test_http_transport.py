# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Tests for social discovery HTTP transport functions."""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from peerpedia_core.exceptions import TransportError
from peerpedia_core.transport import (
    fetch_user_articles,
    fetch_followers,
    fetch_following,
    push_key_rotation,
)


def _mock_client(get=None, post=None):
    """Return a mock httpx.Client-like object."""
    client = MagicMock()
    if get is not None:
        client.get = get
    if post is not None:
        client.post = post
    return client


class TestFetchFollowing:
    def test_success(self):
        mock_resp = httpx.Response(200, json=[{"id": "bob", "name": "Bob"}])
        client = _mock_client(get=MagicMock(return_value=mock_resp))
        with patch("peerpedia_core.transport._http_core._get_client", return_value=client):
            result = fetch_following("http://peer:8080", "alice")
        assert result == [{"id": "bob", "name": "Bob"}]

    def test_404_returns_none(self):
        mock_resp = httpx.Response(404)
        client = _mock_client(get=MagicMock(return_value=mock_resp))
        with patch("peerpedia_core.transport._http_core._get_client", return_value=client):
            result = fetch_following("http://peer:8080", "alice")
        assert result is None

    def test_network_error_raises_transport_error(self):
        client = _mock_client(get=MagicMock(side_effect=httpx.ConnectError("Connection refused")))
        with patch("peerpedia_core.transport._http_core._get_client", return_value=client):
            with pytest.raises(TransportError, match="fetch_following failed"):
                fetch_following("http://peer:8080", "alice")

    def test_non_http_error_propagates(self):
        """Programming errors (not httpx.HTTPError) propagate — fail fast."""
        client = _mock_client(get=MagicMock(side_effect=TypeError("unhashable")))
        with patch("peerpedia_core.transport._http_core._get_client", return_value=client):
            with pytest.raises(TypeError):
                fetch_following("http://peer:8080", "alice")


class TestFetchFollowers:
    def test_success(self):
        mock_resp = httpx.Response(200, json=[{"id": "carol", "name": "Carol"}])
        client = _mock_client(get=MagicMock(return_value=mock_resp))
        with patch("peerpedia_core.transport._http_core._get_client", return_value=client):
            result = fetch_followers("http://peer:8080", "bob")
        assert result == [{"id": "carol", "name": "Carol"}]


class TestFetchArticles:
    def test_pagination_params(self):
        mock_resp = httpx.Response(200, json=[])
        mock_get = MagicMock(return_value=mock_resp)
        client = _mock_client(get=mock_get)
        with patch("peerpedia_core.transport._http_core._get_client", return_value=client):
            fetch_user_articles("http://peer:8080", "alice", limit=5, offset=10)
            call_kwargs = mock_get.call_args.kwargs
            assert call_kwargs["params"] == {"limit": 5, "offset": 10}

    def test_success(self):
        mock_resp = httpx.Response(200, json=[{"id": "art-1", "title": "Paper", "status": "published"}])
        client = _mock_client(get=MagicMock(return_value=mock_resp))
        with patch("peerpedia_core.transport._http_core._get_client", return_value=client):
            result = fetch_user_articles("http://peer:8080", "alice")
        assert result == [{"id": "art-1", "title": "Paper", "status": "published"}]


class TestPushKeyRotation:
    def test_success_200(self):
        mock_resp = httpx.Response(200)
        client = _mock_client(post=MagicMock(return_value=mock_resp))
        with patch("peerpedia_core.transport._http_core._get_client", return_value=client):
            result = push_key_rotation(
                "http://peer:8080", "alice", "aa" * 32,
                private_key_bytes=b"\x00" * 32,
            )
        assert result is True

    def test_404_returns_false(self):
        mock_resp = httpx.Response(404)
        client = _mock_client(post=MagicMock(return_value=mock_resp))
        with patch("peerpedia_core.transport._http_core._get_client", return_value=client):
            result = push_key_rotation(
                "http://peer:8080", "alice", "aa" * 32,
                private_key_bytes=b"\x00" * 32,
            )
        assert result is False

    def test_network_error_raises(self):
        client = _mock_client(post=MagicMock(side_effect=httpx.ConnectError("down")))
        with patch("peerpedia_core.transport._http_core._get_client", return_value=client):
            with pytest.raises(TransportError):
                push_key_rotation(
                    "http://peer:8080", "alice", "aa" * 32,
                    private_key_bytes=b"\x00" * 32,
                )


# ── push_peer_registration ──────────────────────────────────────────────────


class TestPushPeerRegistration:
    def test_returns_true_on_200(self):
        mock_resp = httpx.Response(200)
        client = _mock_client(post=MagicMock(return_value=mock_resp))
        with patch("peerpedia_core.transport._http_core._get_client", return_value=client):
            from peerpedia_core.transport.http_client import push_peer_registration
            result = push_peer_registration("http://peer:8080", "https://me.example.com")
            assert result is True

    def test_non_200_raises_protocol_error(self):
        mock_resp = httpx.Response(500)
        client = _mock_client(post=MagicMock(return_value=mock_resp))
        with patch("peerpedia_core.transport._http_core._get_client", return_value=client):
            from peerpedia_core.transport.http_client import push_peer_registration
            from peerpedia_core.exceptions import ProtocolError
            with pytest.raises(ProtocolError):
                push_peer_registration("http://peer:8080", "https://me.example.com")

    def test_network_error_raises_transport_error(self):
        client = _mock_client(post=MagicMock(side_effect=httpx.ConnectError("down")))
        with patch("peerpedia_core.transport._http_core._get_client", return_value=client):
            from peerpedia_core.transport.http_client import push_peer_registration
            with pytest.raises(TransportError):
                push_peer_registration("http://peer:8080", "https://me.example.com")
