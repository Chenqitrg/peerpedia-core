# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Unit tests for maintainer commands."""

from __future__ import annotations

from argparse import Namespace

from peerpedia_core.cli.cmds.maintainers import (
    _cmd_maintainer_add,
    _cmd_maintainer_remove,
    _cmd_maintainer_list,
    _cmd_maintainer_consent,
    _cmd_maintainer_revoke,
)
from tests.cli.conftest import call, mock_cmd

_MOD = 'peerpedia_core.cli.cmds.maintainers'


def test_maintainer_add_delegates(ctx):
    with mock_cmd(_MOD, '_maint') as app:
        call(_cmd_maintainer_add, ctx, Namespace(article_id='a1', target_user='@bob'))
    app.add.assert_called_once_with(ctx, article_ref='a1', target_ref='@bob')


def test_maintainer_remove_delegates(ctx):
    with mock_cmd(_MOD, '_maint') as app:
        call(_cmd_maintainer_remove, ctx, Namespace(article_id='a1', target_user='@bob'))
    app.remove.assert_called_once_with(ctx, article_ref='a1', target_ref='@bob')


def test_maintainer_list_delegates(ctx):
    with mock_cmd(_MOD, '_maint') as app:
        call(_cmd_maintainer_list, ctx, Namespace(article_id='a1'))
    app.list_article_maintainers.assert_called_once_with(ctx, article_ref='a1')


def test_maintainer_consent_delegates(ctx):
    with mock_cmd(_MOD, '_maint') as app:
        call(_cmd_maintainer_consent, ctx, Namespace(article_id='a1'))
    app.consent.assert_called_once_with(ctx, article_ref='a1')


def test_maintainer_revoke_delegates(ctx):
    with mock_cmd(_MOD, '_maint') as app:
        call(_cmd_maintainer_revoke, ctx, Namespace(article_id='a1'))
    app.revoke.assert_called_once_with(ctx, article_ref='a1')
