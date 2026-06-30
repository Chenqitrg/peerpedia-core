# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Unit tests for notification commands — verify delegation via spec.handler."""

from __future__ import annotations

from argparse import Namespace

from peerpedia_core.cli.cmds.notifications import (
    _cmd_notifications, _cmd_notification_read,
)
from tests.cli.conftest import call, mock_spec_handler

_MOD = 'peerpedia_core.cli.cmds.notifications'


def test_notifications_unread_only(ctx):
    with mock_spec_handler(_MOD, 'notifications') as h:
        call(_cmd_notifications, ctx, Namespace(all=False))
    h.assert_called_once_with(ctx, {'all': False})


def test_notifications_all(ctx):
    with mock_spec_handler(_MOD, 'notifications') as h:
        call(_cmd_notifications, ctx, Namespace(all=True))
    h.assert_called_once_with(ctx, {'all': True})


def test_notification_read_delegates(ctx):
    with mock_spec_handler(_MOD, 'notifications.read') as h:
        call(_cmd_notification_read, ctx, Namespace(notification_id='n1'))
    h.assert_called_once_with(ctx, {'notification_id': 'n1'})
