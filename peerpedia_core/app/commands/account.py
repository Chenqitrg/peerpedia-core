# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

r"""Account commands — register, login, recover, bootstrap, whoami, delete."""

from __future__ import annotations

from peerpedia_core.app.context import AppContext, write_session
from peerpedia_core.app.parsers import parse_bootstrap_json
from peerpedia_core.app.refs import (
    guard_name_available, guard_user_id_available, require_user,
    require_user_by_name, require_user_by_ref,
)
from peerpedia_core.app.result import AppNotice, AppResult
from peerpedia_core.core import (
    create_user, create_user_stub, find_users, get_user_view,
    require_authenticable_user, soft_delete_user, verify_user_password,
)
from peerpedia_core.crypto import derive_key_pair, new_salt
from peerpedia_core.types import short_id


def whoami(ctx: AppContext) -> AppResult:
    """Return current user identity (always includes pubkey if available)."""
    # ── Resolve ──
    user_id = require_user(ctx)
    # ── Execute ──
    view = get_user_view(ctx.db, user_id)
    return AppResult("", data=view)


def register(ctx: AppContext, *, name: str, password: str) -> AppResult:
    """Register a new local user."""
    # ── Guard ──
    guard_name_available(ctx.db, name)
    # ── Execute ──
    salt_hex = new_salt()
    private_key_bytes, pubkey_bytes = derive_key_pair(password, salt_hex)
    pubkey_hex = pubkey_bytes.hex()
    user = create_user(ctx.db, name=name, public_key=pubkey_hex)
    from peerpedia_core.core import update_user_salt
    update_user_salt(ctx.db, user.id, salt_hex)
    ctx.db.commit()
    # ── Session ──
    write_session(user.id, user.name, private_key_bytes.hex())
    return AppResult("REGISTERED",
        data={"id": user.id, "name": user.name, "pubkey": pubkey_hex},
        params={"name": user.name, "id_short": short_id(user.id)})


def login(ctx: AppContext, *, name: str, password: str) -> AppResult:
    """Log in as an existing user."""
    # ── Resolve ──
    user = require_user_by_name(ctx.db, name)
    # ── Guard ──
    require_authenticable_user(user)
    # ── Verify ──
    verify_user_password(ctx.db, user, password)
    # ── Session ──
    return _write_login_session(user, password)


def recover(ctx: AppContext, *, name: str | None = None, user_id: str | None = None,
            password: str) -> AppResult:
    """Recover a user's Ed25519 key from password + stored salt."""
    # ── Resolve ──
    user = require_user_by_ref(ctx.db, user_id) if user_id else \
           require_user_by_name(ctx.db, name)
    # ── Guard ──
    require_authenticable_user(user)
    # ── Verify ──
    verify_user_password(ctx.db, user, password)
    # ── Session ──
    private_key_bytes, _ = derive_key_pair(password, user.salt)
    write_session(user.id, user.name, private_key_bytes.hex())
    return AppResult("RECOVERED",
        data={"id": user.id, "name": user.name},
        params={"name": user.name, "id_short": short_id(user.id)})


def delete_account(ctx: AppContext) -> AppResult:
    """Soft-delete the current user account."""
    # ── Resolve ──
    user = require_user_by_ref(ctx.db, require_user(ctx))
    # ── Execute ──
    soft_delete_user(ctx.db, user.id)
    ctx.db.commit()
    return AppResult("ACCOUNT_DELETED", params={"name": user.name})


def bootstrap(ctx: AppContext, *, from_json: str, peer: str | None = None) -> AppResult:
    """Create a minimal user stub on a new device for key recovery."""
    # ── Parse + Guard ──
    data = parse_bootstrap_json(from_json)
    user_id, name = data["user_id"], data["name"]
    guard_user_id_available(ctx.db, user_id)
    # ── Execute ──
    create_user_stub(ctx.db, user_id=user_id, name=name,
                     public_key=data["public_key"], salt=data["salt"])
    ctx.db.commit()
    # ── Peer ──
    notices: list[AppNotice] = []
    if peer:
        from peerpedia_core.core import merge_peers
        merge_peers(ctx.transport, peer)
        notices.append(AppNotice("W_AUTO_SYNCING", params={"count": 1}))
    return AppResult("BOOTSTRAPPED",
        data={"id": user_id, "name": name},
        params={"name": name, "id_short": short_id(user_id)},
        notices=notices)


def search_users(ctx: AppContext, *, query: str = "") -> AppResult:
    """Search users by name (case-insensitive)."""
    # ── Guard ──
    if not query:
        return AppResult("", data={"items": []})
    # ── Execute ──
    results = find_users(ctx.db, query)
    return AppResult("", data={"items": [{"id": u.id, "name": u.name} for u in results]})


# ── Internal ─────────────────────────────────────────────────────────────


def _write_login_session(user, password: str) -> AppResult:
    """Derive key, write session, return LOGGED_IN."""
    private_key_bytes, _ = derive_key_pair(password, user.salt)
    write_session(user.id, user.name, private_key_bytes.hex())
    return AppResult("LOGGED_IN",
        data={"id": user.id, "name": user.name},
        params={"name": user.name, "id_short": short_id(user.id)})


