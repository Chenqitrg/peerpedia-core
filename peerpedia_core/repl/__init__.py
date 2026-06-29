# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

r"""Interactive REPL for PeerPedia — persistent session, same commands as CLI.

Usage::

    peerpedia repl          enter the REPL explicitly
    peerpedia               enter the REPL (when no subcommand given)

Architecture
------------
``repl/`` only imports from ``cli/`` (helpers, display, parser).  All data
access goes through ``cli.helpers`` — no direct ``commands/`` or ``storage/``
imports.  ``cli/`` never imports from ``repl/``, so there is zero circular
dependency.  No lazy imports are needed.
"""

from __future__ import annotations

import os as _os
import re
import sys
import time

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.history import FileHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.lexers import PygmentsLexer
from pygments.lexers.shell import BashLexer
from rich.panel import Panel
from rich.text import Text

import peerpedia_core.repl.state as _st
from peerpedia_core.cli import build_parser
from peerpedia_core.cli.info import console, theme
from peerpedia_core.app.context import read_session as _read_session
from peerpedia_core.core import count_articles, publish_ready_articles
from peerpedia_core.repl.state import close_db as _close_db, ensure_db as _ensure_db
from peerpedia_core.types import short_id
from peerpedia_core.cli.dispatch import get_cmd_map_for_parser as get_cmd_map
from peerpedia_core.config.params import params
from peerpedia_core.config.paths import REPL_HISTORY_FILE

from peerpedia_core.repl.dispatch import _dispatch, _META_COMMANDS
from peerpedia_core.repl.meta import _meta_theme
from peerpedia_core.repl.state import (
    _get_parser, _prompt_text, _refresh_completions,
    repl_style,
)

# Every flag recognised by the CLI parser — used for tab completion.
# Generated from COMMAND_GROUPS + TOP_LEVEL so it stays in sync.
FLAGS = [
    "--all", "--bookmarked", "--comment", "--content", "--depth", "--feed",
    "--force", "--format", "--from", "--helpfulness", "--host", "--json",
    "--limit", "--local", "--max-users", "--mine", "--name", "--no-editor",
    "--password", "--peer", "--port", "--public-url", "--publish",
    "--reviewer", "--rich", "--scores", "--search", "--server", "--show",
    "--status", "--target", "--target-user", "--title", "--to", "--user",
    "--user-id", "--verbose",
]


def _show_startup_banner(db, session_data: dict | None) -> None:
    """Print the REPL welcome banner with user stats (or registration prompt)."""
    console.print()
    if session_data:
        user_id = session_data.get("user_id", "")
        user_name = session_data.get("name", "?")
        try:
            drafts = count_articles(db, statuses={"draft"}, author_id=user_id)
            in_review = count_articles(db, statuses={"sedimentation"}, author_id=user_id)
            published = count_articles(db, statuses={"published"}, author_id=user_id)
            parts = []
            if drafts: parts.append(f"[bold]{drafts}[/] draft(s)")
            if in_review: parts.append(f"[bold]{in_review}[/] in review")
            if published: parts.append(f"[bold]{published}[/] published")
            status_line = " · ".join(parts) if parts else "no articles yet"
        except Exception:
            import logging
            logging.getLogger(__name__).warning(
                "Failed to load REPL dashboard stats", exc_info=True
            )
            status_line = "?"
        greeting = Text()
        greeting.append("✧ ", style=theme.styles['accent'])
        greeting.append("PeerPedia", style=f"bold {theme.styles['info']}")
        greeting.append("  scholarly terminal", style="muted")
        console.print(Panel(greeting, border_style="muted", padding=(0, 2)))
        user_line = Text()
        user_line.append(user_name, style=f"bold {theme.styles['accent']}")
        user_line.append(f"  {short_id(user_id)}", style="muted")
        console.print(f"  {user_line}")
        console.print(f"  [muted]{status_line}[/]")
    else:
        greeting = Text()
        greeting.append("✧ ", style=theme.styles['accent'])
        greeting.append("PeerPedia", style=f"bold {theme.styles['info']}")
        console.print(Panel(greeting, border_style="muted", padding=(0, 2)))
        console.print("  [muted]Not logged in.  [accent]register --name <name>[/] to begin.[/]")
    console.print("  [dim]Enter submit  ·  Ctrl+J newline  ·  :help commands  ·  :quit exit[/]")
    console.print()


