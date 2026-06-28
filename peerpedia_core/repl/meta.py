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
from peerpedia_core.repl.state import ensure_db as _ensure_db
from peerpedia_core.types import short_id
from peerpedia_core.repl.state import (
    _EMBER_THEME, _EMBER_STYLE, _PARCHMENT_THEME, _PARCHMENT_STYLE,
    console,
)


def _meta_user(name):
    db = _ensure_db()
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
                t.add_row(str(i), short_id(user.id), user.affiliation or "—")
            console.print(t)
            console.print(f"[muted]Use [accent]:user <id prefix>[/] to pick.[/]")
            return
    if u:
        _st._repl_user = name
        console.print(f"[success]✓[/] UserStorage set to [accent]{u.name}[/] [muted]({short_id(u.id)})[/]")
    else:
        console.print(f"[error]✗[/] UserStorage '{name}' not found. [muted]register --name {name}[/] to create.[/]")


def _meta_article(ref: str):
    db = _ensure_db()
    if not ref:
        _st._repl_article_id = None
        _st._repl_article_title = ""
        _st._repl_article_commit = ""
        console.print("[muted]Article context cleared.[/]")
        return
    # FIXME: switch to list_articles when search_articles is deleted.
    # Use search_articles — pure list, no _die. REPL handles results
    # interactively (show candidates, let user pick).
    # FIXME: REPL should use list_articles(db, id_prefix=ref) or list_articles(db, search_query=ref).
    candidates = search_articles(db, ref)
    if len(candidates) == 1:
        article = candidates[0]
    elif len(candidates) > 1:
        console.print(f"[warning]{len(candidates)} articles match '{ref}':[/]")
        for a in candidates[:20]:
            console.print(f"  {short_id(a.id)}  {a.title}")
        return
    else:
        console.print(f"[error]✗[/] ArticleMetaStorage '{ref}' not found.")
        return
    _st._repl_article_id = article.id
    _st._repl_article_title = article.title
    _st._repl_article_commit = _get_article_head_hash(article.id)
    commit_str = f" @{_st._repl_article_commit[:7]}" if _st._repl_article_commit else ""
    # Sedimentation countdown
    sink_info = ""
    if article.status == "sedimentation" and article.sink_start:
        now = datetime.now(timezone.utc)
        start = article.sink_start.replace(tzinfo=timezone.utc) if article.sink_start.tzinfo is None else article.sink_start
        elapsed = (now - start).days
        total = article.sink_duration_days or 7
        remaining = max(0, total - elapsed)
        bar_filled = min(total, max(0, elapsed))
        bar = "█" * bar_filled + "░" * (total - bar_filled)
        sink_info = f"  [{_st.theme.styles['muted']}]{bar}[/] {remaining}d left"
    console.print(f"[success]▸[/] {article.title} [muted]({short_id(article.id)}{commit_str})[/]{sink_info}")


def _meta_theme(mode: str):
    mode = mode.strip().lower() or "parchment"
    if mode in ("dark", "ember", "night"):
        _st.theme = _EMBER_THEME
        _st.repl_style = _EMBER_STYLE
        _st._repl_theme = "ember"
        console.push_theme(_st.theme)
        console.print("🌙  Ember (dark) theme.")
    elif mode in ("light", "parchment", "day"):
        _st.theme = _PARCHMENT_THEME
        _st.repl_style = _PARCHMENT_STYLE
        _st._repl_theme = "parchment"
        console.push_theme(_st.theme)
        console.print("☀   Parchment (light) theme.")
    else:
        console.print(f"[warning]Unknown theme '{mode}'. Use [accent]light[/] or [accent]dark[/].[/]")


def _show_inbox():
    db = _ensure_db()
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
        ts_raw = n.get("created_at", "")
        ts = ts_raw[:16].replace("T", " ") if ts_raw else ""
        marker = "[bold]●[/] " if not n.get("read") else "  "
        t.add_row(ts, f"{marker}{n.get('message', '')}")
    console.print(t)
