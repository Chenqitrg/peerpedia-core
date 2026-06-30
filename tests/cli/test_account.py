# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Unit tests for account commands — verify delegation via spec.handler."""

from __future__ import annotations

from argparse import Namespace
from unittest.mock import patch

from peerpedia_core.cli.cmds.account import (
    _cmd_account_register,
    _cmd_account_login,
    _cmd_account_recover,
    _cmd_account_whoami,
    _cmd_account_bootstrap,
    _cmd_account_delete,
    _cmd_account_search,
)
from tests.cli.conftest import call, mock_spec_handler

_MOD = 'peerpedia_core.cli.cmds.account'


# ── Register ───────────────────────────────────────────────────────────────

def test_register_delegates(ctx):
    with mock_spec_handler(_MOD, 'account.register') as handler:
        with patch(f'{_MOD}._get_password', return_value='secret'):
            call(_cmd_account_register, ctx, Namespace(name='Alice'))
    handler.assert_called_once_with(ctx, {'name': 'Alice', 'password': 'secret'})


# ── Login ──────────────────────────────────────────────────────────────────

def test_login_delegates(ctx):
    with mock_spec_handler(_MOD, 'account.login') as handler:
        with patch(f'{_MOD}._get_password', return_value='pass'):
            call(_cmd_account_login, ctx, Namespace(name='Bob'))
    handler.assert_called_once_with(ctx, {'name': 'Bob', 'password': 'pass'})


# ── Recover ────────────────────────────────────────────────────────────────

def test_recover_delegates_with_name(ctx):
    with mock_spec_handler(_MOD, 'account.recover') as handler:
        with patch(f'{_MOD}._get_password', return_value='pw'):
            call(_cmd_account_recover, ctx, Namespace(name='Carol', user_id=None))
    handler.assert_called_once_with(ctx, {'name': 'Carol', 'user_id': None, 'password': 'pw'})


def test_recover_delegates_with_user_id(ctx):
    with mock_spec_handler(_MOD, 'account.recover') as handler:
        with patch(f'{_MOD}._get_password', return_value='pw'):
            call(_cmd_account_recover, ctx, Namespace(name=None, user_id='uuid-123'))
    handler.assert_called_once_with(ctx, {'name': None, 'user_id': 'uuid-123', 'password': 'pw'})


# ── Whoami ─────────────────────────────────────────────────────────────────

def test_whoami_delegates(ctx):
    with mock_spec_handler(_MOD, 'account.whoami') as handler:
        call(_cmd_account_whoami, ctx, Namespace())
    handler.assert_called_once_with(ctx, {})


# ── Bootstrap ──────────────────────────────────────────────────────────────

def test_bootstrap_delegates_without_peer(ctx):
    with mock_spec_handler(_MOD, 'account.bootstrap') as handler:
        call(_cmd_account_bootstrap, ctx, Namespace(from_='{"name":"X"}'))
    handler.assert_called_once_with(ctx, {'from_': '{"name":"X"}', 'peer': None})


def test_bootstrap_delegates_with_peer(ctx):
    with mock_spec_handler(_MOD, 'account.bootstrap') as handler:
        call(_cmd_account_bootstrap, ctx, Namespace(from_='{}', peer='https://p.example.com'))
    handler.assert_called_once_with(ctx, {'from_': '{}', 'peer': 'https://p.example.com'})


# ── Delete ─────────────────────────────────────────────────────────────────

def test_delete_delegates(ctx):
    with mock_spec_handler(_MOD, 'account.delete') as handler:
        call(_cmd_account_delete, ctx, Namespace())
    handler.assert_called_once_with(ctx, {})


# ── Search ─────────────────────────────────────────────────────────────────

def test_search_delegates_with_query(ctx):
    with mock_spec_handler(_MOD, 'account.search') as handler:
        call(_cmd_account_search, ctx, Namespace(query='Ali'))
    handler.assert_called_once_with(ctx, {'query': 'Ali'})


def test_search_delegates_with_empty_query(ctx):
    with mock_spec_handler(_MOD, 'account.search') as handler:
        call(_cmd_account_search, ctx, Namespace())
    handler.assert_called_once_with(ctx, {'query': ''})
