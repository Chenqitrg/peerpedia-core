# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Unit tests for sync commands."""

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


def test_sync_status_delegates(ctx):
    with mock_cmd(_MOD, '_bundle') as app:
        with patch(f'{_MOD}._resolve_server_url', return_value='https://p.example.com'):
            call(_cmd_sync_status, ctx, Namespace())
    app.sync_status.assert_called_once_with(ctx, server='https://p.example.com')


def test_sync_pull_delegates(ctx):
    with mock_cmd(_MOD, '_bundle') as app:
        with patch(f'{_MOD}._resolve_server_url', return_value='https://p.example.com'):
            call(_cmd_sync_pull, ctx, Namespace())
    app.sync_pull.assert_called_once_with(ctx, server='https://p.example.com')


def test_sync_discover_defaults(ctx):
    with mock_cmd(_MOD, '_bundle') as app:
        with patch(f'{_MOD}._resolve_server_url', return_value='https://p.example.com'):
            call(_cmd_sync_discover, ctx, Namespace())
    app.sync_discover.assert_called_once_with(
        ctx, server='https://p.example.com', depth=1, max_users=100)


def test_sync_discover_custom(ctx):
    with mock_cmd(_MOD, '_bundle') as app:
        with patch(f'{_MOD}._resolve_server_url', return_value='https://p.example.com'):
            call(_cmd_sync_discover, ctx, Namespace(depth=3, max_users=50))
    app.sync_discover.assert_called_once_with(
        ctx, server='https://p.example.com', depth=3, max_users=50)
