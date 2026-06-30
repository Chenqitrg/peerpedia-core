# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Account commands — register, login, recover, whoami, bootstrap, delete, search."""

from __future__ import annotations

from peerpedia_core.app.result import AppResult
from peerpedia_core.cli.decorators import with_context
from peerpedia_core.cli.display import display_user
from peerpedia_core.cli.info import console
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
    result = _account.whoami(ctx)
    # Render as a user panel instead of raw key-value dump
    d = result.data
    display_user(
        d.get("name", "?"),
        d.get("id", "?"),
        affiliation=d.get("affiliation", ""),
        expertise=d.get("expertise"),
        reputation=d.get("reputation"),
        public_key=d.get("public_key"),
        created_at=str(d.get("created_at", "")) if d.get("created_at") else "",
    )
    return AppResult(code="", data=None, params=result.params, notices=result.notices)


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
    result = _account.search_users(ctx, query=getattr(args, "query", ""))
    items = result.data.get("items", [])
    if not items:
        console.print(f"[muted]No users match '{args.query}'.[/]")
        return AppResult(code="", data=None, params=result.params, notices=result.notices)
    for u in items:
        display_user(
            u["name"],
            u["user_id"],
        )
    return AppResult(code="", data=None, params=result.params, notices=result.notices)
