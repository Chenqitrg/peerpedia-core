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
import sys
import time

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.history import FileHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.lexers import PygmentsLexer
from pygments.lexers.shell import BashLexer
from rich.panel import Panel
from rich.text import Text

from peerpedia_core.cli import build_parser
from peerpedia_core.cli.display import console, theme
from peerpedia_core.cli.helpers import (
    _close_db, _ensure_db, _read_session,
    count_articles, publish_ready_articles,
)
from peerpedia_core.cli.parser import get_cmd_map
from peerpedia_core.config.params import params
from peerpedia_core.config.paths import REPL_HISTORY_FILE

from peerpedia_core.repl.commands import _dispatch, _META_COMMANDS, _meta_theme
from peerpedia_core.repl.state import (
    _get_parser, _prompt_text, _refresh_completions, _repl_user,
    _repl_completion_words, console as _repl_console, repl_style,
    theme as _repl_theme_obj,
)

FLAGS = ["--title", "--format", "--content", "--user", "--json", "--rich", "--force",
         "--scores", "--comment", "--commit-hash", "--target", "--status",
         "--publish", "--no-editor", "--server"]


def run():
    """Start the interactive REPL."""
    # Gracefully exit if stdin is not a TTY — scripting/piping should use
    # the CLI directly (peerpedia <command>), not the REPL.
    if not sys.stdin.isatty():
        parser = build_parser()
        parser.print_help()
        print("\n[muted]REPL requires a terminal. Use 'peerpedia <command>' for scripting.[/]")
        return

    global _repl_user
    db = _ensure_db()
    session_data = _read_session()

    if session_data and _repl_user is None:
        import peerpedia_core.repl.state as _st
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

    # ── Startup banner ──────────────────────────────────────────────────
    console.print()
    if session_data:
        user_id = session_data.get("user_id", "")
        user_name = session_data.get("name", "?")
        try:
            drafts = count_articles(db, status="draft", author_id=user_id)
            in_review = count_articles(db, status="sedimentation", author_id=user_id)
            published = count_articles(db, status="published", author_id=user_id)
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
        user_line.append(f"  {user_id[:8]}", style="muted")
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

    # ── REPL session setup ──────────────────────────────────────────────
    REPL_HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    COMMANDS = sorted(get_cmd_map().keys()) + _META_COMMANDS
    # Static completion words — computed once, never change.
    _STATIC_WORDS = frozenset(COMMANDS + FLAGS)
    _refresh_completions()

    class _ReplCompleter(WordCompleter):
        """Dynamic completer: commands + flags + live article IDs and @names."""
        def get_completions(self, document, complete_event):
            self.words = sorted(_STATIC_WORDS | set(_repl_completion_words))
            self.words_changed = True
            yield from super().get_completions(document, complete_event)

    completer = _ReplCompleter([], ignore_case=True, sentence=True)

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
        mouse_support=True,
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
                if session_name and session_name != _repl_user:
                    import peerpedia_core.repl.state as _st
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
                    console.print(f"[info]{count} 篇文章已自动发布[/]")
                _last_scan = now

            if not should_continue:
                console.print("[muted]Bye.[/]")
                break
    finally:
        _close_db()
