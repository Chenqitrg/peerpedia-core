# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Social commands — fork, merge, bookmark."""

from __future__ import annotations

from peerpedia_core.cli.helpers import _with_db, _resolve_user, _ok, _die, _json_out
from peerpedia_core.cli.display import _print_table, console
from peerpedia_core.cli.sync_utils import _try_sync
from peerpedia_core.commands import (
    fork_article, create_merge_proposal, accept_merge,
    add_bookmark, get_bookmarks_for_user,
)


@_with_db
def _cmd_fork(db, args):
    """Fork a published article into a new draft copy.

    args: article_id [positional], --user, --json
    """
    result = fork_article(db, args.article_id, _resolve_user(db, args.user))
    db.commit()
    _try_sync(db)
    if args.json:
        _json_out(result)
    else:
        _ok(f"Forked → [accent]{result['id'][:8]}[/]")


@_with_db
def _cmd_merge_propose(db, args):
    """Propose merging a fork back into the original article.

    args: fork_id [positional], --target, --user, --json
    """
    mp = create_merge_proposal(db, args.fork_id, args.target, _resolve_user(db, args.user))
    db.commit()
    if args.json:
        _json_out({"id": mp.id, "status": mp.status})
    else:
        _ok(f"Merge proposed [accent]{mp.id[:8]}[/] → target {args.target[:8]}")


@_with_db
def _cmd_merge_accept(db, args):
    """Accept a merge proposal. May report conflicts.

    args: proposal_id [positional], --target, --user, --json
    """
    result = accept_merge(db, args.target, args.proposal_id, _resolve_user(db, args.user))
    db.commit()
    _try_sync(db)
    if args.json:
        _json_out(result)
    elif result.get("status") == "conflict":
        console.print(f"[warning]⚠ {result['message']}[/]")
    else:
        _ok(f"Merge accepted — [accent]{result['id'][:8]}[/]")


@_with_db
def _cmd_bookmark_add(db, args):
    """Bookmark an article for the given user.

    args: article_id [positional], --user, --json
    """
    add_bookmark(db, _resolve_user(db, args.user), args.article_id)
    db.commit()
    _ok(f"Bookmarked [accent]{args.article_id[:8]}[/]")


@_with_db
def _cmd_bookmark_list(db, args):
    """List all articles bookmarked by the given user.

    args: --user, --json
    """
    articles = get_bookmarks_for_user(db, _resolve_user(db, args.user))
    if args.json:
        _json_out([{"id": a.id, "title": a.title} for a in articles])
        return
    if not articles:
        console.print("[muted]No bookmarks.[/]")
        return
    rows = [[a.id[:8], a.title] for a in articles]
    _print_table(["Article ID"], rows, title=f"{len(rows)} bookmark(s)")
