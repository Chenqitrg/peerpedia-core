# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Unit tests for maintainer commands — verify delegation via spec.handler."""

from __future__ import annotations

from argparse import Namespace

from peerpedia_core.cli.cmds.maintainers import (
    _cmd_maintainer_add, _cmd_maintainer_remove, _cmd_maintainer_list,
    _cmd_maintainer_consent, _cmd_maintainer_revoke,
)
from tests.cli.conftest import call, mock_spec_handler

_MOD = 'peerpedia_core.cli.cmds.maintainers'


def test_add_delegates(ctx):
    with mock_spec_handler(_MOD, 'maintainer.add') as h:
        call(_cmd_maintainer_add, ctx, Namespace(article_id='art1', target_user='usr1'))
    h.assert_called_once_with(ctx, {'article_id': 'art1', 'target_user': 'usr1'})


def test_remove_delegates(ctx):
    with mock_spec_handler(_MOD, 'maintainer.remove') as h:
        call(_cmd_maintainer_remove, ctx, Namespace(article_id='art2', target_user='usr2'))
    h.assert_called_once_with(ctx, {'article_id': 'art2', 'target_user': 'usr2'})


def test_list_delegates(ctx):
    with mock_spec_handler(_MOD, 'maintainer.list') as h:
        call(_cmd_maintainer_list, ctx, Namespace(article_id='art3'))
    h.assert_called_once_with(ctx, {'article_id': 'art3'})


def test_consent_delegates(ctx):
    with mock_spec_handler(_MOD, 'maintainer.consent') as h:
        call(_cmd_maintainer_consent, ctx, Namespace(article_id='art4'))
    h.assert_called_once_with(ctx, {'article_id': 'art4'})


def test_revoke_delegates(ctx):
    with mock_spec_handler(_MOD, 'maintainer.revoke') as h:
        call(_cmd_maintainer_revoke, ctx, Namespace(article_id='art5'))
    h.assert_called_once_with(ctx, {'article_id': 'art5'})
