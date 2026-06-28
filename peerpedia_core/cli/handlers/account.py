# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Account commands — search, delete, whoami."""

from __future__ import annotations

from peerpedia_core.cli.display import display_user as _render
from peerpedia_core.cli.handlers.login import _check_account_locked, _verify_password
from peerpedia_core.cli.helpers import (
    _with_db, _read_session, _out, _get_password, _json_out,
)
from peerpedia_core.config.paths import SESSION_FILE
from peerpedia_core.core import get_user, search_users, soft_delete_user
from peerpedia_core.types import short_id


def _require_session():
    s = _read_session()
    if not s:
        _out(None, "UNAUTHORIZED")
    return s


@_with_db
def _cmd_account_search(db, args):
    """Search users by name.  args: query [positional], --json"""
    users = search_users(db, args.query, limit=20)
    if args.json:
        _json_out([{"id": u.id, "name": u.name} for u in users])
        return
    if not users:
        _out(args, "EMPTY_SEARCH", query=args.query)
        return
    for u in users:
        _render(name=u.name, affiliation=u.affiliation or "",
                expertise=u.expertise or [], reputation=u.reputation or {},
                user_id=u.id)


@_with_db
def _cmd_account_delete(db, args):
    """Delete your account after password confirmation.  args: --json"""
    s = _require_session()
    user = get_user(db, s["user_id"])
    if user is None:
        _out(args, "NOT_FOUND", what="User")

    _check_account_locked(user)
    _verify_password(db, user, _get_password(args))

    soft_delete_user(db, user.id)
    db.commit()

    try:
        SESSION_FILE.unlink(missing_ok=True)
    except OSError:
        pass

    _out(args, "ACCOUNT_DELETED", {"user_id": user.id}, name=user.name)


@_with_db
def _cmd_whoami(db, args):
    """Show current user identity.  args: --json, --verbose"""
    s = _read_session()
    if not s:
        _out(args, "NOT_LOGGED_IN", {"status": "not_logged_in"})
        return

    uid, name = s["user_id"], s["name"]
    if not args.verbose:
        _out(args, "", {"user_id": uid, "name": name})
        return

    user = get_user(db, uid)
    if user is None:
        _out(args, "USER_NOT_FOUND_LOCAL", user_id=short_id(uid))
    _out(args, "", {"user_id": uid, "name": name,
                    "public_key": user.public_key or "not set",
                    "salt": user.salt or "not set"})
