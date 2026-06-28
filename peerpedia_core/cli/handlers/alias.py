# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Alias commands — nickname users you follow."""

from __future__ import annotations

from peerpedia_core.cli.display import console
from peerpedia_core.cli.helpers import (
    _with_db, _resolve_user, _get_session_user, _ok, _json_out,
)
from peerpedia_core.core import list_aliases, remove_alias, set_alias
from peerpedia_core.types import short_id


@_with_db
def _cmd_alias_set(db, args):
    """Set or update an alias for a user you follow.

    args: user_identifier [positional], alias [positional]
    """
    owner_id = _get_session_user()
    target_id = _resolve_user(db, args.user_identifier)
    set_alias(db, owner_id, target_id, args.alias)
    db.commit()
    _ok(f"Alias [accent]{args.alias}[/] → {short_id(target_id)}")


@_with_db
def _cmd_alias_remove(db, args):
    """Remove an alias.

    args: user_identifier [positional]
    """
    owner_id = _get_session_user()
    target_id = _resolve_user(db, args.user_identifier)
    remove_alias(db, owner_id, target_id)
    db.commit()
    _ok(f"Alias removed for {short_id(target_id)}")


@_with_db
def _cmd_alias_list(db, args):
    """List all aliases you have set.

    args: --json
    """
    aliases = list_aliases(db, _get_session_user())
    if args.json:
        _json_out([{"target": a.target_id, "alias": a.alias} for a in aliases])
    elif not aliases:
        console.print("[muted]No aliases set.[/]")
    else:
        for a in aliases:
            console.print(f"  [accent]{a.alias}[/] → {short_id(a.target_id)}")
