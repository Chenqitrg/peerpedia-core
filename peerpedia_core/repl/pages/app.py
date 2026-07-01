# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""REPL application — page stack, mode switching, command dispatch."""

from __future__ import annotations

import os
import random
import sys
from pathlib import Path

from prompt_toolkit.application import Application
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import HSplit, Layout, VSplit, Window
from prompt_toolkit.layout.controls import BufferControl, FormattedTextControl

from peerpedia_core.app.commandspec import spec_for_cmd_id
from peerpedia_core.app.context import build_context
from peerpedia_core.editor import open_editor as _open_editor
from peerpedia_core.exceptions import PeerpediaError
from peerpedia_core.repl.completer import FLAGS, ReplCompleter, build_command_list
from peerpedia_core.repl.constants import GREETINGS, PROMPT_DEFAULT, PROMPT_MOTHER
from peerpedia_core.repl.engine import execute as _execute_command
from peerpedia_core.repl.meta import _meta_theme, _show_inbox
from peerpedia_core.repl.pages import Page
from peerpedia_core.repl.pages.article_list import ArticleListPage
from peerpedia_core.repl.pages.school import SchoolPage
from peerpedia_core.repl.pages.user_profile import UserProfilePage
from peerpedia_core.repl.state import console, new_session, repl_style

_PROMPT_MAX_WIDTH = 13  # len("peerpedia > ")


