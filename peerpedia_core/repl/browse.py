# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""REPL interactive browsing — full-screen article and user selection views."""

from __future__ import annotations

from prompt_toolkit.application import Application
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import HSplit, Layout, Window
from prompt_toolkit.layout.controls import FormattedTextControl

import peerpedia_core.repl.state as _st
from peerpedia_core.cli.display import _score_lines
from peerpedia_core.app.context import read_session
from peerpedia_core.core import (
    get_head_hash as _get_article_head_hash,
    get_reviews_for_article, get_top_users_by_followers,
    get_user, get_users_by_ids, list_articles,
)

def _get_session_user_id() -> str:
    """Return the current user ID from session, or '' if not logged in."""
    s = read_session()
    return s["user_id"] if s else ""
from peerpedia_core.types import short_id

from peerpedia_core.repl.state import (
    console, repl_style,
)


def _build_browser(title: str, render_fn, status_fn, kb,
                   *, selected: list[int], lines_per_item: int = 1):
    """Build and run a full-screen prompt_toolkit Application.

    Renders ALL items in a ``FormattedTextControl`` — the ``Window``
    handles clipping and scrolls natively when content overflows.
    ``mouse_support=True`` on the ``Application`` means mouse wheel
    scrolling works without any custom handler.

    *lines_per_item* maps ``selected[0]`` (card index) to the correct
    scroll line offset: ``1`` for single-line cards, ``>1`` for multi-line.
    """
    header = Window(height=1, content=FormattedTextControl(
        [("class:prompt", f"▔▔▔ {title} " + "▔" * 50)]
    ))

    list_view = Window(
        content=FormattedTextControl(
            lambda: render_fn(),     # renders ALL items
        ),
        always_hide_cursor=True,
        get_vertical_scroll=lambda win: selected[0] * lines_per_item,
    )

    status_bar = Window(height=1, content=FormattedTextControl(status_fn),
                        style="class:status-bar")
    root = HSplit([header, list_view, Window(height=1), status_bar])
    app = Application(
        layout=Layout(root), key_bindings=kb,
        full_screen=True, mouse_support=True, style=repl_style,
    )
    return app.run()


# ── Shared key-binding helpers ──────────────────────────────────────────────


def _add_browser_nav_keys(kb: KeyBindings, selected: list[int], n: int) -> None:
    """Register ↑/↓ navigation and q/Escape exit on *kb*.

    ``selected[0]`` is mutated in-place so callers that wrap it in a
    closure (e.g. ``selected = [0]``) see live updates after every keypress.
    """
    @kb.add("up")
    def _(event):
        selected[0] = (selected[0] - 1) % n

    @kb.add("down")
    def _(event):
        selected[0] = (selected[0] + 1) % n

    @kb.add("q")
    @kb.add("escape")
    def _(event):
        event.app.exit(result=None)


def _set_article_context(article):
    """Cache article context for prompt display."""
    _st._repl_article_id = article.id
    _st._repl_article_title = article.title
    _st._repl_article_commit = _get_article_head_hash(article.id)


def _browse_articles(db, viewer_id: str | None = None) -> str | None:
    """Full-screen article browser.  Returns article ID or 'action:id'.  """
    articles = list_articles(db)
    if not articles:
        console.print("[muted]No articles.[/]")
        return None

    n = len(articles)
    selected = [0]

    def _formatted_score(v: int) -> str:
        """'★★★☆☆' for a single dimension (used in compact mode)."""
        return f"{'★'*v}{'☆'*(5-v)}"

    def _render():
        lines = []
        for i, a in enumerate(articles):
            prefix = "▸" if i == selected[0] else " "
            style = "class:selected" if i == selected[0] else ""
            status = a.status[:4].upper() if a.status else "?"
            star_lines = _score_lines(a.score)
            if _st._repl_compact:
                # One-line card: id + title-truncated + status + single-star
                single = _formatted_score(int(a.score.get('originality', 0))) if a.score else "—"
                lines.append((style, f"{prefix} {short_id(a.id)}  {a.title[:45]:<45} {status:<8} {single}\n"))
            else:
                # Full card: header line + one line per score dimension
                lines.append((style, f"{prefix} {short_id(a.id)}  {a.title}  {status}\n"))
                for sl in star_lines:
                    lines.append((style, f"          {sl}\n"))
                # Blank separator between cards
                lines.append(("", "\n"))
        return lines

    def _status_text():
        a = articles[selected[0]]
        compact_mark = "[⊞]" if _st._repl_compact else ""
        actions = "Enter:view p:publish e:edit r:review b:bookmark q:back  ↑↓/wheel:scroll"
        return f" {compact_mark} {selected[0]+1}/{n}  ▸ {a.title[:45]}  │  {actions}"

    browse_kb = KeyBindings()

    _add_browser_nav_keys(browse_kb, selected, n)

    @browse_kb.add("enter")
    def _(event):
        _set_article_context(articles[selected[0]])
        event.app.exit(result=articles[selected[0]].id)

    @browse_kb.add("p")
    def _(event):
        event.app.exit(result=f"publish:{articles[selected[0]].id}")

    @browse_kb.add("e")
    def _(event):
        event.app.exit(result=f"edit:{articles[selected[0]].id}")

    @browse_kb.add("r")
    def _(event):
        event.app.exit(result=f"review:{articles[selected[0]].id}")

    @browse_kb.add("b")
    def _(event):
        event.app.exit(result=f"bookmark:{articles[selected[0]].id}")

    article_lines = 1 if _st._repl_compact else 7  # title + 5 scores + blank
    return _build_browser("Articles", _render, _status_text, browse_kb,
                          selected=selected, lines_per_item=article_lines)


