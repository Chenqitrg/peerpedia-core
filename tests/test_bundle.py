# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Tests for sync module."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from peerpedia_core.transport.health import clear_health_cache, is_online
from peerpedia_core.bundle.pending import add, clear, count, list_all, remove


# ── Network tests ────────────────────────────────────────────────────────


def test_is_online_returns_true_for_200():
    clear_health_cache()
    mock_client = MagicMock()
    mock_client.get.return_value.status_code = 200
    with patch("peerpedia_core.transport.health._get_client", return_value=mock_client):
        assert is_online("http://example.com") is True


def test_is_online_returns_false_for_500():
    clear_health_cache()
    mock_client = MagicMock()
    mock_client.get.return_value.status_code = 500
    with patch("peerpedia_core.transport.health._get_client", return_value=mock_client):
        assert is_online("http://example.com") is False


def test_is_online_returns_false_for_network_error():
    clear_health_cache()
    import httpx
    mock_client = MagicMock()
    mock_client.get.side_effect = httpx.ConnectError("Connection refused")
    with patch("peerpedia_core.transport.health._get_client", return_value=mock_client):
        assert is_online("http://example.com") is False


# ── Pending queue tests ──────────────────────────────────────────────────


def test_pending_queue_add_and_list():
    clear()
    add("push", "art-1")
    add("delete", "art-2")

    ops = list_all()
    assert len(ops) == 2
    assert ops[0]["id"] == "art-1"
    assert ops[0]["op_type"] == "push"
    assert ops[1]["id"] == "art-2"
    assert ops[1]["op_type"] == "delete"
    clear()


def test_pending_queue_dedup():
    clear()
    add("push", "art-1")
    add("push", "art-1")  # duplicate
    assert count() == 1
    clear()


def test_pending_queue_remove():
    clear()
    add("push", "art-1")
    add("push", "art-2")
    remove("art-1")
    assert count() == 1
    assert list_all()[0]["id"] == "art-2"
    clear()


def test_pending_queue_count():
    clear()
    assert count() == 0
    add("push", "art-1")
    assert count() == 1
    clear()
    assert count() == 0
