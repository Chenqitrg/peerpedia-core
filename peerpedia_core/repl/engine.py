# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""REPL execution engine — command dispatch and result rendering.

Independent of ``cli/`` dispatch — builds its own ``AppContext`` from
the REPL's persistent DB session and calls ``app/commands/`` directly.
No argparse, no ``@with_context``, no ``cli/cmds/``.
"""

from __future__ import annotations

import logging
import shlex

from peerpedia_core.app.context import AppContext, build_context
from peerpedia_core.app.result import AppResult
from peerpedia_core.cli.display import (
    display_article_meta, display_diff, display_empty_article_list,
    display_full_content, display_user, _print_table,
)
from peerpedia_core.cli.info import console
from peerpedia_core.exceptions import PeerpediaError
from peerpedia_core.messages import lookup as _lookup

import peerpedia_core.app.commands.account as _account
import peerpedia_core.app.commands.article as _article
import peerpedia_core.app.commands.bundle as _bundle
import peerpedia_core.app.commands.fork as _fork
import peerpedia_core.app.commands.maintainer as _maintainer
import peerpedia_core.app.commands.notification as _notify
import peerpedia_core.app.commands.review as _review
import peerpedia_core.app.commands.social as _social
import peerpedia_core.app.commands.sync as _sync

_log = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# Command table — maps (group, action) → handler
# ═══════════════════════════════════════════════════════════════════════════════

def _cmd_register(ctx: AppContext, args: dict) -> AppResult:
    from peerpedia_core.editor import get_password as _get_password
    from argparse import Namespace
    ns = Namespace(name=args["name"], password=None, json=False, rich=True)
    password = _get_password(ns, confirm=True)
    return _account.register(ctx, name=args["name"], password=password)

def _cmd_login(ctx: AppContext, args: dict) -> AppResult:
    from peerpedia_core.editor import get_password as _get_password
    from argparse import Namespace
    ns = Namespace(name=args["name"], password=None, peer=args.get("peer"), user_id=args.get("user_id"), json=False, rich=True)
    password = _get_password(ns, confirm=False)
    return _account.login(ctx, name=args["name"], password=password, peer=args.get("peer"), user_id=args.get("user_id"))

def _cmd_account_search(ctx: AppContext, args: dict) -> AppResult:
    return _account.search_users(ctx, query=args.get("query", ""))

def _cmd_whoami(ctx: AppContext, args: dict) -> AppResult:
    return _account.whoami(ctx)

def _cmd_article_create(ctx: AppContext, args: dict) -> AppResult:
    return _article.create(ctx, title=args["title"],
        format=args.get("format", "markdown"),
        content=args.get("content", ""),
        publish=args.get("publish", False),
        scores_str=args.get("scores"),
    )

def _cmd_article_show(ctx: AppContext, args: dict) -> AppResult:
    return _article.show(ctx, article_ref=args["id"], show=args.get("show", "meta"))

def _cmd_article_list(ctx: AppContext, args: dict) -> AppResult:
    return _article.list_articles(ctx,
        search_query=args.get("search"),
        status_arg=args.get("status"),
        mine=args.get("mine", False),
        feed=args.get("feed", False),
        bookmarked=args.get("bookmarked", False),
        user_ref=args.get("user"),
        server=args.get("server"),
        limit=args.get("limit", 20),
    )

def _cmd_article_edit(ctx: AppContext, args: dict) -> AppResult:
    return _article.edit(ctx, article_ref=args["id"],
        content=args.get("content"),
        title=args.get("title"),
        message=args.get("message", ""),
    )

def _cmd_article_publish(ctx: AppContext, args: dict) -> AppResult:
    return _article.publish(ctx, article_ref=args["id"], scores_str=args["scores"])

def _cmd_article_delete(ctx: AppContext, args: dict) -> AppResult:
    return _article.delete(ctx, article_ref=args["id"])

def _cmd_article_scan(ctx: AppContext, args: dict) -> AppResult:
    return _article.scan(ctx)

def _cmd_article_diff(ctx: AppContext, args: dict) -> AppResult:
    return _article.diff(ctx, article_ref=args["id"],
        hash1=args.get("hash1"), hash2=args.get("hash2"))

def _cmd_follow(ctx: AppContext, args: dict) -> AppResult:
    return _social.follow(ctx, target_ref=args["user_identifier"])

def _cmd_unfollow(ctx: AppContext, args: dict) -> AppResult:
    return _social.unfollow(ctx, target_ref=args["user_identifier"])

def _cmd_following(ctx: AppContext, args: dict) -> AppResult:
    return _social.list_following(ctx, user_ref=args["user"])

def _cmd_followers(ctx: AppContext, args: dict) -> AppResult:
    return _social.list_followers(ctx, user_ref=args["user"])

def _cmd_school(ctx: AppContext, args: dict) -> AppResult:
    return _social.school(ctx, limit=int(args.get("limit", 20)),
        local=args.get("local", False), server=args.get("server", ""))

def _cmd_bookmark_add(ctx: AppContext, args: dict) -> AppResult:
    return _social.bookmark(ctx, article_ref=args["article_id"])

def _cmd_bookmark_remove(ctx: AppContext, args: dict) -> AppResult:
    return _social.unbookmark(ctx, article_ref=args["article_id"])

def _cmd_review_submit(ctx: AppContext, args: dict) -> AppResult:
    return _review.submit(ctx, article_ref=args["article_id"],
        scores_str=args["scores"], comment=args.get("comment", ""))

def _cmd_review_list(ctx: AppContext, args: dict) -> AppResult:
    return _review.list_reviews(ctx, article_ref=args["article_id"])

def _cmd_review_reply(ctx: AppContext, args: dict) -> AppResult:
    return _review.reply(ctx, article_ref=args["article_id"],
        to_ref=args["to"], content=args.get("content", ""))

def _cmd_review_invite(ctx: AppContext, args: dict) -> AppResult:
    return _review.invite_reviewer(ctx, article_ref=args["article_id"], user_ref=args["user"])

def _cmd_review_accept(ctx: AppContext, args: dict) -> AppResult:
    return _review.accept(ctx, article_ref=args["article_id"])

def _cmd_review_decline(ctx: AppContext, args: dict) -> AppResult:
    return _review.decline(ctx, article_ref=args["article_id"])

def _cmd_review_rate(ctx: AppContext, args: dict) -> AppResult:
    return _review.rate(ctx, article_ref=args["article_id"],
        reviewer_ref=args["reviewer"], helpfulness=int(args["helpfulness"]))

def _cmd_fork(ctx: AppContext, args: dict) -> AppResult:
    return _fork.fork(ctx, article_ref=args["article_id"])

def _cmd_merge_propose(ctx: AppContext, args: dict) -> AppResult:
    return _fork.merge_propose(ctx, fork_ref=args.get("fork_id"), target_ref=args["target"])

def _cmd_merge_accept(ctx: AppContext, args: dict) -> AppResult:
    return _fork.merge_accept(ctx, proposal_ref=args.get("proposal_id"), target_ref=args["target"])

def _cmd_merge_withdraw(ctx: AppContext, args: dict) -> AppResult:
    return _fork.merge_withdraw(ctx, proposal_ref=args.get("proposal_id"))

def _cmd_notifications(ctx: AppContext, args: dict) -> AppResult:
    return _notify.list_notifications(ctx, unread_only=not args.get("all", False))

def _cmd_notifications_read(ctx: AppContext, args: dict) -> AppResult:
    return _notify.mark_read_notification(ctx, notification_id=args["notification_id"])

def _cmd_sync_status(ctx: AppContext, args: dict) -> AppResult:
    return _bundle.sync_status(ctx, server=args.get("server", ""))

def _cmd_sync_pull(ctx: AppContext, args: dict) -> AppResult:
    return _bundle.sync_pull(ctx, server=args.get("server", ""))

def _cmd_sync_discover(ctx: AppContext, args: dict) -> AppResult:
    return _bundle.sync_discover(ctx, server=args.get("server", ""),
        depth=int(args.get("depth", 1)))

def _cmd_maintainer_add(ctx: AppContext, args: dict) -> AppResult:
    return _maintainer.add(ctx, article_ref=args["article_id"], target_ref=args["target_user"])

def _cmd_maintainer_remove(ctx: AppContext, args: dict) -> AppResult:
    return _maintainer.remove(ctx, article_ref=args["article_id"], target_ref=args["target_user"])

def _cmd_maintainer_list(ctx: AppContext, args: dict) -> AppResult:
    return _maintainer.list_article_maintainers(ctx, article_ref=args["article_id"])


# ═══════════════════════════════════════════════════════════════════════════════
# Command table
# ═══════════════════════════════════════════════════════════════════════════════

# (group, action) → (handler_fn, {arg_name: takes_value})
# takes_value: True = --key value or positional, False = --flag (boolean)
COMMAND_TABLE: dict[tuple[str, str], tuple[callable, dict[str, bool]]] = {
    # Account
    ("account", "register"):     (_cmd_register,         {"name": True}),
    ("account", "login"):        (_cmd_login,            {"name": True, "peer": True, "user_id": True}),
    ("account", "whoami"):       (_cmd_whoami,           {}),
    ("account", "search"):       (_cmd_account_search,   {"query": True}),
    # Article
    ("article", "create"):       (_cmd_article_create,   {"title": True, "format": True, "content": True, "publish": False, "scores": True}),
    ("article", "show"):         (_cmd_article_show,     {"id": True, "show": True}),
    ("article", "list"):         (_cmd_article_list,     {"search": True, "status": True, "mine": False, "feed": False, "bookmarked": False, "user": True, "server": True, "limit": True}),
    ("article", "edit"):         (_cmd_article_edit,     {"id": True, "content": True, "title": True, "message": True}),
    ("article", "publish"):      (_cmd_article_publish,  {"id": True, "scores": True}),
    ("article", "delete"):       (_cmd_article_delete,   {"id": True}),
    ("article", "scan"):         (_cmd_article_scan,     {}),
    ("article", "diff"):         (_cmd_article_diff,     {"id": True, "hash1": True, "hash2": True}),
    # Social
    ("follow", None):            (_cmd_follow,           {"user_identifier": True}),
    ("unfollow", None):          (_cmd_unfollow,         {"user_identifier": True}),
    ("following", None):         (_cmd_following,        {"user": True}),
    ("followers", None):         (_cmd_followers,        {"user": True}),
    ("school", None):            (_cmd_school,           {"limit": True, "local": False, "server": True}),
    ("bookmark", "add"):         (_cmd_bookmark_add,     {"article_id": True}),
    ("bookmark", "remove"):      (_cmd_bookmark_remove,  {"article_id": True}),
    # Review
    ("review", "submit"):        (_cmd_review_submit,    {"article_id": True, "scores": True, "comment": True}),
    ("review", "list"):          (_cmd_review_list,      {"article_id": True}),
    ("review", "reply"):         (_cmd_review_reply,     {"article_id": True, "to": True, "content": True}),
    ("review", "invite"):        (_cmd_review_invite,    {"article_id": True, "user": True}),
    ("review", "accept"):        (_cmd_review_accept,    {"article_id": True}),
    ("review", "decline"):       (_cmd_review_decline,   {"article_id": True}),
    ("review", "rate"):          (_cmd_review_rate,      {"article_id": True, "reviewer": True, "helpfulness": True}),
    # Fork / Merge
    ("fork", None):              (_cmd_fork,             {"article_id": True}),
    ("merge", "propose"):        (_cmd_merge_propose,    {"fork_id": True, "target": True}),
    ("merge", "accept"):         (_cmd_merge_accept,     {"proposal_id": True, "target": True}),
    ("merge", "withdraw"):       (_cmd_merge_withdraw,   {"proposal_id": True}),
    # Notifications
    ("notifications", None):     (_cmd_notifications,    {"all": False}),
    ("notifications", "read"):   (_cmd_notifications_read, {"notification_id": True}),
    # Sync
    ("sync", "status"):          (_cmd_sync_status,      {"server": True}),
    ("sync", "pull"):            (_cmd_sync_pull,        {"server": True}),
    ("sync", "discover"):        (_cmd_sync_discover,    {"depth": True, "max_users": True, "server": True}),
    # Maintainer
    ("maintainer", "add"):       (_cmd_maintainer_add,   {"article_id": True, "target_user": True}),
    ("maintainer", "remove"):    (_cmd_maintainer_remove,{"article_id": True, "target_user": True}),
    ("maintainer", "list"):      (_cmd_maintainer_list,  {"article_id": True}),
}


# ═══════════════════════════════════════════════════════════════════════════════
# Parser
# ═══════════════════════════════════════════════════════════════════════════════

def _parse_args(raw_args: list[str], arg_spec: dict[str, bool]) -> dict[str, str | bool]:
    """Parse shlex-split args into a dict based on *arg_spec*.

    Positional values are assigned in order; flags (bool) are set True
    when present; ``--key=value`` and ``--key value`` are both supported.
    """
    result: dict[str, str | bool] = {}
    positional: list[str] = []
    i = 0
    while i < len(raw_args):
        a = raw_args[i]
        if a.startswith("--"):
            # --key=value or --key
            if "=" in a:
                key, val = a[2:].split("=", 1)
                key = key.replace("-", "_")
                if key in arg_spec:
                    result[key] = val
            else:
                key = a[2:].replace("-", "_")
                if key in arg_spec:
                    if arg_spec[key]:
                        # Takes a value
                        i += 1
                        if i < len(raw_args) and not raw_args[i].startswith("--"):
                            result[key] = raw_args[i]
                    else:
                        result[key] = True
        else:
            positional.append(a)
        i += 1

    # Assign positional values to required args in order
    pos_names = [k for k, required in arg_spec.items() if required and k not in result]
    for j, val in enumerate(positional):
        if j < len(pos_names):
            result[pos_names[j]] = val

    # Set bool flags (takes_value=False) to False if not present.
    # Value args (takes_value=True) are left unset — the handler provides defaults.
    for k, takes_value in arg_spec.items():
        if not takes_value and k not in result:
            result[k] = False

    return result


# ═══════════════════════════════════════════════════════════════════════════════
# Engine
# ═══════════════════════════════════════════════════════════════════════════════

def execute(cmd_str: str, db) -> bool:
    """Parse and execute a single REPL command against *db*.

    Returns False to exit the REPL, True to continue.
    """
    cmd_str = cmd_str.strip()
    if not cmd_str:
        return True

    # ── Parse ─────────────────────────────────────────────────────────────
    try:
        parts = shlex.split(cmd_str)
    except ValueError as e:
        console.print(f"[error]✗ Parse error: {e}[/]")
        return True

    # ── Lookup ────────────────────────────────────────────────────────────
    group = parts[0]
    action: str | None = None
    rest = parts[1:]

    if len(parts) >= 2 and (group, parts[1]) in COMMAND_TABLE:
        action = parts[1]
        rest = parts[2:]
    elif (group, None) in COMMAND_TABLE:
        pass  # top-level command
    else:
        # Try compound lookup for group+action combos where action is required
        found = False
        if len(parts) >= 2:
            for (g, a), _ in COMMAND_TABLE.items():
                if g == group and a is not None:
                    action = a
                    found = True
                    break
        if not found and (group, None) not in COMMAND_TABLE:
            console.print(f"[error]✗ Unknown command: {cmd_str}[/]. Try :help")
            return True

    key = (group, action)
    if key not in COMMAND_TABLE:
        console.print(f"[error]✗ Unknown command: {cmd_str}[/]. Try :help")
        return True

    handler, arg_spec = COMMAND_TABLE[key]
    args = _parse_args(rest, arg_spec)

    # ── Build context ─────────────────────────────────────────────────────
    ctx = build_context(db)

    # ── Execute ───────────────────────────────────────────────────────────
    try:
        result = handler(ctx, args)
        db.commit()
    except PeerpediaError as e:
        db.rollback()
        _render_error(e)
        return True
    except Exception as e:
        db.rollback()
        _log.exception("REPL command failed: %s", cmd_str)
        console.print(f"[error]✗ Internal error: {e}[/]")
        return True

    # ── Render ────────────────────────────────────────────────────────────
    _render(result)
    return True


# ═══════════════════════════════════════════════════════════════════════════════
# Rendering
# ═══════════════════════════════════════════════════════════════════════════════

def _render(result: AppResult) -> None:
    """Render an ``AppResult`` — Rich output, no JSON mode in REPL."""
    # Notices first
    for notice in result.notices:
        _out_notice(notice)

    code, m = _lookup(result.code)
    if m.kind.name in ("SUCCESS", "INFO") and m.text:
        # Success message
        console.print(f"✓ {m.text.format(**result.params)}" if result.params else f"✓ {m.text}")
        return

    data = result.data
    if not data:
        return

    # Render data based on structure
    if isinstance(data, list) and data and isinstance(data[0], dict):
        _print_table(
            list(data[0].keys()),
            [list(d.values()) for d in data],
        )
    elif isinstance(data, dict):
        items = data.get("items")
        unread = data.get("unread_count")
        if isinstance(items, list):
            if items and isinstance(items[0], dict):
                # List of user-like dicts
                for u in items:
                    uid = u.get("id") or u.get("user_id", "?")
                    display_user(
                        u.get("name", "?"),
                        uid,
                        affiliation=u.get("affiliation", ""),
                        expertise=u.get("expertise"),
                        follower_count=u.get("follower_count"),
                        public_key=u.get("public_key"),
                        created_at=str(u.get("created_at", "")) if u.get("created_at") else "",
                    )
            elif unread is not None and items:
                # Notifications
                _print_table(
                    ["Event", "Message", "Read"],
                    [[n.get("event", "?"), n.get("message", "?"), "✓" if n.get("read") else "—"]
                     for n in items],
                    title=f"Notifications ({unread} unread)",
                )
            elif not items:
                pass  # empty list — already rendered by handler
        else:
            # Single-user dict (whoami)
            uid = data.get("id", "?")
            display_user(
                data.get("name", "?"),
                uid,
                public_key=data.get("public_key"),
                affiliation=data.get("affiliation", ""),
                expertise=data.get("expertise"),
                created_at=str(data.get("created_at", "")) if data.get("created_at") else "",
            )


def _out_notice(notice) -> None:
    """Render a notice to the console."""
    code, m = _lookup(notice.code)
    if m.text:
        text = m.text.format(**notice.params) if notice.params else m.text
        console.print(text)


def _render_error(error: PeerpediaError) -> None:
    """Render a ``PeerpediaError`` to the console."""
    code, m = _lookup(error.code)
    console.print(f"[error]✗ {m.text.format(**error.context) if hasattr(error, 'context') and error.context else str(error)}[/]")
    if m.suggestion:
        console.print(f"  [dim]→ {m.suggestion}[/]")
    if m.see_also:
        console.print(f"  [dim]See also: {' · '.join(m.see_also)}[/]")
