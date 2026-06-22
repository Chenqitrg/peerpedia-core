# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Social commands — fork, merge, bookmark."""

from __future__ import annotations

from peerpedia_core.cli.helpers import (
    _with_db, _resolve_user, _get_session_user, _resolve_and_display_article, _ok, _die, _json_out,
)
from peerpedia_core.cli.display import console
from peerpedia_core.cli.sync_utils import _try_sync
from peerpedia_core.commands import (
    fork_article, create_merge_proposal, accept_merge,
    add_bookmark, remove_bookmark,
    follow_user, unfollow_user,
)


@_with_db
def _cmd_fork(db, args):
    """Fork a published article into a new draft copy.

    args: article_id [positional], --json
    """
    result = fork_article(db, args.article_id, _get_session_user())
    db.commit()
    _try_sync(db)
    if args.json:
        _json_out(result)
    else:
        _ok(f"Forked → [accent]{result['id'][:8]}[/]")


@_with_db
def _cmd_merge_propose(db, args):
    """Propose merging a fork back into the original article.

    args: fork_id [positional], --target, --json
    """
    mp = create_merge_proposal(db, args.fork_id, args.target, _get_session_user())
    db.commit()
    if args.json:
        _json_out({"id": mp.id, "status": mp.status})
    else:
        _ok(f"Merge proposed [accent]{mp.id[:8]}[/] → target {args.target[:8]}")


@_with_db
def _cmd_merge_accept(db, args):
    """Accept a merge proposal. May report conflicts.

    args: proposal_id [positional], --target, --json
    """
    result = accept_merge(db, args.target, args.proposal_id, _get_session_user())
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

    args: article_id [positional], --json
    """
    add_bookmark(db, _get_session_user(), args.article_id)
    db.commit()
    _ok(f"Bookmarked [accent]{args.article_id[:8]}[/]")


@_with_db
def _cmd_bookmark_remove(db, args):
    """Remove a bookmark. Idempotent.

    args: article_id [positional], --json
    """
    remove_bookmark(db, _get_session_user(), args.article_id)
    db.commit()
    if args.json:
        _json_out({"removed": True})
    else:
        _ok(f"Removed bookmark for [accent]{args.article_id[:8]}[/]")


@_with_db
def _cmd_follow_user(db, args):
    """Follow a user.

    args: user_identifier [positional], --json
    """
    follower_id = _get_session_user()
    followed_id = _resolve_user(db, args.user_identifier)
    follow_user(db, follower_id, followed_id)
    db.commit()
    if args.json:
        _json_out({"following": True})
    else:
        _ok(f"Now following [accent]{followed_id[:8]}[/]")


@_with_db
def _cmd_unfollow_user(db, args):
    """Unfollow a user. Idempotent.

    args: user_identifier [positional], --json
    """
    follower_id = _get_session_user()
    followed_id = _resolve_user(db, args.user_identifier)
    unfollow_user(db, follower_id, followed_id)
    db.commit()
    if args.json:
        _json_out({"following": False})
    else:
        _ok(f"Stopped following [accent]{followed_id[:8]}[/]")
