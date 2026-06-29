# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Unit tests for fork / merge commands."""

from __future__ import annotations

from argparse import Namespace

from peerpedia_core.cli.cmds.fork import (
    _cmd_fork,
    _cmd_merge_propose,
    _cmd_merge_accept,
    _cmd_merge_withdraw,
)
from tests.cli.conftest import call, mock_cmd

_MOD = 'peerpedia_core.cli.cmds.fork'


def test_fork_delegates(ctx):
    with mock_cmd(_MOD, '_fork') as app:
        call(_cmd_fork, ctx, Namespace(article_id='abc12345'))
    app.fork.assert_called_once_with(ctx, article_ref='abc12345')


def test_merge_propose_delegates(ctx):
    with mock_cmd(_MOD, '_fork') as app:
        call(_cmd_merge_propose, ctx, Namespace(fork_id='fork1', target='orig1'))
    app.merge_propose.assert_called_once_with(
        ctx, fork_ref='fork1', target_ref='orig1')


def test_merge_accept_delegates(ctx):
    with mock_cmd(_MOD, '_fork') as app:
        call(_cmd_merge_accept, ctx, Namespace(proposal_id='prop1', target='orig1'))
    app.merge_accept.assert_called_once_with(
        ctx, proposal_ref='prop1', target_ref='orig1')


def test_merge_withdraw_delegates(ctx):
    with mock_cmd(_MOD, '_fork') as app:
        call(_cmd_merge_withdraw, ctx, Namespace(proposal_id='prop1'))
    app.merge_withdraw.assert_called_once_with(ctx, proposal_ref='prop1')
