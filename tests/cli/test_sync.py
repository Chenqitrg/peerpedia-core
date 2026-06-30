# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Unit tests for sync commands.

Network operations have historically been the most brittle area —
these tests verify parameter mapping and URL resolution for every edge case.
"""

from __future__ import annotations

from argparse import Namespace
from unittest.mock import patch

from peerpedia_core.cli.cmds.sync import (
    _cmd_sync_status,
    _cmd_sync_pull,
    _cmd_sync_discover,
)
from tests.cli.conftest import call, mock_cmd

_MOD = 'peerpedia_core.cli.cmds.sync'


# ── Helpers ───────────────────────────────────────────────────────────────

def _resolve(return_value='https://p.example.com'):
    return patch(f'{_MOD}._resolve_server_url', return_value=return_value)


# ── Sync status ───────────────────────────────────────────────────────────

def test_sync_status_delegates(ctx):
    with mock_cmd(_MOD, '_bundle') as app, _resolve():
        call(_cmd_sync_status, ctx, Namespace())
    app.sync_status.assert_called_once_with(ctx, server='https://p.example.com')


def test_sync_status_passes_server_directly(ctx):
    """--server flag should take priority over env var."""
    with mock_cmd(_MOD, '_bundle') as app:
        with patch(f'{_MOD}._resolve_server_url', return_value='https://custom.example.com'):
            call(_cmd_sync_status, ctx, Namespace(server='https://custom.example.com'))
    app.sync_status.assert_called_once_with(ctx, server='https://custom.example.com')


def test_sync_status_resolved_url(ctx):
    """When --server is unset, _resolve_server_url is called (env/file fallback)."""
    with mock_cmd(_MOD, '_bundle') as app, _resolve('https://env.example.com'):
        call(_cmd_sync_status, ctx, Namespace())
    app.sync_status.assert_called_once_with(ctx, server='https://env.example.com')


# ── Sync pull ─────────────────────────────────────────────────────────────

def test_sync_pull_delegates(ctx):
    with mock_cmd(_MOD, '_bundle') as app, _resolve():
        call(_cmd_sync_pull, ctx, Namespace())
    app.sync_pull.assert_called_once_with(ctx, server='https://p.example.com')


def test_sync_pull_with_explicit_server(ctx):
    with mock_cmd(_MOD, '_bundle') as app:
        with patch(f'{_MOD}._resolve_server_url', return_value='https://explicit.example.com'):
            call(_cmd_sync_pull, ctx, Namespace(server='https://explicit.example.com'))
    app.sync_pull.assert_called_once_with(
        ctx, server='https://explicit.example.com')


# ── Sync discover defaults ────────────────────────────────────────────────

def test_sync_discover_defaults(ctx):
    """depth=1, max_users=100 when not specified."""
    with mock_cmd(_MOD, '_bundle') as app, _resolve():
        call(_cmd_sync_discover, ctx, Namespace())
    app.sync_discover.assert_called_once_with(
        ctx, server='https://p.example.com', depth=1, max_users=100)


def test_sync_discover_custom(ctx):
    with mock_cmd(_MOD, '_bundle') as app, _resolve():
        call(_cmd_sync_discover, ctx, Namespace(depth=3, max_users=50))
    app.sync_discover.assert_called_once_with(
        ctx, server='https://p.example.com', depth=3, max_users=50)


# ── Sync discover depth edge cases ────────────────────────────────────────

def test_sync_discover_depth_zero_falls_back_to_default(ctx):
    """depth=0 is falsy → falls back to default 1."""
    with mock_cmd(_MOD, '_bundle') as app, _resolve():
        call(_cmd_sync_discover, ctx, Namespace(depth=0, max_users=100))
    app.sync_discover.assert_called_once_with(
        ctx, server='https://p.example.com', depth=1, max_users=100)


def test_sync_discover_depth_none_falls_back(ctx):
    with mock_cmd(_MOD, '_bundle') as app, _resolve():
        call(_cmd_sync_discover, ctx, Namespace(depth=None, max_users=100))
    app.sync_discover.assert_called_once_with(
        ctx, server='https://p.example.com', depth=1, max_users=100)


def test_sync_discover_depth_negative(ctx):
    """Negative depth passes through — validation is the app layer's job."""
    with mock_cmd(_MOD, '_bundle') as app, _resolve():
        call(_cmd_sync_discover, ctx, Namespace(depth=-1, max_users=100))
    app.sync_discover.assert_called_once_with(
        ctx, server='https://p.example.com', depth=-1, max_users=100)


def test_sync_discover_max_users_zero_falls_back(ctx):
    """max_users=0 is falsy → falls back to default 100."""
    with mock_cmd(_MOD, '_bundle') as app, _resolve():
        call(_cmd_sync_discover, ctx, Namespace(depth=2, max_users=0))
    app.sync_discover.assert_called_once_with(
        ctx, server='https://p.example.com', depth=2, max_users=100)


def test_sync_discover_max_users_none_falls_back(ctx):
    with mock_cmd(_MOD, '_bundle') as app, _resolve():
        call(_cmd_sync_discover, ctx, Namespace(depth=2, max_users=None))
    app.sync_discover.assert_called_once_with(
        ctx, server='https://p.example.com', depth=2, max_users=100)


def test_sync_discover_large_depth(ctx):
    """Large values pass through — capping is the app layer's job."""
    with mock_cmd(_MOD, '_bundle') as app, _resolve():
        call(_cmd_sync_discover, ctx, Namespace(depth=100, max_users=10000))
    app.sync_discover.assert_called_once_with(
        ctx, server='https://p.example.com', depth=100, max_users=10000)


# ── Sync discover server resolution ───────────────────────────────────────

def test_sync_discover_with_explicit_server(ctx):
    with mock_cmd(_MOD, '_bundle') as app:
        with patch(f'{_MOD}._resolve_server_url', return_value='https://override.example.com'):
            call(_cmd_sync_discover, ctx, Namespace(
                server='https://override.example.com', depth=2))
    app.sync_discover.assert_called_once_with(
        ctx, server='https://override.example.com', depth=2, max_users=100)


# ── URL resolution edge cases ─────────────────────────────────────────────

def test_sync_all_three_commands_same_url(ctx):
    """Status, pull, and discover should all resolve the same server URL."""
    url = 'https://peer.shared.example.com'
    with mock_cmd(_MOD, '_bundle') as app, _resolve(url):
        call(_cmd_sync_status, ctx, Namespace(server=url))
        call(_cmd_sync_pull, ctx, Namespace(server=url))
        call(_cmd_sync_discover, ctx, Namespace(server=url, depth=5))
    app.sync_status.assert_called_once_with(ctx, server=url)
    app.sync_pull.assert_called_once_with(ctx, server=url)
    app.sync_discover.assert_called_once_with(
        ctx, server=url, depth=5, max_users=100)
