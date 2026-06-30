# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Unit tests for sync commands — verify delegation via spec.handler."""

from __future__ import annotations

from argparse import Namespace
from unittest.mock import patch

from peerpedia_core.cli.cmds.sync import _cmd_sync_status, _cmd_sync_pull, _cmd_sync_discover
from tests.cli.conftest import call, mock_spec_handler

_MOD = 'peerpedia_core.cli.cmds.sync'


def _resolve(return_value='https://p.example.com'):
    return patch(f'{_MOD}._resolve_server_url', return_value=return_value)


# ── Sync status ───────────────────────────────────────────────────────────

def test_sync_status_delegates(ctx):
    with mock_spec_handler(_MOD, 'sync.status') as h, _resolve():
        call(_cmd_sync_status, ctx, Namespace())
    h.assert_called_once_with(ctx, {'server': 'https://p.example.com'})


def test_sync_status_passes_server_directly(ctx):
    with mock_spec_handler(_MOD, 'sync.status') as h:
        with patch(f'{_MOD}._resolve_server_url', return_value='https://custom.example.com'):
            call(_cmd_sync_status, ctx, Namespace(server='https://custom.example.com'))
    h.assert_called_once_with(ctx, {'server': 'https://custom.example.com'})


def test_sync_status_resolved_url(ctx):
    with mock_spec_handler(_MOD, 'sync.status') as h, _resolve('https://env.example.com'):
        call(_cmd_sync_status, ctx, Namespace())
    h.assert_called_once_with(ctx, {'server': 'https://env.example.com'})


# ── Sync pull ─────────────────────────────────────────────────────────────

def test_sync_pull_delegates(ctx):
    with mock_spec_handler(_MOD, 'sync.pull') as h, _resolve():
        call(_cmd_sync_pull, ctx, Namespace())
    h.assert_called_once_with(ctx, {'server': 'https://p.example.com'})


def test_sync_pull_with_explicit_server(ctx):
    with mock_spec_handler(_MOD, 'sync.pull') as h:
        with patch(f'{_MOD}._resolve_server_url', return_value='https://explicit.example.com'):
            call(_cmd_sync_pull, ctx, Namespace(server='https://explicit.example.com'))
    h.assert_called_once_with(ctx, {'server': 'https://explicit.example.com'})


# ── Sync discover ─────────────────────────────────────────────────────────

def test_sync_discover_defaults(ctx):
    with mock_spec_handler(_MOD, 'sync.discover') as h, _resolve():
        call(_cmd_sync_discover, ctx, Namespace())
    h.assert_called_once_with(ctx, {'server': 'https://p.example.com', 'depth': 1, 'max_users': 100})


def test_sync_discover_custom(ctx):
    with mock_spec_handler(_MOD, 'sync.discover') as h, _resolve():
        call(_cmd_sync_discover, ctx, Namespace(depth=3, max_users=50))
    h.assert_called_once_with(ctx, {'server': 'https://p.example.com', 'depth': 3, 'max_users': 50})


def test_sync_discover_depth_zero_falls_back_to_default(ctx):
    with mock_spec_handler(_MOD, 'sync.discover') as h, _resolve():
        call(_cmd_sync_discover, ctx, Namespace(depth=0, max_users=100))
    h.assert_called_once_with(ctx, {'server': 'https://p.example.com', 'depth': 1, 'max_users': 100})


def test_sync_discover_depth_none_falls_back(ctx):
    with mock_spec_handler(_MOD, 'sync.discover') as h, _resolve():
        call(_cmd_sync_discover, ctx, Namespace(depth=None, max_users=100))
    h.assert_called_once_with(ctx, {'server': 'https://p.example.com', 'depth': 1, 'max_users': 100})


def test_sync_discover_depth_negative(ctx):
    with mock_spec_handler(_MOD, 'sync.discover') as h, _resolve():
        call(_cmd_sync_discover, ctx, Namespace(depth=-1, max_users=100))
    h.assert_called_once_with(ctx, {'server': 'https://p.example.com', 'depth': -1, 'max_users': 100})


def test_sync_discover_max_users_zero_falls_back(ctx):
    with mock_spec_handler(_MOD, 'sync.discover') as h, _resolve():
        call(_cmd_sync_discover, ctx, Namespace(depth=2, max_users=0))
    h.assert_called_once_with(ctx, {'server': 'https://p.example.com', 'depth': 2, 'max_users': 100})


def test_sync_discover_max_users_none_falls_back(ctx):
    with mock_spec_handler(_MOD, 'sync.discover') as h, _resolve():
        call(_cmd_sync_discover, ctx, Namespace(depth=2, max_users=None))
    h.assert_called_once_with(ctx, {'server': 'https://p.example.com', 'depth': 2, 'max_users': 100})


def test_sync_discover_large_depth(ctx):
    with mock_spec_handler(_MOD, 'sync.discover') as h, _resolve():
        call(_cmd_sync_discover, ctx, Namespace(depth=100, max_users=10000))
    h.assert_called_once_with(ctx, {'server': 'https://p.example.com', 'depth': 100, 'max_users': 10000})


def test_sync_discover_with_explicit_server(ctx):
    with mock_spec_handler(_MOD, 'sync.discover') as h:
        with patch(f'{_MOD}._resolve_server_url', return_value='https://override.example.com'):
            call(_cmd_sync_discover, ctx, Namespace(server='https://override.example.com', depth=2))
    h.assert_called_once_with(ctx, {'server': 'https://override.example.com', 'depth': 2, 'max_users': 100})


def test_sync_all_three_commands_same_url(ctx):
    url = 'https://peer.shared.example.com'
    with mock_spec_handler(_MOD, 'sync.status') as h1, _resolve(url):
        call(_cmd_sync_status, ctx, Namespace(server=url))
    h1.assert_called_once_with(ctx, {'server': url})

    with mock_spec_handler(_MOD, 'sync.pull') as h2, _resolve(url):
        call(_cmd_sync_pull, ctx, Namespace(server=url))
    h2.assert_called_once_with(ctx, {'server': url})

    with mock_spec_handler(_MOD, 'sync.discover') as h3, _resolve(url):
        call(_cmd_sync_discover, ctx, Namespace(server=url, depth=5))
    h3.assert_called_once_with(ctx, {'server': url, 'depth': 5, 'max_users': 100})