class ReplApplication:
    """Full-screen REPL with page stack navigation.

    Two modes:
      - Command mode (stack empty): input is a command, Enter executes it
      - Page mode (stack non-empty): input filters the current page, Esc pops
    """

    def __init__(self):
        self._stack: list[Page] = []
        self._prompt_text: str = PROMPT_DEFAULT
        self._mother_mode: bool = False
        static_words = frozenset(build_command_list() + FLAGS)
        self._input_buffer = Buffer(
            completer=ReplCompleter(static_words),
        )

    # ── Public API ─────────────────────────────────────────────────────────

    @property
    def current_page(self) -> Page | None:
        return self._stack[-1] if self._stack else None

    @property
    def is_command_mode(self) -> bool:
        return len(self._stack) == 0

    def push(self, page: Page) -> None:
        self._stack.append(page)
        self._input_buffer.reset()

    def pop(self) -> None:
        if self._stack:
            self._stack.pop()
        self._input_buffer.reset()
        # Clear filter on the page we return to
        if self._stack:
            self._stack[-1].filter_query = ""

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
            VSplit([
                Window(
                    FormattedTextControl(self._render_prompt),
                    width=_PROMPT_MAX_WIDTH,
                    dont_extend_width=True,
                ),
                Window(BufferControl(buffer=self._input_buffer)),
            ]),
        ]))

    def _render_body(self):
        """Return fragments for the main area (page or empty)."""
        page = self.current_page
        if page is None:
            return [("class:muted", "  Type a command (new, mine, feed, school, user, quit).\n")]
        fragments: list[tuple[str, str]] = []
        # Breadcrumb for pages below the top
        for p in self._stack[:-1]:
            title = getattr(p, 'title', p.__class__.__name__)
            fragments.append(("class:muted", f"  ─ {title}\n"))
        fragments.extend(page._render())
        return fragments

    def _render_prompt(self):
        """Return fragments for the prompt portion of the input line."""
        return [("class:prompt", self._prompt_text)]

    # ── Key bindings ───────────────────────────────────────────────────────

    def _build_keybindings(self) -> KeyBindings:
        kb = KeyBindings()

        @kb.add("enter")
        def _(event):
            if self.is_command_mode:
                self._dispatch_command(self._input_buffer.text)
                self._input_buffer.reset()
            else:
                page = self.current_page
                if page:
                    if page.filter_query.startswith(":"):
                        self._handle_page_command(page.filter_query)
                        page.filter_query = ""
                    else:
                        new_page = page.handle_key("enter")
                        if new_page:
                            self.push(new_page)

        @kb.add("escape")
        def _(event):
            if self.is_command_mode:
                self._input_buffer.reset()
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
            if self.is_command_mode:
                # Trigger buffer completion
                buf = event.current_buffer
                if buf:
                    buf.start_completion(select_first=False)
            else:
                page = self.current_page
                if page:
                    page.handle_key("tab")

        @kb.add("delete")
        def _(event):
            page = self.current_page
            if not page or self.is_command_mode:
                return
            item = page.focused_item()
            if item is None:
                return
            aid = item.get("id", "")
            if not aid:
                return
            confirm = console.input("[warning]Delete this article? [y/N]: [/]")
            if confirm.strip().lower() == "y":
                _execute_command(f"article delete --force {aid}")

        @kb.add("<any>")
        def _(event):
            # Any printable character → append to input
            if event.data and len(event.data) == 1 and event.data.isprintable():
                ch = event.data
                # ? → mother mode
                if ch == "?" and self.is_command_mode and not self._input_buffer.text:
                    self._mother_mode = True
                    self._prompt_text = PROMPT_MOTHER
                    return
                if self.is_command_mode:
                    self._input_buffer.insert_text(ch)
                else:
                    page = self.current_page
                    if page:
                        # : prefix → page-mode command (not filter)
                        if ch == ":" and not page.filter_query:
                            page.filter_query = ":"
                        elif page.filter_query.startswith(":"):
                            page.filter_query += ch
                            # :command completed on Enter
                        else:
                            page.filter_query += ch
                            page.focus_index = 0

        @kb.add("backspace")
        def _(event):
            if self.is_command_mode:
                buf = self._input_buffer
                if buf.text:
                    buf.delete_before_cursor()
                # Exit mother mode on backspace with empty buffer
                if self._mother_mode and not buf.text:
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

        # Mother mode help
        if self._mother_mode and cmd == "help":
            path = Path(__file__).resolve().parent.parent.parent / "cli" / "help" / "mother.txt"
            if path.exists():
                console.print(path.read_text())
            else:
                console.print("[warning]mother.txt not found[/]")
            return

        # Easter eggs
        if cmd in ("hi", "hello"):
            console.print(f"[info]{random.choice(GREETINGS)}[/]")
            return

        if cmd == "quit":
            sys.exit(0)

        if cmd == "editor":
            self._show_editor()
            return
        if cmd.startswith("editor "):
            self._set_editor(cmd[7:].strip())
            return

        if cmd in ("mine", "feed"):
            self._open_article_list(cmd)
        elif cmd == "school":
            self._open_school()
        elif cmd == "new":
            self._cmd_new()
        elif cmd.startswith("user "):
            self._open_user(cmd[5:].strip())
        elif cmd == "inbox":
            self._show_inbox()
        elif cmd.startswith("theme "):
            self._set_theme(cmd[6:].strip())
        elif cmd == "theme":
            self._set_theme("")
        else:
            _execute_command(cmd)

    # ── Page-mode : commands ──────────────────────────────────────────────

    def _handle_page_command(self, query: str) -> None:
        """Dispatch a :command entered in page mode."""
        page = self.current_page
        if page is None:
            return
        cmd = query.lstrip(":")
        item = page.focused_item()
        if item is None:
            return
        aid = item.get("id", "")

        if cmd == "edit" and aid:
            _execute_command(f"article edit {aid}")
        elif cmd == "publish" and aid:
            _execute_command(f"article publish {aid}")
        elif cmd == "review" and aid:
            _execute_command(f"review submit {aid}")
        elif cmd == "bookmark" and aid:
            _execute_command(f"bookmark add {aid}")
        elif cmd == "fork" and aid:
            _execute_command(f"fork {aid}")
        elif cmd == "share" and aid:
            _execute_command(f"share add {aid}")
        elif cmd == "follow" and aid:
            _execute_command(f"follow {aid}")
        elif cmd == "history" and aid:
            _execute_command(f"article diff {aid}")
        else:
            console.print(f"[warning]Unknown page command: :{cmd}[/]")

    def _cmd_new(self) -> None:
        """Create a new article: open editor for content, prompt for title."""
        try:
            content = _open_editor("# Write your article here\n\n")
        except PeerpediaError:
            console.print("[error]No TTY available for editor[/]")
            return
        if not content.strip() or content.strip() == "# Write your article here":
            console.print("[warning]Empty article, cancelled.[/]")
            return
        title = console.input("[info]Article title: [/]").strip()
        if not title:
            console.print("[warning]No title provided, cancelled.[/]")
            return
        db = new_session()
        try:
            ctx = build_context(db)
            spec = spec_for_cmd_id("article.create")
            result = spec.handler(ctx, {
                "title": title,
                "content": content,
                "no_editor": True,
            })
            db.commit()
            aid = result.data.get("id", "") if result.data else ""
            console.print(f"[success]Article created: {title}[/]")
            if aid:
                console.print(f"  [muted]{aid}[/]")
        except PeerpediaError as e:
            console.print(f"[error]{e.detail}[/]")
        finally:
            db.close()

    def _show_editor(self) -> None:
        editor = os.environ.get("EDITOR", "vim")
        console.print(f"[info]Editor: {editor}[/]")

    def _set_editor(self, path: str) -> None:
        os.environ["EDITOR"] = path
        console.print(f"[info]Editor set to {path}[/]")

    def _open_article_list(self, cmd: str) -> None:
        """Execute an article listing command and open the ArticleList page."""
        db = new_session()
        try:
            ctx = build_context(db)
            spec = spec_for_cmd_id("article.list")
            result = spec.handler(ctx, {"search": "", "status": "",
                                         "mine": "maintainer" if cmd == "mine" else None,
                                         "feed": cmd == "feed"})
            articles = result.data.get("items", []) if result.data else []
        finally:
            db.close()

        if articles:
            self.push(ArticleListPage(articles))

    def _open_school(self) -> None:
        """Execute school command and open School page."""
        db = new_session()
        try:
            ctx = build_context(db)
            spec = spec_for_cmd_id("school")
            result = spec.handler(ctx, {"limit": 20, "local": True})
            users = result.data.get("items", []) if result.data else []
        finally:
            db.close()
        if users:
            self.push(SchoolPage(users))

    def _open_user(self, name: str) -> None:
        """Search for a user and open their profile page."""
        db = new_session()
        try:
            ctx = build_context(db)
            spec = spec_for_cmd_id("account.search")
            result = spec.handler(ctx, {"query": name})
            users = result.data.get("items", []) if result.data else []
            if users:
                u = users[0]
                self.push(UserProfilePage(
                    user_id=u.get("id", name),
                    name=u.get("name", name),
                ))
            else:
                console.print(f"[warning]User '{name}' not found[/]")
        finally:
            db.close()

    def _show_inbox(self) -> None:
        """Show the user's inbox notifications."""
        _show_inbox()

    def _set_theme(self, mode: str) -> None:
        """Switch the REPL theme."""
        _meta_theme(mode)
