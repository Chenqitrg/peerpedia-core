# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""REPL interactive browsing — school leaderboard.

Article and review browsers removed in Phase 0 (replaced by page stack).
School browser kept temporarily, will be replaced in Phase 4.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Generic, TypeVar

from prompt_toolkit.application import Application
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import HSplit, Layout, Window
from prompt_toolkit.layout.controls import FormattedTextControl

import peerpedia_core.repl.state as _st
from peerpedia_core.app.context import read_session
from peerpedia_core.core import get_top_users_by_followers
from peerpedia_core.repl.state import console

T = TypeVar("T")
Fragment = tuple[str, str]

# ── Constants ───────────────────────────────────────────────────────────────

_SCHOOL_PAGE_SIZE = 20
_SCHOOL_NAME_WIDTH = 20
_SCHOOL_ACTIONS_HINT = "Enter: follow  "
_RANK_WIDTH = 3


# ── Cursor ──────────────────────────────────────────────────────────────────


@dataclass
class BrowserCursor:
    index: int = 0

    def move(self, delta: int, item_count: int) -> None:
        if item_count > 0:
            self.index = (self.index + delta) % item_count


# ── Action ──────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class BrowserAction(Generic[T]):
    key: str
    handler: Callable[[T], str | None]


# ── ListBrowser ─────────────────────────────────────────────────────────────


class ListBrowser(Generic[T]):
    """Generic full-screen list browser.  Temporary — replaced in Phase 4."""

    def __init__(
        self, *, title: str, items: Sequence[T],
        render_item: Callable[[T, int, bool], list[Fragment]],
        status_text: Callable[[T, int, int], str],
        actions: Sequence[BrowserAction[T]] = (),
        lines_per_item: int = 1,
    ):
        self._title = title
        self._items = list(items)
        self._render_item = render_item
        self._status_text = status_text
        self._actions = actions
        self._lines_per_item = lines_per_item
        self._cursor = BrowserCursor()

    def run(self) -> str | None:
        kb = KeyBindings()

        @kb.add("up")
        def _(event):
            self._cursor.move(-1, len(self._items))

        @kb.add("down")
        def _(event):
            self._cursor.move(1, len(self._items))

        @kb.add("q")
        @kb.add("escape")
        def _(event):
            event.app.exit(result=None)

        for action in self._actions:
            @kb.add(action.key)
            def _(event, a=action):
                item = self._items[self._cursor.index]
                result = a.handler(item)
                if result is not None:
                    event.app.exit(result=result)

        list_window = Window(
            FormattedTextControl(self._render),
            get_vertical_scroll=lambda _: self._cursor.index * self._lines_per_item,
        )

        root = HSplit([
            Window(FormattedTextControl(
                [("class:prompt", f"▔▔▔ {self._title} ")])),
            list_window,
            Window(height=1, char=" "),
            Window(FormattedTextControl(self._status), style="class:status-bar"),
        ])

        app = Application(
            layout=Layout(root),
            full_screen=True,
            mouse_support=True,
            style=_st.repl_style,
            key_bindings=kb,
        )
        return app.run()

    def _render(self) -> list[Fragment]:
        fragments: list[Fragment] = []
        for i, item in enumerate(self._items):
            fragments.extend(self._render_item(item, i, i == self._cursor.index))
        return fragments

    def _status(self) -> str:
        if not self._items:
            return ""
        item = self._items[self._cursor.index]
        return self._status_text(item, self._cursor.index, len(self._items))


# ── School browser ──────────────────────────────────────────────────────────


def _get_session_user_id() -> str:
    s = read_session()
    return s["user_id"] if s else ""


def _render_user_line(user, rank: int, is_selected: bool, *, is_self: bool) -> Fragment:
    prefix = "▸" if is_selected else " "
    style = "class:selected" if is_selected else ""
    fc = getattr(user, "follower_count", 0)
    self_mark = " (you)" if is_self else ""
    text = f"{prefix} {rank:>{_RANK_WIDTH}}. {user.name:<{_SCHOOL_NAME_WIDTH}} {fc} followers{self_mark}\n"
    return style, text


def _user_status_text(user, index: int, total: int, *, is_self: bool) -> str:
    hint = "" if is_self else _SCHOOL_ACTIONS_HINT
    self_note = " (you)" if is_self else ""
    return f" {index + 1}/{total}  ▸ {user.name}{self_note}  │  {hint}q: back  ↑↓/wheel:scroll"


def _browse_school(db) -> str | None:
    users = get_top_users_by_followers(db, limit=_SCHOOL_PAGE_SIZE)
    if not users:
        console.print("[muted]No users found.[/]")
        return None

    current_user_id = _get_session_user_id()
    is_self = lambda u: u.id == current_user_id

    return ListBrowser(
        title="School — Top Users",
        items=users,
        render_item=lambda u, i, s: [_render_user_line(u, i + 1, s, is_self=is_self(u))],
        status_text=lambda u, i, t: _user_status_text(u, i, t, is_self=is_self(u)),
        actions=[
            BrowserAction(
                key="enter",
                handler=lambda u: f"follow:{u.id}" if not is_self(u) else None,
            ),
        ],
        lines_per_item=1,
    ).run()
