# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""REPL entry point — session setup, main loop, periodic scan."""

from __future__ import annotations

import os as _os
import sys
import time

from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.lexers import PygmentsLexer
from pygments.lexers.shell import BashLexer

import peerpedia_core.repl.state as _st
from peerpedia_core.repl.state import console
from peerpedia_core.app.context import read_session as _read_session
from peerpedia_core.core import publish_ready_articles
from peerpedia_core.repl.state import close_db as _close_db, new_session
from peerpedia_core.config.params import params
from peerpedia_core.config.paths import REPL_HISTORY_FILE

from peerpedia_core.repl.banner import show_startup_banner
from peerpedia_core.repl.completer import (
    FLAGS, build_command_list, make_completer,
)
from peerpedia_core.repl.dispatch import _META_COMMANDS, _dispatch_meta
from peerpedia_core.repl.engine import execute as _execute_command
from peerpedia_core.repl.meta import _meta_theme
from peerpedia_core.repl.state import (
    _prompt_text, _refresh_completions, repl_style,
)


def run():
    """Start the interactive REPL."""
    if not sys.stdin.isatty():
        console.print("[bold]PeerPedia REPL[/] requires a terminal.")
        console.print("Use [accent]peerpedia <command>[/] for scripting, "
                      "or [accent]peerpedia --help[/] for the command list.")
        return

    db = new_session()
    try:
        session_data = _read_session()

        if session_data and _st._repl_user is None:
            _st._repl_user = session_data.get("name")

        if _os.environ.get("COLORFGBG"):
            try:
                bg_hex = _os.environ["COLORFGBG"].split(";")[-1]
                if int(bg_hex) < 8:
                    _meta_theme("dark")
            except (ValueError, IndexError):
                pass

        show_startup_banner(db, session_data)
    finally:
        db.close()

    # ── Session setup ──────────────────────────────────────────────────
    REPL_HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    _STATIC_WORDS = frozenset(build_command_list() + FLAGS)
    _refresh_completions()
    completer = make_completer(_STATIC_WORDS)

    kb = KeyBindings()

    @kb.add("enter")
    def _(event):
        event.current_buffer.validate_and_handle()

    @kb.add("c-j")
    def _(event):
        event.current_buffer.insert_text("\n")

    session = PromptSession(
        history=FileHistory(str(REPL_HISTORY_FILE)),
        completer=completer,
        style=repl_style,
        mouse_support=False,
        key_bindings=kb,
        lexer=PygmentsLexer(BashLexer),
    )

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

            if cmd.startswith(":"):
                should_continue = _dispatch_meta(cmd)
                if not should_continue:
                    break
            else:
                should_continue = _execute_command(cmd)

            sid = _read_session()
            if sid:
                session_name = sid.get("name", "")
                if session_name and session_name != _st._repl_user:
                    _st._repl_user = session_name

            _refresh_completions()

            now = time.time()
            if now - _last_scan > params.sink.scan_interval_seconds:
                db2 = new_session()
                try:
                    count = publish_ready_articles(db2)
                    db2.commit()
                    if count > 0:
                        console.print(f"[info]{count} article(s) auto-published[/]")
                finally:
                    db2.close()
                _last_scan = now

            if not should_continue:
                console.print("[muted]Bye.[/]")
                break
    finally:
        _close_db()
