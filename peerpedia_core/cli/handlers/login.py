# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Login and recover — verify password, derive Ed25519 key, write session."""

from __future__ import annotations

import logging
import os as _os

from peerpedia_core.cli.bundle_utils import _TRANSPORT
from peerpedia_core.cli.helpers import (
    _with_db, _write_session, _out, _log, _get_password,
    DEFAULT_ARTICLES_DIR,
)
from peerpedia_core.core import (
    create_user_stub, get_user, get_user_by_name,
    increment_failed_login, reset_failed_login,
)
from peerpedia_core.core.sync_article import sync_article
from peerpedia_core.crypto import derive_key_pair
from peerpedia_core.storage.peers import get_known_peers
from peerpedia_core.types import short_id

_log = logging.getLogger(__name__)


def _auto_sync_after_auth(db, user_id: str) -> None:
    """Best-effort article sync with all known peers after login."""
    peers = get_known_peers()
    if not peers:
        _out(None, "W_NO_KNOWN_PEERS")
        return

    _out(None, "W_AUTO_SYNCING", count=len(peers))
    for server in peers:
        if not _TRANSPORT.is_online(server):
            continue
        try:
            for article_dir in DEFAULT_ARTICLES_DIR.iterdir():
                if not (article_dir / ".git").is_dir():
                    continue
                try:
                    sync_article(db, _TRANSPORT, server, article_dir.name)
                    db.commit()
                except Exception as e:
                    _log("L_AUTO_SYNC_ARTICLE", level="warning",
                         article=article_dir.name, server=server, error=e)
        except Exception as e:
            _log("L_AUTO_SYNC_SERVER", level="warning", server=server, error=e)


def _resolve_user_for_auth(db, name: str, user_id: str | None, peer: str | None):
    """Resolve *name* to a single user — disambiguate, bootstrap, or die."""
    user = get_user_by_name(db, name)

    if len(user) > 1 and user_id:
        resolved = get_user(db, user_id)
        if resolved and resolved in user:
            user = [resolved]
        else:
            _out(None, "USER_ID_MISMATCH", name=name, user_id=user_id[:50])

    if len(user) == 0:
        if peer and user_id:
            data = _TRANSPORT.fetch_user(peer, user_id)
            if data:
                create_user_stub(db, user_id=data["id"], name=data["name"],
                                 public_key=data["public_key"], salt=data["salt"])
                db.commit()
                u = get_user(db, data["id"])
                if u is None:
                    _out(None, "BOOTSTRAP_FAILED", user_id=data["id"], peer=peer)
                user = [u]
            else:
                _out(None, "USER_NOT_FOUND_PEER", name=name, peer=peer)
        else:
            _out(None, "USER_NOT_FOUND", name=name)

    if len(user) > 1:
        _out(None, "AMBIGUOUS_NAME", name=name,
             ids=", ".join(short_id(u.id) for u in user))
    return user[0]


def _check_account_locked(user) -> None:
    """Die if *user* has an active lockout."""
    if user.salt is None:
        _out(None, "UNSUPPORTED_KEY", name=user.name)
    if user.locked_until is not None:
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        if user.locked_until > now:
            remaining = int((user.locked_until - now).total_seconds())
            _out(None, "ACCOUNT_LOCKED", minutes=max(1, remaining // 60))


def _verify_password(db, user, password: str) -> None:
    """Raise if password does not match stored pubkey."""
    _, pubkey_bytes = derive_key_pair(password, user.salt)
    if pubkey_bytes.hex() != user.public_key:
        increment_failed_login(db, user.id)
        _out(None, "AUTH_FAILED")
    reset_failed_login(db, user.id)


def _verify_password_and_login(db, user, password: str, args, action: str = "login"):
    """Verify password, write session, display result."""
    _verify_password(db, user, password)
    private_key_bytes, _ = derive_key_pair(password, user.salt)
    _write_session(user.id, user.name, private_key_bytes.hex())
    code = "LOGGED_IN" if action == "login" else "RECOVERED"
    _out(args, code, {"id": user.id, "name": user.name},
         name=user.name, id_short=short_id(user.id))


def _resolve_user_by_name_or_id(db, name, user_id):
    """Look up a single user by --user-id (preferred) or --name."""
    if user_id:
        user = get_user(db, user_id)
        if user is None:
            _out(None, "USER_NOT_FOUND_LOCAL", user_id=short_id(user_id))
        if name:
            _log("L_AMBIGUOUS_INPUT", level="warning")
        return user
    elif name:
        user = get_user_by_name(db, name)
        if len(user) == 0:
            _out(None, "USER_NOT_FOUND_LOCAL", user_id=name)
        if len(user) > 1:
            _out(None, "AMBIGUOUS_NAME", name=name,
                 ids=", ".join(u.id for u in user))
        return user[0]
    else:
        _out(None, "AMBIGUOUS_ARGS")


@_with_db
def _cmd_login(db, args):
    """Log in as an existing user — verify password, load key into session.

    With --peer and --user-id, bootstraps a new device from a peer first.
    args: --name, --password, --json, --peer, --user-id
    """
    user_id = getattr(args, "user_id", None)
    peer = getattr(args, "peer", None) or _os.environ.get("PEERPEDIA_SERVER")
    user = _resolve_user_for_auth(db, args.name, user_id, peer)
    _check_account_locked(user)
    password = _get_password(args)
    _verify_password_and_login(db, user, password, args, action="login")
    _auto_sync_after_auth(db, user.id)


@_with_db
def _cmd_recover(db, args):
    """Recover a user's Ed25519 key from password + stored salt.

    Re-derives the key pair deterministically (scrypt + Ed25519).
    args: --name, --user-id, --json
    """
    user = _resolve_user_by_name_or_id(db, args.name, args.user_id)
    _check_account_locked(user)
    password = _get_password(args)
    _verify_password_and_login(db, user, password, args, action="recover")
