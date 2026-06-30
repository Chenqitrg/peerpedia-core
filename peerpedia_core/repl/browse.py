# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""REPL interactive browsing — full-screen article and user selection views."""

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
from peerpedia_core.core import (
    get_head_hash as _get_article_head_hash,
    get_reviews_for_article,
    get_top_users_by_followers,
    list_articles,
    list_users_by_ids,
)
from peerpedia_core.presentation.rich.components import (
    no_articles_msg, no_rating_stars, no_reviews_msg, no_users_msg,
    star_string, status_label,
)
from peerpedia_core.repl.display import _score_lines
from peerpedia_core.repl.state import console, repl_style

# ═══════════════════════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════════════════════

_HEADER_DECORATION_WIDTH = 50
_TITLE_TRUNCATE = 45
_STATUS_WIDTH = 8
_FULL_CARD_LINES = 7    # 1 title + 5 scores + 1 blank
_COMPACT_CARD_LINES = 1
_SCHOOL_PAGE_SIZE = 20
_RANK_WIDTH = 3
_SCHOOL_NAME_WIDTH = 25
_RATING_PRECISION = ".1f"  # one decimal place for review averages

# Status bar action hints
_ARTICLE_ACTIONS_HINT = "Enter:view p:publish e:edit r:review b:bookmark q:back  ↑↓/wheel:scroll"
_SCHOOL_ACTIONS_HINT = "Enter: follow  q: back  ↑↓/wheel:scroll"
_REVIEW_ACTIONS_HINT = "Enter: view  r: reply  q: back  ↑↓/wheel:scroll"
_REVIEW_NAME_WIDTH = 20

# ═══════════════════════════════════════════════════════════════════════════════
# Types
# ═══════════════════════════════════════════════════════════════════════════════

T = TypeVar("T")
Fragment = tuple[str, str]
# Callbacks that each browser must provide:
#   render_item(item, index, is_selected) → list of styled fragments
#   status_text(item, index, total) → status bar string
#   actions → list of (key, handler) pairs where handler(item) → result string | None
RenderItem = Callable[[T, int, bool], list[Fragment]]
StatusText = Callable[[T, int, int], str]
ActionHandler = Callable[[T], str | None]


@dataclass
class BrowserCursor:
    """Mutable cursor.  Dataclass so closures see mutations without ``list[0]``."""

    index: int = 0

    def move(self, delta: int, item_count: int) -> None:
        self.index = (self.index + delta) % item_count


@dataclass(frozen=True)
class BrowserAction(Generic[T]):
    """A key binding that, when pressed, calls *handler* on the current item."""

    key: str
    handler: ActionHandler[T]


def _browser_result(action: str, object_id: str) -> str:
    """Centralized action-result string: ``'action:id'``."""
    return f"{action}:{object_id}"


# ═══════════════════════════════════════════════════════════════════════════════
# ListBrowser — generic full-screen list browser over any item type
# ═══════════════════════════════════════════════════════════════════════════════


