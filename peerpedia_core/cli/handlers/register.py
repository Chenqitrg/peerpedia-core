# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Register a new local user."""

from __future__ import annotations

from peerpedia_core.cli.decorators import with_context
from peerpedia_core.editor import get_password as _get_password
import peerpedia_core.app.commands.account as _account


@with_context
def _cmd_register(ctx, args):
    """Register a new local user."""
    password = _get_password(args, confirm=True)
    return _account.register(ctx, name=args.name, password=password)
