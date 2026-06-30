# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""REPL meta-command dispatch — :help, :quit, :theme, :feed, etc.

Meta-commands are REPL-only (not CLI).  Each command manages its own DB
session via the engine (per-command unit of work).  No argparse dependency.
"""

from __future__ import annotations

import sys

from peerpedia_core.repl.help import _meta_help
from peerpedia_core.repl.meta import (
    _meta_user, _meta_article, _meta_theme, _show_inbox,
)
from peerpedia_core.repl.state import console

import peerpedia_core.repl.state as _st


# ═══════════════════════════════════════════════════════════════════════════════
# Meta-command handlers — (arg: str) -> bool
# ═══════════════════════════════════════════════════════════════════════════════

def _handle_quit(arg: str) -> bool:
    return False


def _handle_compact(arg: str) -> bool:
    _st.set_compact(not _st._repl_compact)
    mode = "compact table" if _st._repl_compact else "rich panels"
    console.print(f"[muted]Output mode: {mode}.[/]")
    return True


def _handle_feed(arg: str) -> bool:
    from peerpedia_core.repl.engine import execute
    return execute("article list --feed")


def _handle_school(arg: str) -> bool:
    if sys.stdout.isatty():
        from peerpedia_core.repl.browse import _browse_school
        from peerpedia_core.repl.state import new_session
        db = new_session()
        try:
            result = _browse_school(db)
        finally:
            db.close()
        if result and result.startswith("follow:"):
            target_id = result[len("follow:"):]
            from peerpedia_core.repl.engine import execute
            return execute(f"follow {target_id}")
    else:
        from peerpedia_core.repl.engine import execute
        return execute("school --local")
    return True


def _handle_write(arg: str) -> bool:
    from peerpedia_core.repl.engine import execute
    return _meta_write(execute)


def _handle_help(arg: str) -> bool:
    _meta_help(arg.strip())
    return True


def _handle_user(arg: str) -> bool:
    _meta_user(arg.strip())
    return True


def _handle_article(arg: str) -> bool:
    _meta_article(arg.strip())
    return True


def _handle_theme(arg: str) -> bool:
    _meta_theme(arg.strip())
    return True


def _handle_inbox(arg: str) -> bool:
    _show_inbox()
    return True


# ═══════════════════════════════════════════════════════════════════════════════
# Dispatch table
# ═══════════════════════════════════════════════════════════════════════════════

_META_DISPATCH = {
    ":quit":    _handle_quit,
    ":q":       _handle_quit,
    ":help":    _handle_help,
    ":h":       _handle_help,
    ":user":    _handle_user,
    ":u":       _handle_user,
    ":article": _handle_article,
    ":a":       _handle_article,
    ":theme":   _handle_theme,
    ":inbox":   _handle_inbox,
    ":compact": _handle_compact,
    ":feed":    _handle_feed,
    ":school":  _handle_school,
    ":write":   _handle_write,
}

_META_COMMANDS = list(_META_DISPATCH.keys())


def _dispatch_meta(cmd_str: str) -> bool | None:
    """Look up a ``:<command>`` string in ``_META_DISPATCH`` and run it.

    Returns True/False if *cmd_str* is a meta-command and was handled,
    or None if *cmd_str* does not start with ``:``.
    """
    if not cmd_str.startswith(":"):
        return None

    parts = cmd_str.split(maxsplit=1)
    meta = parts[0]
    arg = parts[1] if len(parts) > 1 else ""

    handler = _META_DISPATCH.get(meta)
    if handler is not None:
        return handler(arg)

    console.print(f"[error]Unknown meta-command: {meta}[/]. Try :help")
    return True