class ListBrowser(Generic[T]):
    """Full-screen scrollable list browser.

    Each concrete browser (articles, users, reviews) provides:
      - *items* — the data to browse
      - *render_item(item, index, is_selected)* → list of Fragment
      - *status_text(item, index, total)* → status bar string
      - *actions* — list of BrowserAction
      - *lines_per_item* — scroll offset per card
    """

    def __init__(
        self,
        *,
        title: str,
        items: Sequence[T],
        render_item: RenderItem[T],
        status_text: StatusText[T],
        actions: Sequence[BrowserAction[T]] = (),
        lines_per_item: int = 1,
    ) -> None:
        self._title = title
        self._items = items
        self._render_item = render_item
        self._status_text = status_text
        self._actions = actions
        self._lines_per_item = lines_per_item
        self._cursor = BrowserCursor()

    # ── public API ──────────────────────────────────────────────────────────

    def run(self) -> str | None:
        """Launch the full-screen browser.  Returns action result or None."""
        kb = KeyBindings()
        self._add_nav_keys(kb)
        self._add_action_keys(kb)
        app = Application(
            layout=Layout(self._root()),
            key_bindings=kb,
            full_screen=True,
            mouse_support=True,
            style=repl_style,
        )
        return app.run()

    # ── layout ──────────────────────────────────────────────────────────────

    def _root(self) -> HSplit:
        return HSplit([
            _header_window(self._title),
            self._list_window(),
            Window(height=1),
            self._status_bar(),
        ])

    def _list_window(self) -> Window:
        return Window(
            content=FormattedTextControl(self._render),
            always_hide_cursor=True,
            get_vertical_scroll=lambda _win: self._cursor.index * self._lines_per_item,
        )

    def _status_bar(self) -> Window:
        return Window(
            height=1,
            content=FormattedTextControl(self._status),
            style="class:status-bar",
        )

    # ── rendering ───────────────────────────────────────────────────────────

    def _render(self) -> list[Fragment]:
        lines: list[Fragment] = []
        for i, item in enumerate(self._items):
            lines.extend(self._render_item(item, i, i == self._cursor.index))
        return lines

    def _status(self) -> str:
        item = self._items[self._cursor.index]
        return self._status_text(item, self._cursor.index, len(self._items))

    # ── key bindings ────────────────────────────────────────────────────────

    def _add_nav_keys(self, kb: KeyBindings) -> None:
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

    def _add_action_keys(self, kb: KeyBindings) -> None:
        for action in self._actions:
            @kb.add(action.key)
            def _(event, a=action):  # capture by default arg to avoid closure bug
                item = self._items[self._cursor.index]
                event.app.exit(result=a.handler(item))


# ═══════════════════════════════════════════════════════════════════════════════
# Prompt-toolkit helpers (used by ListBrowser)
# ═══════════════════════════════════════════════════════════════════════════════


def _header_window(title: str) -> Window:
    return Window(
        height=1,
        content=FormattedTextControl(
            [("class:prompt", f"▔▔▔ {title} " + "▔" * _HEADER_DECORATION_WIDTH)]
        ),
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Shared formatting helpers
# ═══════════════════════════════════════════════════════════════════════════════


def _get_session_user_id() -> str:
    s = read_session()
    return s["user_id"] if s else ""



# ═══════════════════════════════════════════════════════════════════════════════
# Article browser
# ═══════════════════════════════════════════════════════════════════════════════


def _render_compact_card(a, prefix: str, style: str) -> list[Fragment]:
    status = status_label(a.status)
    if a.score:
        star = star_string(int(a.score.get("originality", 0)))
    else:
        star = "—"
    line = (
        f"{prefix} {a.id}  "
        f"{a.title[:_TITLE_TRUNCATE]:<{_TITLE_TRUNCATE}} "
        f"{status:<{_STATUS_WIDTH}} {star}\n"
    )
    return [(style, line)]


def _render_full_card(a, prefix: str, style: str) -> list[Fragment]:
    status = status_label(a.status)
    lines: list[Fragment] = [(style, f"{prefix} {a.id}  {a.title}  {status}\n")]
    for sl in _score_lines(a.score):
        lines.append((style, f"          {sl}\n"))
    lines.append(("", "\n"))
    return lines


def _render_article_item(article, index: int, is_selected: bool, *, compact: bool) -> list[Fragment]:
    prefix = "▸" if is_selected else " "
    style = "class:selected" if is_selected else ""
    if compact:
        return _render_compact_card(article, prefix, style)
    return _render_full_card(article, prefix, style)


def _article_status_text(article, index: int, total: int, *, compact: bool) -> str:
    compact_mark = "[⊞]" if compact else ""
    actions = _ARTICLE_ACTIONS_HINT
    return f" {compact_mark} {index + 1}/{total}  ▸ {article.title[:_TITLE_TRUNCATE]}  │  {actions}"


def _select_article(article) -> str:
    _st.set_article_context(
        article.id, article.title, _get_article_head_hash(article.id),
    )
    return article.id


_ARTICLE_ACTIONS: list[BrowserAction] = [
    BrowserAction(key="enter", handler=_select_article),
    BrowserAction(key="p", handler=lambda a: _browser_result("publish", a.id)),
    BrowserAction(key="e", handler=lambda a: _browser_result("edit", a.id)),
    BrowserAction(key="r", handler=lambda a: _browser_result("review", a.id)),
    BrowserAction(key="b", handler=lambda a: _browser_result("bookmark", a.id)),
]


def _browse_articles(db) -> str | None:
    articles = list_articles(db)
    if not articles:
        console.print(no_articles_msg())
        return None

    compact = _st.session.compact
    return ListBrowser(
        title="Articles",
        items=articles,
        render_item=lambda a, i, s: _render_article_item(a, i, s, compact=compact),
        status_text=lambda a, i, t: _article_status_text(a, i, t, compact=compact),
        actions=_ARTICLE_ACTIONS,
        lines_per_item=_COMPACT_CARD_LINES if compact else _FULL_CARD_LINES,
    ).run()


# ═══════════════════════════════════════════════════════════════════════════════
# School browser
# ═══════════════════════════════════════════════════════════════════════════════


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
        console.print(no_users_msg())
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
                handler=lambda u: _browser_result("follow", u.id) if not is_self(u) else None,
            ),
        ],
        lines_per_item=_COMPACT_CARD_LINES,
    ).run()


