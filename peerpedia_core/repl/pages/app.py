# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""REPL application — page stack, mode switching, command dispatch."""

from __future__ import annotations

from prompt_toolkit.application import Application
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import HSplit, Layout, Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.styles import Style

from peerpedia_core.app.commandspec import spec_for_cmd_id
from peerpedia_core.app.context import build_context
from peerpedia_core.repl.constants import GREETINGS, PROMPT_DEFAULT, PROMPT_MOTHER
from peerpedia_core.repl.engine import execute as _execute_command
from peerpedia_core.repl.pages import Page
from peerpedia_core.repl.pages.article_list import ArticleListPage
from peerpedia_core.repl.pages.placeholder import PlaceholderPage
from peerpedia_core.repl.state import console, new_session, repl_style


class ReplApplication:
    """Full-screen REPL with page stack navigation.

    Two modes:
      - Command mode (stack empty): input is a command, Enter executes it
      - Page mode (stack non-empty): input filters the current page, Esc pops
    """

    def __init__(self):
        self._stack: list[Page] = []
        self._input_text: str = ""
        self._prompt_text: str = PROMPT_DEFAULT
        self._mother_mode: bool = False

    # ── Public API ─────────────────────────────────────────────────────────

    @property
    def current_page(self) -> Page | None:
        return self._stack[-1] if self._stack else None

    @property
    def is_command_mode(self) -> bool:
        return len(self._stack) == 0

    def push(self, page: Page) -> None:
        self._stack.append(page)
        self._input_text = ""

    def pop(self) -> None:
        if self._stack:
            self._stack.pop()
        self._input_text = ""

    # ── Run ────────────────────────────────────────────────────────────────

    def run(self) -> None:
        kb = self._build_keybindings()
        app = Application(
            layout=self._build_layout(),
            full_screen=True,
            mouse_support=True,
            style=repl_style,
            key_bindings=kb,
        )
        app.run()

    # ── Layout ─────────────────────────────────────────────────────────────

    def _build_layout(self) -> Layout:
        return Layout(HSplit([
            Window(FormattedTextControl(self._render_body)),
            Window(height=1, char=" "),
            Window(FormattedTextControl(self._render_input)),
        ]))

    def _render_body(self):
        """Return fragments for the main area (page or empty)."""
        page = self.current_page
        if page is None:
            return [("class:muted", "  Type a command (new, mine, feed, school, user, quit).\n")]
        # For now, placeholder page just renders its layout via the page stack
        return [("", "")]

    def _render_input(self):
        """Return fragments for the bottom input line."""
        return [("class:prompt", self._prompt_text), ("", self._input_text)]

    # ── Key bindings ───────────────────────────────────────────────────────

    def _build_keybindings(self) -> KeyBindings:
        kb = KeyBindings()

        @kb.add("enter")
        def _(event):
            if self.is_command_mode:
                self._dispatch_command(self._input_text)
                self._input_text = ""
            else:
                page = self.current_page
                if page:
                    new_page = page.handle_key("enter")
                    if new_page:
                        self.push(new_page)

        @kb.add("escape")
        def _(event):
            if self.is_command_mode:
                self._input_text = ""
            else:
                self.pop()
            if self._mother_mode:
                self._mother_mode = False
                self._prompt_text = PROMPT_DEFAULT

        @kb.add("up")
        def _(event):
            page = self.current_page
            if page and not self.is_command_mode:
                page.move_focus(-1)

        @kb.add("down")
        def _(event):
            page = self.current_page
            if page and not self.is_command_mode:
                page.move_focus(1)

        @kb.add("tab")
        def _(event):
            page = self.current_page
            if page:
                page.handle_key("tab")

        @kb.add("<any>")
        def _(event):
            # Any printable character → append to input text
            if event.data and len(event.data) == 1 and event.data.isprintable():
                ch = event.data
                # ? → mother mode
                if ch == "?" and self.is_command_mode and not self._input_text:
                    self._mother_mode = True
                    self._prompt_text = PROMPT_MOTHER
                    return
                if self.is_command_mode:
                    self._input_text += ch
                else:
                    page = self.current_page
                    if page:
                        page.filter_query += ch
                        page.focus_index = 0

        @kb.add("backspace")
        def _(event):
            if self.is_command_mode or not self.current_page:
                if self._input_text:
                    last = self._input_text[-1]
                    self._input_text = self._input_text[:-1]
                    # If deleting the ? that triggered mother mode
                    if self._mother_mode and not self._input_text:
                        self._mother_mode = False
                        self._prompt_text = PROMPT_DEFAULT
            else:
                page = self.current_page
                if page and page.filter_query:
                    page.filter_query = page.filter_query[:-1]

        return kb

    # ── Command dispatch ───────────────────────────────────────────────────

    def _dispatch_command(self, text: str) -> None:
        """Parse and dispatch a command-line string."""
        cmd = text.strip()
        if not cmd:
            return

        # Easier eggs (Phase 7 polish will add more)
        if cmd in ("hi", "hello"):
            import random
            console.print(f"[info]{random.choice(GREETINGS)}[/]")
            return

        if cmd == "quit":
            import sys
            sys.exit(0)

        if cmd in ("mine", "feed"):
            self._open_article_list(cmd)
        elif cmd in ("new", "school"):
            self.push(PlaceholderPage())  # Phase 4/6 will replace
        else:
            _execute_command(cmd)

    def _open_article_list(self, cmd: str) -> None:
        """Execute an article listing command and open the ArticleList page."""
        db = new_session()
        try:
            ctx = build_context(db)
            spec = spec_for_cmd_id("article.list")
            result = spec.handler(ctx, {"search": "", "status": "",
                                         "mine": cmd == "mine",
                                         "feed": cmd == "feed"})
            articles = result.data.get("items", []) if result.data else []
        finally:
            db.close()

        if articles:
            self.push(ArticleListPage(articles))
