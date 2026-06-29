# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Login and recover — verify password, derive Ed25519 key, write session."""

from __future__ import annotations

from peerpedia_core.cli.decorators import with_context
from peerpedia_core.editor import get_password as _get_password
import peerpedia_core.app.commands.account as _account


@with_context
def _cmd_login(ctx, args):
    """Log in as an existing user — verify password, load key into session."""
    password = _get_password(args)
    return _account.login(ctx, name=args.name, password=password)


@with_context
def _cmd_recover(ctx, args):
    """Recover a user's Ed25519 key from password + stored salt."""
    password = _get_password(args)
    return _account.recover(ctx, name=getattr(args, "name", None),
        user_id=getattr(args, "user_id", None), password=password)