# ═══════════════════════════════════════════════════════════════════════════════
# Review browser
# ═══════════════════════════════════════════════════════════════════════════════


def _reviewer_name(r, users_by_id: dict) -> str:
    rid = getattr(r, "reviewer_id", "?")
    user = users_by_id.get(rid)
    return user.name if user else rid


def _format_star_rating(scores: dict | None) -> tuple[str, float]:
    s = scores if scores else {}
    if not s:
        return no_rating_stars(), 0.0
    avg = sum(s.values()) / len(s)
    return star_string(int(avg)), avg


def _render_review_line(r, index: int, is_selected: bool, users_by_id: dict) -> Fragment:
    prefix = "▸" if is_selected else " "
    style = "class:selected" if is_selected else ""
    name = _reviewer_name(r, users_by_id)
    stars, avg = _format_star_rating(getattr(r, "scores", None))
    text = f"{prefix} {name:<{_REVIEW_NAME_WIDTH}} {stars}  {format(avg, _RATING_PRECISION)}\n"
    return style, text


def _review_status_text(r, index: int, total: int, users_by_id: dict) -> str:
    name = _reviewer_name(r, users_by_id)
    return f" {index + 1}/{total}  ▸ {name}  │  {_REVIEW_ACTIONS_HINT}"


def _browse_reviews(db, article_id: str) -> str | None:
    reviews = get_reviews_for_article(db, article_id)
    if not reviews:
        console.print(no_reviews_msg())
        return None

    reviewer_ids = {getattr(r, "reviewer_id", None) for r in reviews} - {None}
    users_by_id = (
        {u.id: u for u in list_users_by_ids(db, reviewer_ids)} if reviewer_ids else {}
    )

    return ListBrowser(
        title="Reviews",
        items=reviews,
        render_item=lambda r, i, s: [_render_review_line(r, i, s, users_by_id)],
        status_text=lambda r, i, t: _review_status_text(r, i, t, users_by_id),
        actions=[
            BrowserAction(key="enter", handler=lambda r: getattr(r, "reviewer_id", "")),
            BrowserAction(
                key="r",
                handler=lambda r: _browser_result("reply", getattr(r, "reviewer_id", "")),
            ),
        ],
        lines_per_item=_COMPACT_CARD_LINES,
    ).run()
