# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""REPL meta-command handlers — pure logic, no dispatch dependency.

Each handler is a self-contained function.  They read/write REPL session
state via ``_st.<field>`` (importing the state module, never ``from…import``
for mutable fields).  Never call ``_dispatch`` — that keeps the dependency
graph one-way: ``dispatch.py`` → ``meta.py``.
"""

from __future__ import annotations

import shlex
from datetime import datetime, timezone

from rich.table import Table

import peerpedia_core.repl.state as _st
from peerpedia_core.app.context import read_session as _read_session
from peerpedia_core.core import (
    get_head_hash as _get_article_head_hash,
    get_notifications_for_user, get_user, list_users_by_name,
    list_articles, search_articles,
)
from peerpedia_core.repl.state import new_session
from peerpedia_core.repl.state import console


def _meta_user(name):
    db = new_session()
    try:
        u = get_user(db, name)
        if u is None:
            users = list_users_by_name(db, name)
            if len(users) == 1:
                u = users[0]
            elif len(users) > 1:
                t = Table(title=f"Multiple users matching '{name}'", border_style="muted")
                t.add_column("#", style="muted", width=3)
                t.add_column("ID", style="accent", width=10)
                t.add_column("Affiliation", style="muted")
                for i, user in enumerate(users, 1):
                    t.add_row(str(i), user.id, user.affiliation or "—")
                console.print(t)
                console.print(f"[muted]Use [accent]:user <id prefix>[/] to pick.[/]")
                return
        if u:
            _st.set_user(name)
            console.print(f"[success]✓[/] UserStorage set to [accent]{u.name}[/] [muted]({u.id})[/]")
        else:
            console.print(f"[error]✗[/] UserStorage '{name}' not found. [muted]register --name {name}[/] to create.[/]")
    finally:
        db.close()


def _format_sink_bar(article) -> str:
    """Sedimentation progress bar, e.g. '  ████░░ 4d left'.  Empty if not sinking."""
    if article.status != "sedimentation" or not article.sink_start:
        return ""
    now = datetime.now(timezone.utc)
    start = article.sink_start.replace(tzinfo=timezone.utc) if article.sink_start.tzinfo is None else article.sink_start
    elapsed = (now - start).days
    total = article.sink_duration_days or 7
    remaining = max(0, total - elapsed)
    bar_filled = min(total, max(0, elapsed))
    bar = "█" * bar_filled + "░" * (total - bar_filled)
    return f"  [{_st.theme.styles['muted']}]{bar}[/] {remaining}d left"


def _meta_article(ref: str):
    db = new_session()
    try:
        if not ref:
            _st.set_article_context(None)
            console.print("[muted]Article context cleared.[/]")
            return
        candidates = search_articles(db, ref)
        if len(candidates) == 1:
            article = candidates[0]
        elif len(candidates) > 1:
            console.print(f"[warning]{len(candidates)} articles match '{ref}':[/]")
            for a in candidates[:20]:
                console.print(f"  {a.id}  {a.title}")
            return
        else:
            console.print(f"[error]✗[/] ArticleMetaStorage '{ref}' not found.")
            return
        _st.set_article_context(article.id, article.title, _get_article_head_hash(article.id))
        commit_str = f" @{_st._repl_article_commit[:7]}" if _st._repl_article_commit else ""
        console.print(
            f"[success]▸[/] {article.title} "
            f"[muted]({article.id}{commit_str})[/]"
            f"{_format_sink_bar(article)}"
        )
    finally:
        db.close()


def _meta_theme(mode: str):
    mode = mode.strip().lower() or "parchment"
    theme_name = _st.set_theme(mode)
    if theme_name == "ember":
        console.print("🌙  Ember (dark) theme.")
    elif theme_name == "parchment":
        console.print("☀   Parchment (light) theme.")
    else:
        console.print(f"[warning]Unknown theme '{mode}'. Use [accent]light[/] or [accent]dark[/].[/]")


def _format_notification_time(ts_raw: str) -> str:
    """'2026-01-15T09:30:00' → '2026-01-15 09:30'."""
    return ts_raw[:16].replace("T", " ") if ts_raw else ""


def _unread_marker(read: bool) -> str:
    """● for unread, blank for read."""
    return "[bold]●[/] " if not read else "  "


def _show_inbox():
    db = new_session()
    try:
        session_data = _read_session()
        if not session_data:
            console.print("[muted]Not logged in.[/]")
            return
        notifications = get_notifications_for_user(db, session_data["user_id"])
        if not notifications:
            console.print("[muted]No notifications.[/]")
            return
        t = Table(title="Notifications", border_style="muted")
        t.add_column("Time", style="muted", width=16)
        t.add_column("Event", style="accent")
        for n in notifications[:20]:
            t.add_row(
                _format_notification_time(n.get("created_at", "")),
                f"{_unread_marker(n.get('read', False))}{n.get('message', '')}",
            )
        console.print(t)
    finally:
        db.close()
