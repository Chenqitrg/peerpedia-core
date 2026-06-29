# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Account commands — register, login, recover, whoami, bootstrap, delete, search."""

from __future__ import annotations

from peerpedia_core.cli.decorators import with_context
from peerpedia_core.editor import get_password as _get_password
import peerpedia_core.app.commands.account as _account


# ── Registration ──────────────────────────────────────────────────────────

@with_context
def _cmd_account_register(ctx, args):
    """Register a new local user."""
    password = _get_password(args, confirm=True)
    return _account.register(ctx, name=args.name, password=password)


# ── Login / Recover ───────────────────────────────────────────────────────

@with_context
def _cmd_account_login(ctx, args):
    """Log in as an existing user — verify password, load key into session."""
    password = _get_password(args)
    return _account.login(ctx, name=args.name, password=password)


@with_context
def _cmd_account_recover(ctx, args):
    """Recover a user's Ed25519 key from password + stored salt."""
    password = _get_password(args)
    return _account.recover(ctx, name=getattr(args, "name", None),
        user_id=getattr(args, "user_id", None), password=password)


# ── Identity ──────────────────────────────────────────────────────────────

@with_context
def _cmd_account_whoami(ctx, args):
    """Show current login status."""
    return _account.whoami(ctx)


@with_context
def _cmd_account_bootstrap(ctx, args):
    """Create a minimal user stub on a new device for key recovery."""
    return _account.bootstrap(ctx, from_json=args.from_,
        peer=getattr(args, "peer", None))


# ── Management ────────────────────────────────────────────────────────────

@with_context
def _cmd_account_delete(ctx, args):
    """Soft-delete the current user account."""
    return _account.delete_account(ctx)


@with_context
def _cmd_account_search(ctx, args):
    """Search users by name (case-insensitive)."""
    return _account.search_users(ctx, query=getattr(args, "query", ""))
