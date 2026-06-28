# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""REPL command dispatch — meta-command table + REPL intercepts + CLI bridge.

Architecture::
    dispatch.py  →  meta.py, help.py, wizards.py, bridge.py
    bridge.py    →  help.py            (no back-import)
    wizards.py   →  state.py           (no back-import; dispatch_fn is a parameter)
"""

from __future__ import annotations

import shlex
import sys

from peerpedia_core.repl.state import ensure_db as _ensure_db
from peerpedia_core.types import short_id

import peerpedia_core.repl.state as _st
from peerpedia_core.repl.bridge import execute as _run_cli
from peerpedia_core.repl.help import _meta_help
from peerpedia_core.repl.meta import (
    _meta_user, _meta_article, _meta_theme, _show_inbox,
)
from peerpedia_core.repl.state import console
from peerpedia_core.repl.wizards import _meta_write


# ── Meta-command dispatch table ──────────────────────────────────────────


def _simple_handler(handler, takes_arg: bool = True):
    """Wrap a ``(arg,)`` or ``()`` handler into the unified ``(arg, parser) -> bool``
    signature used by ``_META_DISPATCH``.
    """
    if takes_arg:
        def dispatch_fn(arg, parser):
            handler(arg.strip())
            return True
    else:
        def dispatch_fn(arg, parser):
            handler()
            return True
    return dispatch_fn


def _handle_quit(arg, parser):
    return False


def _handle_compact(arg, parser):
    _st._repl_compact = not _st._repl_compact
    mode = "compact table" if _st._repl_compact else "rich panels"
    console.print(f"[muted]Output mode: {mode}.[/]")
    return True


def _handle_feed(arg, parser):
    try:
        args = parser.parse_known_args(["article", "list", "--feed"])[0]
        if hasattr(args, "func"):
            args.rich = True
            args.json = False
            args.func(args)
    except Exception as e:
        console.print(f"[error]✗ {e}[/]")
    return True


def _handle_school(arg, parser):
    if sys.stdout.isatty():
        from peerpedia_core.repl.browse import _browse_school
        db = _ensure_db()
        result = _browse_school(db)
        if result and result.startswith("follow:"):
            target_id = result.split(":", 1)[1]
            return _dispatch(f"follow {target_id}", parser)
    else:
        return _dispatch("school --local", parser)
    return True


def _handle_write(arg, parser):
    return _meta_write(_dispatch, parser)


# Every meta-command maps to a ``(arg: str, parser) -> bool`` callable.
_META_DISPATCH = {
    ":quit":    _handle_quit,
    ":q":       _handle_quit,
    ":help":    _simple_handler(_meta_help),
    ":h":       _simple_handler(_meta_help),
    ":user":    _simple_handler(_meta_user),
    ":u":       _simple_handler(_meta_user),
    ":article": _simple_handler(_meta_article),
    ":a":       _simple_handler(_meta_article),
    ":theme":   _simple_handler(_meta_theme),
    ":inbox":   _simple_handler(_show_inbox, takes_arg=False),
    ":compact": _handle_compact,
    ":feed":    _handle_feed,
    ":school":  _handle_school,
    ":write":   _handle_write,
}

_META_COMMANDS = list(_META_DISPATCH.keys())


# ── Dispatch ─────────────────────────────────────────────────────────────


def _dispatch_meta(cmd_str: str, parser) -> bool | None:
    """Look up a ``:<command>`` string in ``_META_DISPATCH`` and run it.

    Returns True/False if *cmd_str* is a meta-command and was handled,
    or None if *cmd_str* does not start with ``:`` (caller should fall
    through to CLI execution).
    """
    if not cmd_str.startswith(":"):
        return None

    parts = cmd_str.split(maxsplit=1)
    meta = parts[0]
    arg = parts[1] if len(parts) > 1 else ""

    handler = _META_DISPATCH.get(meta)
    if handler is not None:
        return handler(arg, parser)

    console.print(f"[error]Unknown meta-command: {meta}[/]. Try :help")
    return True


def _dispatch(cmd_str: str, parser) -> bool:
    """Parse and execute a single command. Returns False to exit REPL."""
    cmd_str = cmd_str.strip()
    if not cmd_str:
        return True

    # ── Meta-commands ────────────────────────────────────────────────
    if (result := _dispatch_meta(cmd_str, parser)) is not None:
        return result

    # ── Parse ─────────────────────────────────────────────────────────
    try:
        args_list = shlex.split(cmd_str)
    except ValueError as e:
        console.print(f"[error]✗ Parse error: {e}[/]")
        return True

    if not args_list:
        return True

    cmd = args_list[0]

    # ── REPL intercepts (interactive browse) ──────────────────────────
    if (result := _try_browse_intercept(cmd, args_list, parser)) is not None:
        return result

    # ── Context injection ─────────────────────────────────────────────
    cmd_str, args_list = _inject_context(cmd_str, cmd, args_list)

    # ── CLI execution ─────────────────────────────────────────────────
    return _run_cli(args_list, parser)


# ── REPL intercepts ──────────────────────────────────────────────────────


def _try_browse_intercept(cmd: str, args_list: list[str], parser) -> bool | None:
    """Intercept commands that should open an interactive browser.

    Returns True/False if handled, None to continue to CLI execution.
    """
    # Bare 'list' → interactive article browser
    if cmd == "list" and len(args_list) == 1 and sys.stdout.isatty():
        from peerpedia_core.repl.browse import _browse_articles
        db = _ensure_db()
        result = _browse_articles(db)
        if result:
            if ":" in result:
                _dispatch_action(db, result, parser)
            else:
                _meta_article(result)
                return _dispatch(f"show {result}", parser)
        return True

    # 'review list' with article context → interactive review browser
    if (cmd == "review" and len(args_list) >= 2 and args_list[1] == "list"
            and sys.stdout.isatty()):
        aid = None
        if len(args_list) >= 3 and not args_list[2].startswith("--"):
            aid = args_list[2]
        elif _st._repl_article_id:
            aid = _st._repl_article_id
        if aid:
            from peerpedia_core.repl.browse import _browse_reviews
            db = _ensure_db()
            result = _browse_reviews(db, aid)
            if result:
                if result.startswith("reply:"):
                    reviewer_id = result.split(":", 1)[1]
                    return _dispatch(f"review reply {aid} --to {reviewer_id}", parser)
                else:
                    console.print(f"[accent]{short_id(result)}[/]")
            return True

    return None  # not an intercept — continue to CLI


# ── Context injection ────────────────────────────────────────────────────


def _inject_context(cmd_str: str, cmd: str, args_list: list[str]) -> tuple[str, list[str]]:
    """Inject sticky user / article context into *cmd_str* and *args_list*.

    Returns ``(cmd_str, args_list)`` — possibly modified.
    """
    # Inject --user if sticky user is set.
    _skip_user_inject = {"register", "whoami", "school",
                         ":help", ":h", ":user", ":u", ":article", ":a",
                         ":feed", ":school", ":theme", ":quit", ":q"}
    sticky_user = _st._repl_user
    if (sticky_user and "--user" not in cmd_str
            and cmd not in _skip_user_inject
            and not any(f in cmd_str for f in ("--feed", "--mine", "--bookmarked"))):
        cmd_str += f" --user {shlex.quote(sticky_user)}"
        try:
            args_list = shlex.split(cmd_str)
        except ValueError:
            pass

    # Auto-inject article ID from context.
    sticky_article = _st._repl_article_id
    if sticky_article and cmd in ("show", "publish", "edit", "delete", "fork"):
        rest = cmd_str[len(cmd):].strip()
        if not rest or rest.startswith("-"):
            cmd_str = f"{cmd} {shlex.quote(sticky_article)}"
            if rest:
                cmd_str += f" {rest}"
            try:
                args_list = shlex.split(cmd_str)
            except ValueError:
                pass

    return cmd_str, args_list


# ── Browse action dispatch ───────────────────────────────────────────────


def _dispatch_action(db, result: str, parser) -> None:
    """Handle a browse result like 'publish:<id>' or 'edit:<id>'."""
    if not result or ":" not in result:
        return
    action, article_id = result.split(":", 1)
    _meta_article(article_id)
    if action == "publish":
        _dispatch(f"publish {article_id} --scores \"orig=4,rig=3,comp=4,ped=3,imp=4\"", parser)
    elif action == "edit":
        _dispatch(f"edit {article_id}", parser)
    elif action == "review":
        _dispatch(f"review submit {article_id} --scores \"orig=4,rig=3,comp=4,ped=3,imp=4\"", parser)
    elif action == "bookmark":
        _dispatch(f"bookmark add {article_id}", parser)
