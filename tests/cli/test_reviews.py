# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Unit tests for review commands — verify delegation via spec.handler."""

from __future__ import annotations

from argparse import Namespace
from unittest.mock import patch

from peerpedia_core.cli.cmds.reviews import (
    _cmd_review_submit, _cmd_review_list, _cmd_review_reply,
    _cmd_review_invite, _cmd_review_accept, _cmd_review_decline, _cmd_review_rate,
)
from tests.cli.conftest import call, mock_spec_handler

_MOD = 'peerpedia_core.cli.cmds.reviews'


def test_review_submit_delegates(ctx):
    with mock_spec_handler(_MOD, 'review.submit') as h:
        call(_cmd_review_submit, ctx,
             Namespace(article_id='a1', scores='orig=4,rigor=3', comment='Nice paper'))
    h.assert_called_once_with(ctx, {'article_id': 'a1', 'scores': 'orig=4,rigor=3', 'comment': 'Nice paper'})


def test_review_submit_empty_comment(ctx):
    with mock_spec_handler(_MOD, 'review.submit') as h:
        call(_cmd_review_submit, ctx,
             Namespace(article_id='a1', scores='orig=4', comment=None))
    h.assert_called_once_with(ctx, {'article_id': 'a1', 'scores': 'orig=4', 'comment': ''})


def test_review_list_delegates(ctx):
    with mock_spec_handler(_MOD, 'review.list') as h:
        call(_cmd_review_list, ctx, Namespace(article_id='a1'))
    h.assert_called_once_with(ctx, {'article_id': 'a1'})


def test_review_reply_delegates(ctx):
    with mock_spec_handler(_MOD, 'review.reply') as h:
        with patch(f'{_MOD}._edit_reply', return_value='Thanks for the review!'):
            call(_cmd_review_reply, ctx, Namespace(article_id='a1', to='@bob'))
    h.assert_called_once_with(ctx, {'article_id': 'a1', 'to': '@bob', 'content': 'Thanks for the review!'})


def test_review_invite_delegates(ctx):
    with mock_spec_handler(_MOD, 'review.invite') as h:
        call(_cmd_review_invite, ctx, Namespace(article_id='a1', user='@bob'))
    h.assert_called_once_with(ctx, {'article_id': 'a1', 'user': '@bob'})


def test_review_accept_delegates(ctx):
    with mock_spec_handler(_MOD, 'review.accept') as h:
        call(_cmd_review_accept, ctx, Namespace(article_id='a1'))
    h.assert_called_once_with(ctx, {'article_id': 'a1'})


def test_review_decline_delegates(ctx):
    with mock_spec_handler(_MOD, 'review.decline') as h:
        call(_cmd_review_decline, ctx, Namespace(article_id='a1'))
    h.assert_called_once_with(ctx, {'article_id': 'a1'})


def test_review_rate_delegates(ctx):
    with mock_spec_handler(_MOD, 'review.rate') as h:
        call(_cmd_review_rate, ctx, Namespace(article_id='a1', reviewer='@bob', helpfulness=4))
    h.assert_called_once_with(ctx, {'article_id': 'a1', 'reviewer': '@bob', 'helpfulness': 4})
