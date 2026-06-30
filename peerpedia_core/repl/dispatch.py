# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""REPL meta-command dispatch — :help, :quit, :theme, :feed, etc.

Meta-commands are REPL-only (not CLI).  They use the REPL's persistent
DB session and the engine for sub-dispatch.  No argparse dependency.
"""

from __future__ import annotations

import sys

from peerpedia_core.repl.help import _meta_help
from peerpedia_core.repl.meta import (
    _meta_user, _meta_article, _meta_theme, _show_inbox,
)
from peerpedia_core.repl.state import console, ensure_db
from peerpedia_core.repl.wizards import _meta_write

import peerpedia_core.repl.state as _st


# ═══════════════════════════════════════════════════════════════════════════════
# Meta-command handlers — (arg: str, db) -> bool
# ═══════════════════════════════════════════════════════════════════════════════

def _handle_quit(arg: str, db) -> bool:
    return False


def _handle_compact(arg: str, db) -> bool:
    _st._repl_compact = not _st._repl_compact
    mode = "compact table" if _st._repl_compact else "rich panels"
    console.print(f"[muted]Output mode: {mode}.[/]")
    return True


def _handle_feed(arg: str, db) -> bool:
    from peerpedia_core.repl.engine import execute
    return execute("article list --feed", db)


def _handle_school(arg: str, db) -> bool:
    if sys.stdout.isatty():
        from peerpedia_core.repl.browse import _browse_school
        result = _browse_school(db)
        if result and result.startswith("follow:"):
            target_id = result.split(":", 1)[1]
            from peerpedia_core.repl.engine import execute
            return execute(f"follow {target_id}", db)
    else:
        from peerpedia_core.repl.engine import execute
        return execute("school --local", db)
    return True


def _handle_write(arg: str, db) -> bool:
    from peerpedia_core.repl.engine import execute
    return _meta_write(execute, db)


def _handle_help(arg: str, db) -> bool:
    _meta_help(arg.strip())
    return True


def _handle_user(arg: str, db) -> bool:
    _meta_user(arg.strip())
    return True


def _handle_article(arg: str, db) -> bool:
    _meta_article(arg.strip())
    return True


def _handle_theme(arg: str, db) -> bool:
    _meta_theme(arg.strip())
    return True


def _handle_inbox(arg: str, db) -> bool:
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


def _dispatch_meta(cmd_str: str, db) -> bool | None:
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
        return handler(arg, db)

    console.print(f"[error]Unknown meta-command: {meta}[/]. Try :help")
    return True