def _browse_school(db) -> str | None:
    """Interactive user leaderboard.  Returns 'follow:<id>' or None."""
    users = get_top_users_by_followers(db, limit=20)
    if not users:
        console.print("[muted]No users found.[/]")
        return None

    n = len(users)
    selected = [0]
    current_user_id = _get_session_user_id()

    def _render():
        lines = []
        for i, u in enumerate(users):
            prefix = "▸" if i == selected[0] else " "
            style_class = "class:selected" if i == selected[0] else ""
            fc = u.follower_count if hasattr(u, 'follower_count') else 0
            is_self = " (you)" if u.id == current_user_id else ""
            lines.append((style_class, f"{prefix} {i+1:>3}. {u.name:<25} {fc} followers{is_self}\n"))
        return lines

    def _status_text():
        u = users[selected[0]]
        if u.id == current_user_id:
            return f" {selected[0]+1}/{n}  ▸ {u.name} (you)  │  q: back  ↑↓/wheel:scroll"
        return f" {selected[0]+1}/{n}  ▸ {u.name}  │  Enter: follow  q: back  ↑↓/wheel:scroll"

    kb = KeyBindings()

    _add_browser_nav_keys(kb, selected, n)

    @kb.add("enter")
    def _(event):
        u = users[selected[0]]
        if u.id != current_user_id:
            event.app.exit(result=f"follow:{u.id}")

    return _build_browser("School — Top Users", _render, _status_text, kb,
                          selected=selected, lines_per_item=1)


def _browse_reviews(db, article_id: str) -> str | None:
    """Interactive review viewer.  Returns reviewer ID or 'reply:<id>'."""
    reviews = get_reviews_for_article(db, article_id)
    if not reviews:
        console.print("[muted]No reviews yet.[/]")
        return None

    reviewer_ids = {r.reviewer_id for r in reviews if hasattr(r, 'reviewer_id')}
    users_by_id = {u.id: u for u in get_users_by_ids(db, reviewer_ids)} if reviewer_ids else {}

    n = len(reviews)
    selected = [0]

    def _render():
        lines = []
        for i, r in enumerate(reviews):
            prefix = "▸" if i == selected[0] else " "
            style_class = "class:selected" if i == selected[0] else ""
            rid = r.reviewer_id if hasattr(r, 'reviewer_id') else "?"
            user = users_by_id.get(rid)
            name = user.name if user else short_id(rid)
            s = r.scores if hasattr(r, 'scores') and r.scores else {}
            avg = sum(s.values()) / len(s) if s else 0
            stars = "★" * int(avg) + "☆" * (5 - int(avg)) if avg else "  —  "
            lines.append((style_class, f"{prefix} {name:<20} {stars}  {avg:.1f}\n"))
        return lines

    def _status_text():
        r = reviews[selected[0]]
        rid = r.reviewer_id if hasattr(r, 'reviewer_id') else "?"
        user = users_by_id.get(rid)
        name = user.name if user else short_id(rid)
        return f" {selected[0]+1}/{n}  ▸ {name}  │  Enter: view  r: reply  q: back  ↑↓/wheel:scroll"

    kb = KeyBindings()

    _add_browser_nav_keys(kb, selected, n)

    @kb.add("enter")
    def _(event):
        r = reviews[selected[0]]
        rid = r.reviewer_id if hasattr(r, 'reviewer_id') else ""
        event.app.exit(result=rid)

    @kb.add("r")
    def _(event):
        r = reviews[selected[0]]
        rid = r.reviewer_id if hasattr(r, 'reviewer_id') else ""
        event.app.exit(result=f"reply:{rid}")

    return _build_browser("Reviews", _render, _status_text, kb,
                          selected=selected, lines_per_item=1)
