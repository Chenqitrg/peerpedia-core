# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""REPL interactive browsing — full-screen article and user selection views."""

from __future__ import annotations

from prompt_toolkit.application import Application
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import HSplit, Layout, Window

from peerpedia_core.repl.typography import title as _T_raw, status as _St_raw

def _T(s):
    import peerpedia_core.repl.state as _st
    return _T_raw(s) if _st._repl_unicode else s

def _St(s):
    import peerpedia_core.repl.state as _st
    return _St_raw(s) if _st._repl_unicode else s
from prompt_toolkit.layout.controls import FormattedTextControl

from peerpedia_core.repl.state import (
    _ensure_db, _get_stars, _get_session_user_id,
    _repl_compact, _repl_article_id, _repl_article_title, _repl_article_commit,
    console, repl_style,
)


def _set_article_context(article):
    """Cache article context for prompt display."""
    global _repl_article_id, _repl_article_title, _repl_article_commit
    _repl_article_id = article.id
    _repl_article_title = article.title
    try:
        from peerpedia_core.storage.git_backend import DEFAULT_ARTICLES_DIR, get_head_hash
        rp = DEFAULT_ARTICLES_DIR / article.id
        if (rp / ".git").is_dir():
            _repl_article_commit = get_head_hash(rp)
        else:
            _repl_article_commit = ""
    except Exception:
        _repl_article_commit = ""


def _browse_articles(db, viewer_id: str | None = None) -> str | None:
    """Launch a full-screen article browser.  Returns the selected article ID
    or 'action:id' string, or None if cancelled."""
    from peerpedia_core.commands import list_articles as _la

    articles = _la(db)
    if not articles:
        console.print("[muted]No articles.[/]")
        return None

    n = len(articles)
    selected = [0]

    def _render():
        lines = []
        for i, a in enumerate(articles):
            prefix = "▸" if i == selected[0] else " "
            style_class = "class:selected" if i == selected[0] else ""
            if _repl_compact:
                star_val = f" {a.score['originality']:.0f}" if a.score and 'originality' in a.score else "—"
                status_badge = _St(a.status[:4].upper()) if a.status else a.status
                lines.append((style_class, f"{prefix} {a.id[:8]}  {_T(a.title[:45]):<45} {status_badge:<15} {star_val}\n"))
            else:
                star = _get_stars()(a.score) if a.score else "[muted]  —  [/]"
                status_badge = _St(a.status[:4].upper()) if a.status else a.status
                lines.append((style_class, f"{prefix} {a.id[:8]}  {_T(a.title):<40} {status_badge:<15} {star}\n"))
        return lines

    def _status_text():
        a = articles[selected[0]]
        compact_mark = "[⊞]" if _repl_compact else ""
        actions = "Enter:view p:publish e:edit r:review b:bookmark q:back"
        return f" {compact_mark} {selected[0]+1}/{n}  ▸ {a.title[:45]}  │  {actions}"

    browse_kb = KeyBindings()

    @browse_kb.add("up")
    def _(event):
        selected[0] = (selected[0] - 1) % n

    @browse_kb.add("down")
    def _(event):
        selected[0] = (selected[0] + 1) % n

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

    @browse_kb.add("q")
    @browse_kb.add("escape")
    def _(event):
        event.app.exit(result=None)

    header = Window(height=1, content=FormattedTextControl(
        [("class:prompt", "▔▔▔ Articles ▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔")]
    ))
    list_view = Window(content=FormattedTextControl(_render), always_hide_cursor=True)
    status_bar = Window(height=1, content=FormattedTextControl(_status_text), style="class:status-bar")
    root = HSplit([header, list_view, Window(height=1), status_bar])

    app = Application(
        layout=Layout(root), key_bindings=browse_kb,
        full_screen=True, mouse_support=True, style=repl_style,
    )
    return app.run()


def _browse_school(db) -> str | None:
    """Launch an interactive user leaderboard.  Returns 'follow:<id>' or None."""
    from peerpedia_core.commands import get_top_users_by_followers
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
            return f" {selected[0]+1}/{n}  ▸ {u.name} (you)  │  q: back"
        return f" {selected[0]+1}/{n}  ▸ {u.name}  │  Enter: follow  q: back"

    kb = KeyBindings()

    @kb.add("up")
    def _(event):
        selected[0] = (selected[0] - 1) % n

    @kb.add("down")
    def _(event):
        selected[0] = (selected[0] + 1) % n

    @kb.add("enter")
    def _(event):
        u = users[selected[0]]
        if u.id != current_user_id:
            event.app.exit(result=f"follow:{u.id}")

    @kb.add("q")
    @kb.add("escape")
    def _(event):
        event.app.exit(result=None)

    header = Window(height=1, content=FormattedTextControl(
        [("class:prompt", "▔▔▔ School — Top Users ▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔")]
    ))
    list_view = Window(content=FormattedTextControl(_render), always_hide_cursor=True)
    status_bar = Window(height=1, content=FormattedTextControl(_status_text), style="class:status-bar")
    root = HSplit([header, list_view, Window(height=1), status_bar])

    app = Application(
        layout=Layout(root), key_bindings=kb,
        full_screen=True, mouse_support=True, style=repl_style,
    )
    return app.run()


def _browse_reviews(db, article_id: str) -> str | None:
    """Launch an interactive review viewer. Returns the selected reviewer ID
    or 'reply:<id>' for reply action, or None if cancelled."""
    from peerpedia_core.commands import get_reviews_for_article, get_user, get_users_by_ids

    reviews = get_reviews_for_article(db, article_id)
    if not reviews:
        console.print("[muted]No reviews yet.[/]")
        return None

    # Batch-load reviewer names
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
            name = user.name if user else rid[:8]
            s = r.scores if hasattr(r, 'scores') and r.scores else {}
            avg = sum(s.values()) / len(s) if s else 0
            stars = "★" * int(avg) + "☆" * (5 - int(avg)) if avg else "  —  "
            lines.append((style_class, f"{prefix} {name:<20} {stars}  {avg:.1f}\n"))
        return lines

    def _status_text():
        r = reviews[selected[0]]
        rid = r.reviewer_id if hasattr(r, 'reviewer_id') else "?"
        user = users_by_id.get(rid)
        name = user.name if user else rid[:8]
        return f" {selected[0]+1}/{n}  ▸ {name}  │  Enter: view  r: reply  q: back"

    kb = KeyBindings()

    @kb.add("up")
    def _(event):
        selected[0] = (selected[0] - 1) % n

    @kb.add("down")
    def _(event):
        selected[0] = (selected[0] + 1) % n

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

    @kb.add("q")
    @kb.add("escape")
    def _(event):
        event.app.exit(result=None)

    header = Window(height=1, content=FormattedTextControl(
        [("class:prompt", "▔▔▔ Reviews ▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔")]
    ))
    list_view = Window(content=FormattedTextControl(_render), always_hide_cursor=True)
    status_bar = Window(height=1, content=FormattedTextControl(_status_text), style="class:status-bar")
    root = HSplit([header, list_view, Window(height=1), status_bar])

    app = Application(
        layout=Layout(root), key_bindings=kb,
        full_screen=True, mouse_support=True, style=repl_style,
    )
    return app.run()