def run():
    """Start the interactive REPL."""
    # Gracefully exit if stdin is not a TTY — scripting/piping should use
    # the CLI directly (peerpedia <command>), not the REPL.
    if not sys.stdin.isatty():
        parser = build_parser()
        parser.print_help()
        print("\n[muted]REPL requires a terminal. Use 'peerpedia <command>' for scripting.[/]")
        return

    db = _ensure_db()
    session_data = _read_session()

    if session_data and _st._repl_user is None:
        _st._repl_user = session_data.get("name")

    # ── Auto-detect terminal background ────────────────────────────────
    if _os.environ.get("COLORFGBG"):
        try:
            bg_hex = _os.environ["COLORFGBG"].split(";")[-1]
            bg_int = int(bg_hex)
            if bg_int < 8:  # dark background
                _meta_theme("dark")
        except (ValueError, IndexError):
            pass

    _show_startup_banner(db, session_data)

    # ── REPL session setup ──────────────────────────────────────────────
    REPL_HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    COMMANDS = sorted(get_cmd_map().keys()) + _META_COMMANDS
    # Static completion words — computed once, never change.
    _STATIC_WORDS = frozenset(COMMANDS + FLAGS)
    _refresh_completions()

    class _ReplCompleter(Completer):
        """Complete the last word of input against the full word list.

        Unlike ``WordCompleter(sentence=True)`` which matches the *entire*
        text-before-cursor (breaking multi-word completion), this completer
        extracts only the last whitespace-delimited token and matches it
        against every known command, flag, article ID, and @name.
        """
        def get_completions(self, document, complete_event):
            text = document.text_before_cursor
            if not text:
                return
            # Find the last whitespace-delimited token.
            m = re.search(r'(\S+)$', text)
            if not m:
                return
            word_before = m.group(1)
            low = word_before.lower()

            # Merge static and dynamic word lists.
            all_words: set[str] = set(_STATIC_WORDS) | set(_st._repl_completion_words)

            yielded: set[str] = set()
            for w in sorted(all_words):
                if w in yielded:
                    continue
                if w.lower().startswith(low):
                    yielded.add(w)
                    yield Completion(
                        w,
                        start_position=-len(word_before),
                        display=w,
                    )

    completer = _ReplCompleter()

    kb = KeyBindings()

    @kb.add("enter")
    def _(event):
        """Enter submits the current input (standard REPL convention)."""
        event.current_buffer.validate_and_handle()

    @kb.add("c-j")
    def _(event):
        """Ctrl+J inserts a newline for multi-line input."""
        event.current_buffer.insert_text("\n")

    session = PromptSession(
        history=FileHistory(str(REPL_HISTORY_FILE)),
        completer=completer,
        style=repl_style,
        mouse_support=False,
        key_bindings=kb,
        lexer=PygmentsLexer(BashLexer),
    )

    parser = _get_parser()
    _last_scan = 0.0

    try:
        while True:
            try:
                cmd = session.prompt(_prompt_text())
            except KeyboardInterrupt:
                console.print("\n[muted](Ctrl-D to exit)[/]")
                continue
            except EOFError:
                console.print("\n[muted]Bye.[/]")
                break

            should_continue = _dispatch(cmd, parser)

            # Sync REPL user with session file (register/login may change it).
            sid = _read_session()
            if sid:
                session_name = sid.get("name", "")
                if session_name and session_name != _st._repl_user:
                    _st._repl_user = session_name

            # Refresh tab completions (new articles/users may have been created).
            _refresh_completions()

            # Periodic scan: check for publishable articles
            now = time.time()
            if now - _last_scan > params.sink.scan_interval_seconds:
                db2 = _ensure_db()
                count = publish_ready_articles(db2)
                db2.commit()
                if count > 0:
                    console.print(f"[info]{count} article(s) auto-published[/]")
                _last_scan = now

            if not should_continue:
                console.print("[muted]Bye.[/]")
                break
    finally:
        _close_db()
