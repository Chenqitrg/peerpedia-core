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
from peerpedia_core.presentation.rich.components import (
    auto_publish_msg, repl_bye_msg, repl_interrupt_msg, repl_tty_required,
)

from peerpedia_core.repl.banner import show_startup_banner
from peerpedia_core.repl.completer import (
    FLAGS, build_command_list, make_completer,
)
from peerpedia_core.repl.engine import execute as _execute_command
from peerpedia_core.repl.meta import _meta_theme
from peerpedia_core.repl.state import (
    _prompt_text, _refresh_completions, repl_style,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Startup helpers
# ═══════════════════════════════════════════════════════════════════════════════


def _detect_theme_from_env() -> None:
    """Auto-detect dark terminal background from COLORFGBG env var."""
    if not _os.environ.get("COLORFGBG"):
        return
    try:
        bg_hex = _os.environ["COLORFGBG"].split(";")[-1]
        if int(bg_hex) < 8:
            _meta_theme("dark")
    except (ValueError, IndexError):
        pass


def _startup() -> None:
    """Initialize session, detect theme, show banner."""
    db = new_session()
    try:
        session_data = _read_session()
        _detect_theme_from_env()
        show_startup_banner(db, session_data)
    finally:
        db.close()


def _maybe_auto_publish(last_scan: float) -> float:
    """Run sink scan if interval has elapsed.  Returns updated timestamp."""
    now = time.time()
    if now - last_scan <= params.sink.scan_interval_seconds:
        return last_scan
    db = new_session()
    try:
        count = publish_ready_articles(db)
        db.commit()
        if count > 0:
            console.print(auto_publish_msg(count))
    finally:
        db.close()
    return now


# ═══════════════════════════════════════════════════════════════════════════════
# Main loop
# ═══════════════════════════════════════════════════════════════════════════════


def _build_prompt_session(static_words: frozenset[str]) -> PromptSession:
    """Build the prompt_toolkit PromptSession with key bindings."""
    kb = KeyBindings()

    @kb.add("enter")
    def _(event):
        event.current_buffer.validate_and_handle()

    @kb.add("c-j")
    def _(event):
        event.current_buffer.insert_text("\n")

    return PromptSession(
        history=FileHistory(str(REPL_HISTORY_FILE)),
        completer=make_completer(static_words),
        style=repl_style,
        mouse_support=False,
        key_bindings=kb,
        lexer=PygmentsLexer(BashLexer),
    )


def _post_command_cycle(last_scan: float) -> float:
    """Refresh completions, auto-publish.  Returns new timestamp."""
    _refresh_completions()
    return _maybe_auto_publish(last_scan)


def run():
    """Start the interactive REPL."""
    if not sys.stdin.isatty():
        console.print(repl_tty_required())
        return

    _startup()
    _close_db()  # close the startup DB session's engine

    from peerpedia_core.repl.pages.app import ReplApplication
    app = ReplApplication()
    try:
        app.run()
    finally:
        _close_db()
