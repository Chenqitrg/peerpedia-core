# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Maintainer commands — manage who controls an article."""

from __future__ import annotations

from peerpedia_core.cli.helpers import _with_db, _resolve_user, _ok, _json_out
from peerpedia_core.cli.display import _print_table, console
from peerpedia_core.commands import (
    add_maintainer_to_article,
    list_maintainers,
    remove_maintainer_from_article,
)


@_with_db
def _cmd_maintainer_add(db, args):
    """Add a maintainer to an article.

    args: article_id [positional], --target-user, --user, --json
    """
    caller_id = _resolve_user(db, args.user)
    result = add_maintainer_to_article(db, args.article_id, args.target_user, caller_id)
    db.commit()
    if args.json:
        _json_out(result)
    else:
        _ok(f"Maintainer [accent]{args.target_user[:8]}[/] added to article [accent]{args.article_id[:8]}[/]")


@_with_db
def _cmd_maintainer_remove(db, args):
    """Remove a maintainer from an article.

    args: article_id [positional], --target-user, --user, --json
    """
    caller_id = _resolve_user(db, args.user)
    result = remove_maintainer_from_article(db, args.article_id, args.target_user, caller_id)
    db.commit()
    if args.json:
        _json_out(result)
    else:
        _ok(f"Maintainer [accent]{args.target_user[:8]}[/] removed from article [accent]{args.article_id[:8]}[/]")


@_with_db
def _cmd_maintainer_list(db, args):
    """List all maintainers of an article.

    args: article_id [positional], --json
    """
    ids = list_maintainers(db, args.article_id)
    if args.json:
        _json_out({"article_id": args.article_id, "maintainers": ids})
        return
    if not ids:
        console.print("[muted]No maintainers.[/]")
        return
    rows = [[uid[:8]] for uid in ids]
    _print_table(["Maintainer ID"], rows, title=f"{len(rows)} maintainer(s)")
