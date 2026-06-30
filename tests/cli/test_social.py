# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Unit tests for social commands — verify delegation via spec.handler."""

from __future__ import annotations

from argparse import Namespace
from unittest.mock import patch

from peerpedia_core.cli.cmds.social import (
    _cmd_follow, _cmd_unfollow, _cmd_following, _cmd_followers,
    _cmd_alias_set, _cmd_alias_remove, _cmd_alias_list,
    _cmd_bookmark_add, _cmd_bookmark_remove,
    _cmd_share_add, _cmd_share_list, _cmd_share_remove,
    _cmd_school,
)
from tests.cli.conftest import call, mock_spec_handler

_MOD = 'peerpedia_core.cli.cmds.social'


# ── Follow / Unfollow ─────────────────────────────────────────────────────

def test_follow_delegates(ctx):
    with mock_spec_handler(_MOD, 'follow') as h:
        call(_cmd_follow, ctx, Namespace(user_identifier='@alice'))
    h.assert_called_once_with(ctx, {'user_identifier': '@alice'})


def test_unfollow_delegates(ctx):
    with mock_spec_handler(_MOD, 'unfollow') as h:
        call(_cmd_unfollow, ctx, Namespace(user_identifier='@alice'))
    h.assert_called_once_with(ctx, {'user_identifier': '@alice'})


def test_following_delegates(ctx):
    with mock_spec_handler(_MOD, 'following') as h:
        call(_cmd_following, ctx, Namespace(user='@bob'))
    h.assert_called_once_with(ctx, {'user': '@bob'})


def test_followers_delegates(ctx):
    with mock_spec_handler(_MOD, 'followers') as h:
        call(_cmd_followers, ctx, Namespace(user='@bob'))
    h.assert_called_once_with(ctx, {'user': '@bob'})


# ── Alias ─────────────────────────────────────────────────────────────────

def test_alias_set_delegates(ctx):
    with mock_spec_handler(_MOD, 'alias.set') as h:
        call(_cmd_alias_set, ctx, Namespace(user_identifier='@carol', alias='caz'))
    h.assert_called_once_with(ctx, {'user_identifier': '@carol', 'alias': 'caz'})


def test_alias_remove_delegates(ctx):
    with mock_spec_handler(_MOD, 'alias.remove') as h:
        call(_cmd_alias_remove, ctx, Namespace(user_identifier='@carol'))
    h.assert_called_once_with(ctx, {'user_identifier': '@carol'})


def test_alias_list_delegates(ctx):
    with mock_spec_handler(_MOD, 'alias.list') as h:
        call(_cmd_alias_list, ctx, Namespace())
    h.assert_called_once_with(ctx, {})


# ── Bookmark ──────────────────────────────────────────────────────────────

def test_bookmark_add_delegates(ctx):
    with mock_spec_handler(_MOD, 'bookmark.add') as h:
        call(_cmd_bookmark_add, ctx, Namespace(article_id='abc12345'))
    h.assert_called_once_with(ctx, {'article_id': 'abc12345'})


def test_bookmark_remove_delegates(ctx):
    with mock_spec_handler(_MOD, 'bookmark.remove') as h:
        call(_cmd_bookmark_remove, ctx, Namespace(article_id='abc12345'))
    h.assert_called_once_with(ctx, {'article_id': 'abc12345'})


# ── Share ─────────────────────────────────────────────────────────────────

def test_share_add_delegates(ctx):
    with mock_spec_handler(_MOD, 'share.add') as h:
        call(_cmd_share_add, ctx, Namespace(article_id='a1', to='@bob', comment='Check this out'))
    h.assert_called_once_with(ctx, {'article_id': 'a1', 'to': '@bob', 'comment': 'Check this out'})


def test_share_add_no_to_no_comment(ctx):
    with mock_spec_handler(_MOD, 'share.add') as h:
        call(_cmd_share_add, ctx, Namespace(article_id='a1'))
    h.assert_called_once_with(ctx, {'article_id': 'a1', 'to': None, 'comment': None})


def test_share_list_mine(ctx):
    with mock_spec_handler(_MOD, 'share.list') as h:
        call(_cmd_share_list, ctx, Namespace(mine=True))
    h.assert_called_once_with(ctx, {'mine': True})


def test_share_list_feed(ctx):
    with mock_spec_handler(_MOD, 'share.list') as h:
        call(_cmd_share_list, ctx, Namespace())
    h.assert_called_once_with(ctx, {'mine': False})


def test_share_remove_delegates(ctx):
    with mock_spec_handler(_MOD, 'share.remove') as h:
        call(_cmd_share_remove, ctx, Namespace(article_id='a1'))
    h.assert_called_once_with(ctx, {'article_id': 'a1'})


# ── School ────────────────────────────────────────────────────────────────

def test_school_local(ctx):
    with mock_spec_handler(_MOD, 'school') as h:
        call(_cmd_school, ctx, Namespace(local=True, limit=20))
    h.assert_called_once_with(ctx, {'limit': 20, 'local': True, 'server': ''})


def test_school_default_limit(ctx):
    with mock_spec_handler(_MOD, 'school') as h:
        with patch(f'{_MOD}._resolve_server_url', return_value=''):
            call(_cmd_school, ctx, Namespace())
    h.assert_called_once_with(ctx, {'limit': 20, 'local': False, 'server': ''})


def test_school_remote(ctx):
    with mock_spec_handler(_MOD, 'school') as h:
        with patch(f'{_MOD}._resolve_server_url', return_value='https://peer.example.com'):
            call(_cmd_school, ctx, Namespace(limit=10, local=False))
    h.assert_called_once_with(ctx, {'limit': 10, 'local': False, 'server': 'https://peer.example.com'})
