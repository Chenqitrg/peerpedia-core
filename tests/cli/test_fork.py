# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Unit tests for fork / merge commands.

Merge has historically been brittle — these tests verify parameter
mapping for every edge case (missing args, short IDs, full lifecycle).
"""

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


# ── Fork ──────────────────────────────────────────────────────────────────

def test_fork_delegates(ctx):
    with mock_cmd(_MOD, '_fork') as app:
        call(_cmd_fork, ctx, Namespace(article_id='abc12345'))
    app.fork.assert_called_once_with(ctx, article_ref='abc12345')


def test_fork_short_id(ctx):
    """Short ID prefixes pass through — resolution is the app layer's job."""
    with mock_cmd(_MOD, '_fork') as app:
        call(_cmd_fork, ctx, Namespace(article_id='abc'))
    app.fork.assert_called_once_with(ctx, article_ref='abc')


def test_fork_uuid(ctx):
    with mock_cmd(_MOD, '_fork') as app:
        call(_cmd_fork, ctx, Namespace(
            article_id='00000000-0000-0000-0000-000000000001'))
    app.fork.assert_called_once_with(
        ctx, article_ref='00000000-0000-0000-0000-000000000001')


# ── Merge propose ─────────────────────────────────────────────────────────

def test_merge_propose_delegates(ctx):
    with mock_cmd(_MOD, '_fork') as app:
        call(_cmd_merge_propose, ctx, Namespace(fork_id='fork1', target='orig1'))
    app.merge_propose.assert_called_once_with(
        ctx, fork_ref='fork1', target_ref='orig1')


def test_merge_propose_target_is_positional(ctx):
    """--target is required by argparse — the handler receives the raw value."""
    with mock_cmd(_MOD, '_fork') as app:
        call(_cmd_merge_propose, ctx, Namespace(fork_id='fork-abc', target='orig-def'))
    app.merge_propose.assert_called_once_with(
        ctx, fork_ref='fork-abc', target_ref='orig-def')


def test_merge_propose_short_ids(ctx):
    with mock_cmd(_MOD, '_fork') as app:
        call(_cmd_merge_propose, ctx, Namespace(fork_id='f12', target='a34'))
    app.merge_propose.assert_called_once_with(
        ctx, fork_ref='f12', target_ref='a34')


# ── Merge accept ──────────────────────────────────────────────────────────

def test_merge_accept_delegates(ctx):
    with mock_cmd(_MOD, '_fork') as app:
        call(_cmd_merge_accept, ctx, Namespace(proposal_id='prop1', target='orig1'))
    app.merge_accept.assert_called_once_with(
        ctx, proposal_ref='prop1', target_ref='orig1')


def test_merge_accept_proposal_and_target(ctx):
    with mock_cmd(_MOD, '_fork') as app:
        call(_cmd_merge_accept, ctx, Namespace(
            proposal_id='prop-xyz', target='article-abc'))
    app.merge_accept.assert_called_once_with(
        ctx, proposal_ref='prop-xyz', target_ref='article-abc')


# ── Merge withdraw ────────────────────────────────────────────────────────

def test_merge_withdraw_delegates(ctx):
    with mock_cmd(_MOD, '_fork') as app:
        call(_cmd_merge_withdraw, ctx, Namespace(proposal_id='prop1'))
    app.merge_withdraw.assert_called_once_with(ctx, proposal_ref='prop1')


def test_merge_withdraw_short_proposal_id(ctx):
    with mock_cmd(_MOD, '_fork') as app:
        call(_cmd_merge_withdraw, ctx, Namespace(proposal_id='p1'))
    app.merge_withdraw.assert_called_once_with(ctx, proposal_ref='p1')


# ── Full lifecycle: fork → propose → accept ──────────────────────────────

def test_fork_to_merge_lifecycle(ctx):
    """Simulate the full fork → propose → accept pipeline.

    Each step is a separate handler call — verify the refs thread through.
    """
    article_id = 'abc12345'
    fork_id = 'fork-1'
    proposal_id = 'prop-1'

    with mock_cmd(_MOD, '_fork') as app:
        # Step 1: fork
        call(_cmd_fork, ctx, Namespace(article_id=article_id))
        app.fork.assert_called_once_with(ctx, article_ref=article_id)

        # Step 2: propose merge back
        call(_cmd_merge_propose, ctx, Namespace(
            fork_id=fork_id, target=article_id))
        app.merge_propose.assert_called_with(
            ctx, fork_ref=fork_id, target_ref=article_id)

        # Step 3: original author accepts
        call(_cmd_merge_accept, ctx, Namespace(
            proposal_id=proposal_id, target=article_id))
        app.merge_accept.assert_called_with(
            ctx, proposal_ref=proposal_id, target_ref=article_id)


def test_merge_withdraw_after_propose(ctx):
    """Propose then withdraw — verify the proposal ref passes through."""
    with mock_cmd(_MOD, '_fork') as app:
        call(_cmd_merge_propose, ctx, Namespace(fork_id='f1', target='orig'))
        call(_cmd_merge_withdraw, ctx, Namespace(proposal_id='prop-1'))
    app.merge_propose.assert_called_once()
    app.merge_withdraw.assert_called_once()
