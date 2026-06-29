# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Unit tests for review commands."""

from __future__ import annotations

from argparse import Namespace
from unittest.mock import patch

from peerpedia_core.cli.cmds.reviews import (
    _cmd_review_submit,
    _cmd_review_list,
    _cmd_review_reply,
    _cmd_review_invite,
    _cmd_review_accept,
    _cmd_review_decline,
    _cmd_review_rate,
    _edit_reply,
)
from tests.cli.conftest import call, mock_cmd

_MOD = 'peerpedia_core.cli.cmds.reviews'


# ── Submit ────────────────────────────────────────────────────────────────

def test_review_submit_delegates(ctx):
    with mock_cmd(_MOD, '_review') as app:
        call(_cmd_review_submit, ctx,
             Namespace(article_id='a1', scores='orig=4,rigor=3', comment='Nice paper'))
    app.submit.assert_called_once_with(ctx, article_ref='a1',
        scores_str='orig=4,rigor=3', comment='Nice paper')


def test_review_submit_empty_comment(ctx):
    with mock_cmd(_MOD, '_review') as app:
        call(_cmd_review_submit, ctx,
             Namespace(article_id='a1', scores='orig=4', comment=None))
    app.submit.assert_called_once_with(ctx, article_ref='a1',
        scores_str='orig=4', comment='')


# ── List ──────────────────────────────────────────────────────────────────

def test_review_list_delegates(ctx):
    with mock_cmd(_MOD, '_review') as app:
        call(_cmd_review_list, ctx, Namespace(article_id='a1'))
    app.list_reviews.assert_called_once_with(ctx, article_ref='a1')


# ── Reply ─────────────────────────────────────────────────────────────────

def test_review_reply_delegates(ctx):
    with mock_cmd(_MOD, '_review') as app:
        with patch(f'{_MOD}._edit_reply', return_value='Thanks for the review!'):
            call(_cmd_review_reply, ctx, Namespace(article_id='a1', to='@bob'))
    app.reply.assert_called_once_with(ctx, article_ref='a1',
        to_ref='@bob', content='Thanks for the review!')


# ── Invite / Accept / Decline ─────────────────────────────────────────────

def test_review_invite_delegates(ctx):
    with mock_cmd(_MOD, '_review') as app:
        call(_cmd_review_invite, ctx, Namespace(article_id='a1', user='@bob'))
    app.invite_reviewer.assert_called_once_with(ctx, article_ref='a1', user_ref='@bob')


def test_review_accept_delegates(ctx):
    with mock_cmd(_MOD, '_review') as app:
        call(_cmd_review_accept, ctx, Namespace(article_id='a1'))
    app.accept.assert_called_once_with(ctx, article_ref='a1')


def test_review_decline_delegates(ctx):
    with mock_cmd(_MOD, '_review') as app:
        call(_cmd_review_decline, ctx, Namespace(article_id='a1'))
    app.decline.assert_called_once_with(ctx, article_ref='a1')


# ── Rate ──────────────────────────────────────────────────────────────────

def test_review_rate_delegates(ctx):
    with mock_cmd(_MOD, '_review') as app:
        call(_cmd_review_rate, ctx,
             Namespace(article_id='a1', reviewer='@bob', helpfulness=4))
    app.rate.assert_called_once_with(ctx, article_ref='a1',
        reviewer_ref='@bob', helpfulness=4)


# ── _edit_reply helper ────────────────────────────────────────────────────

def test_edit_reply_returns_content():
    template = (
        "# Author Reply\n"
        "# Replying to: @bob\n"
        "# Write your reply below. Lines starting with # are ignored.\n"
        "# An empty reply aborts.\n\n"
        "Great points, I've updated the paper.\n"
    )
    with patch(f'{_MOD}._open_editor', return_value=template):
        result = _edit_reply('@bob')
    assert result == 'Great points, I\'ve updated the paper.'


def test_edit_reply_strips_empty_lines():
    template = (
        "# Author Reply\n"
        "# Replying to: @bob\n"
        "# Write your reply below. Lines starting with # are ignored.\n"
        "# An empty reply aborts.\n\n"
        "Response here.\n\n\n"
    )
    with patch(f'{_MOD}._open_editor', return_value=template):
        result = _edit_reply('@bob')
    assert result == 'Response here.'


def test_edit_reply_empty_returns_empty_string():
    template = (
        "# Only comments\n"
        "# No real content\n"
    )
    with patch(f'{_MOD}._open_editor', return_value=template):
        result = _edit_reply('@bob')
    assert result == ''
