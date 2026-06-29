# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Unit tests for social commands — verify delegation to app layer."""

from __future__ import annotations

from argparse import Namespace
from unittest.mock import patch

from peerpedia_core.cli.cmds.social import (
    _cmd_follow,
    _cmd_unfollow,
    _cmd_following,
    _cmd_followers,
    _cmd_alias_set,
    _cmd_alias_remove,
    _cmd_alias_list,
    _cmd_bookmark_add,
    _cmd_bookmark_remove,
    _cmd_share_add,
    _cmd_share_list,
    _cmd_share_remove,
    _cmd_school,
)
from tests.cli.conftest import call, mock_cmd


_MOD = 'peerpedia_core.cli.cmds.social'


# ── Follow / Unfollow ─────────────────────────────────────────────────────

def test_follow_delegates(ctx):
    with mock_cmd(_MOD, '_social') as app:
        call(_cmd_follow, ctx, Namespace(user_identifier='@alice'))
    app.follow.assert_called_once_with(ctx, target_ref='@alice')


def test_unfollow_delegates(ctx):
    with mock_cmd(_MOD, '_social') as app:
        call(_cmd_unfollow, ctx, Namespace(user_identifier='@alice'))
    app.unfollow.assert_called_once_with(ctx, target_ref='@alice')


def test_following_delegates(ctx):
    with mock_cmd(_MOD, '_social') as app:
        call(_cmd_following, ctx, Namespace(user='@bob'))
    app.list_following.assert_called_once_with(ctx, user_ref='@bob')


def test_followers_delegates(ctx):
    with mock_cmd(_MOD, '_social') as app:
        call(_cmd_followers, ctx, Namespace(user='@bob'))
    app.list_followers.assert_called_once_with(ctx, user_ref='@bob')


# ── Alias ─────────────────────────────────────────────────────────────────

def test_alias_set_delegates(ctx):
    with mock_cmd(_MOD, '_social') as app:
        call(_cmd_alias_set, ctx, Namespace(user_identifier='@eve', alias='ev'))
    app.alias.assert_called_once_with(ctx, user_ref='@eve', alias='ev')


def test_alias_remove_delegates(ctx):
    with mock_cmd(_MOD, '_social') as app:
        call(_cmd_alias_remove, ctx, Namespace(user_identifier='@eve'))
    app.unalias.assert_called_once_with(ctx, user_ref='@eve')


def test_alias_list_delegates(ctx):
    with mock_cmd(_MOD, '_social') as app:
        call(_cmd_alias_list, ctx, Namespace())
    app.alias_list.assert_called_once_with(ctx)


# ── Bookmark ──────────────────────────────────────────────────────────────

def test_bookmark_add_delegates(ctx):
    with mock_cmd(_MOD, '_social') as app:
        call(_cmd_bookmark_add, ctx, Namespace(article_id='abc12345'))
    app.bookmark.assert_called_once_with(ctx, article_ref='abc12345')


def test_bookmark_remove_delegates(ctx):
    with mock_cmd(_MOD, '_social') as app:
        call(_cmd_bookmark_remove, ctx, Namespace(article_id='abc12345'))
    app.unbookmark.assert_called_once_with(ctx, article_ref='abc12345')


# ── Share ─────────────────────────────────────────────────────────────────

def test_share_add_delegates(ctx):
    with mock_cmd(_MOD, '_social') as app:
        call(_cmd_share_add, ctx, Namespace(article_id='abc', to='@bob', comment='nice'))
    app.share.assert_called_once_with(ctx, article_ref='abc',
        to_ref='@bob', comment='nice')


def test_share_add_without_to_or_comment(ctx):
    with mock_cmd(_MOD, '_social') as app:
        call(_cmd_share_add, ctx, Namespace(article_id='abc'))
    app.share.assert_called_once_with(ctx, article_ref='abc',
        to_ref=None, comment=None)


def test_share_list_delegates(ctx):
    with mock_cmd(_MOD, '_social') as app:
        call(_cmd_share_list, ctx, Namespace(mine=False))
    app.share_list.assert_called_once_with(ctx, mine=False)


def test_share_list_mine(ctx):
    with mock_cmd(_MOD, '_social') as app:
        call(_cmd_share_list, ctx, Namespace(mine=True))
    app.share_list.assert_called_once_with(ctx, mine=True)


def test_share_remove_delegates(ctx):
    with mock_cmd(_MOD, '_social') as app:
        call(_cmd_share_remove, ctx, Namespace(article_id='abc'))
    app.unshare.assert_called_once_with(ctx, article_ref='abc')


# ── School ────────────────────────────────────────────────────────────────

def test_school_local(ctx):
    with mock_cmd(_MOD, '_social') as app:
        call(_cmd_school, ctx, Namespace(limit=5, local=True))
    app.school.assert_called_once_with(ctx, limit=5, local=True, server='')


def test_school_default_limit(ctx):
    with mock_cmd(_MOD, '_social') as app:
        with patch(f'{_MOD}._resolve_server_url', return_value='https://p.example.com'):
            call(_cmd_school, ctx, Namespace(limit=None, local=False))
    app.school.assert_called_once_with(
        ctx, limit=20, local=False, server='https://p.example.com')
