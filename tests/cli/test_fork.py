# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Unit tests for fork / merge commands — verify delegation via spec.handler."""

from __future__ import annotations

from argparse import Namespace

from peerpedia_core.cli.cmds.fork import (
    _cmd_fork, _cmd_merge_propose, _cmd_merge_accept, _cmd_merge_withdraw,
)
from tests.cli.conftest import call, mock_spec_handler

_MOD = 'peerpedia_core.cli.cmds.fork'


def test_fork_delegates(ctx):
    with mock_spec_handler(_MOD, 'fork') as h:
        call(_cmd_fork, ctx, Namespace(article_id='abc12345'))
    h.assert_called_once_with(ctx, {'article_id': 'abc12345'})


def test_fork_short_id(ctx):
    with mock_spec_handler(_MOD, 'fork') as h:
        call(_cmd_fork, ctx, Namespace(article_id='abc'))
    h.assert_called_once_with(ctx, {'article_id': 'abc'})


def test_fork_uuid(ctx):
    with mock_spec_handler(_MOD, 'fork') as h:
        call(_cmd_fork, ctx, Namespace(article_id='a1b2c3d4-e5f6-7890-abcd-ef1234567890'))
    h.assert_called_once_with(ctx, {'article_id': 'a1b2c3d4-e5f6-7890-abcd-ef1234567890'})


def test_merge_propose_with_explicit_fork_id(ctx):
    with mock_spec_handler(_MOD, 'merge.propose') as h:
        call(_cmd_merge_propose, ctx, Namespace(fork_id='fork123', target='orig456'))
    h.assert_called_once_with(ctx, {'fork_id': 'fork123', 'target': 'orig456'})


def test_merge_propose_short_ids(ctx):
    with mock_spec_handler(_MOD, 'merge.propose') as h:
        call(_cmd_merge_propose, ctx, Namespace(fork_id='frk', target='org'))
    h.assert_called_once_with(ctx, {'fork_id': 'frk', 'target': 'org'})


def test_merge_propose_full_ids(ctx):
    with mock_spec_handler(_MOD, 'merge.propose') as h:
        call(_cmd_merge_propose, ctx, Namespace(fork_id='a1b2c3d4', target='e5f6a7b8'))
    h.assert_called_once_with(ctx, {'fork_id': 'a1b2c3d4', 'target': 'e5f6a7b8'})


def test_merge_accept_with_explicit_proposal_id(ctx):
    with mock_spec_handler(_MOD, 'merge.accept') as h:
        call(_cmd_merge_accept, ctx, Namespace(proposal_id='prop1', target='orig456'))
    h.assert_called_once_with(ctx, {'proposal_id': 'prop1', 'target': 'orig456'})


def test_merge_accept_short_ids(ctx):
    with mock_spec_handler(_MOD, 'merge.accept') as h:
        call(_cmd_merge_accept, ctx, Namespace(proposal_id='prp', target='org'))
    h.assert_called_once_with(ctx, {'proposal_id': 'prp', 'target': 'org'})


def test_merge_withdraw_delegates(ctx):
    with mock_spec_handler(_MOD, 'merge.withdraw') as h:
        call(_cmd_merge_withdraw, ctx, Namespace(proposal_id='prop1'))
    h.assert_called_once_with(ctx, {'proposal_id': 'prop1'})


def test_merge_withdraw_short_id(ctx):
    with mock_spec_handler(_MOD, 'merge.withdraw') as h:
        call(_cmd_merge_withdraw, ctx, Namespace(proposal_id='prp'))
    h.assert_called_once_with(ctx, {'proposal_id': 'prp'})


def test_merge_withdraw_full_id(ctx):
    with mock_spec_handler(_MOD, 'merge.withdraw') as h:
        call(_cmd_merge_withdraw, ctx, Namespace(proposal_id='a1b2c3d4-e5f6-7890'))
    h.assert_called_once_with(ctx, {'proposal_id': 'a1b2c3d4-e5f6-7890'})


def test_lifecycle_fork_propose_accept(ctx):
    with mock_spec_handler(_MOD, 'fork') as h_fork:
        call(_cmd_fork, ctx, Namespace(article_id='orig'))
    h_fork.assert_called_once_with(ctx, {'article_id': 'orig'})

    with mock_spec_handler(_MOD, 'merge.propose') as h_prop:
        call(_cmd_merge_propose, ctx, Namespace(fork_id='fork1', target='orig'))
    h_prop.assert_called_once_with(ctx, {'fork_id': 'fork1', 'target': 'orig'})

    with mock_spec_handler(_MOD, 'merge.accept') as h_accept:
        call(_cmd_merge_accept, ctx, Namespace(proposal_id='prop1', target='orig'))
    h_accept.assert_called_once_with(ctx, {'proposal_id': 'prop1', 'target': 'orig'})
