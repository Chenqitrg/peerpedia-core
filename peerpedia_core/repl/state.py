# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""REPL state — theme definitions, session variables, prompt, DB helpers."""

from __future__ import annotations

from prompt_toolkit.styles import Style
from rich.console import Console
from rich.theme import Theme

from peerpedia_core.config.paths import DB_PATH, DB_URL
from peerpedia_core.storage.db import db_repl_setup

# ── Color themes ─────────────────────────────────────────────────────────

_PARCHMENT_THEME = Theme({
    "success": "#777C5C bold",    # olive
    "error": "#B84040 bold",      # brick red
    "warning": "#D4893C bold",    # amber
    "info": "#A85F3B bold",       # primary terracotta
    "accent": "#B08A57 bold",     # gold-brown
    "muted": "#6F665E dim",       # warm gray
})

_EMBER_THEME = Theme({
    "success": "#8F9A82 bold",    # sage
    "error": "#CC5544 bold",      # ember red
    "warning": "#D4A03C bold",    # golden amber
    "info": "#D18462 bold",       # primary rose
    "accent": "#B89A66 bold",     # dark gold
    "muted": "#BDB3A6 dim",       # warm gray (night)
})

_PARCHMENT_STYLE = Style.from_dict({
    "prompt": "#A85F3B bold",
    "separator": "#D8CBBB",
})

_EMBER_STYLE = Style.from_dict({
    "prompt": "#D18462 bold",
    "separator": "#454037",
})

theme = _PARCHMENT_THEME
repl_style = _PARCHMENT_STYLE
console = Console(theme=theme)

# ── Session state ────────────────────────────────────────────────────────

_repl_user: str | None = None
_repl_article_id: str | None = None
_repl_article_title: str = ""
_repl_article_commit: str = ""
_repl_theme: str = "parchment"
_repl_compact: bool = False
_repl_unicode: bool = True      # Unicode pseudo-font typography toggle
_repl_completion_words: list = []  # dynamic completion: article IDs, @names
_repl_db = None


def _ensure_db():
    global _repl_db
    if _repl_db is None:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        _repl_engine, _repl_db = db_repl_setup(DB_URL)
    return _repl_db


# Cache for notification count — only refresh every 30s, not on every
# keystroke (prompt_toolkit calls _prompt_text on each render cycle).
_notif_cache: tuple[float, int] = (0.0, 0)

def _prompt_text():
    user = _repl_user or "guest"
    # Notification badge — cached for 30s to avoid DB query on every keystroke.
    try:
        import time
        now = time.time()
        global _notif_cache
        if now - _notif_cache[0] > 30.0:
            from peerpedia_core.cli.helpers import _read_session
            from peerpedia_core.commands import count_unread_notifications
            db = _ensure_db()
            sid = _read_session()
            if sid:
                unread = count_unread_notifications(db, sid["user_id"])
                _notif_cache = (now, unread)
            else:
                _notif_cache = (now, 0)
        badge = f" ({_notif_cache[1]})" if _notif_cache[1] > 0 else ""
    except Exception:
        badge = ""
    parts = [("class:prompt", f"{user}{badge}")]
    if _repl_article_id:
        label = _repl_article_title or _repl_article_id[:8]
        parts.append(("class:separator", f" ▸ {label}"))
        if _repl_article_commit:
            parts.append(("class:separator", f" @{_repl_article_commit[:7]}"))
    parts.append(("class:separator", "> "))
    return parts


def _refresh_completions():
    """Rebuild dynamic completion word list from DB (article IDs + @names)."""
    global _repl_completion_words
    try:
        db = _ensure_db()
        words = []
        # Article title words and ID prefixes
        from peerpedia_core.commands import list_articles
        for a in list_articles(db, limit=50):
            if a.id:
                words.append(a.id[:8])
            if a.title:
                for w in a.title.split():
                    if len(w) > 2:
                        words.append(w)
        # @usernames
        from peerpedia_core.commands import list_users
        for u in list_users(db):
            if u.name:
                words.append(f"@{u.name}")
                words.append(u.id[:8])
        _repl_completion_words = sorted(set(words))
    except Exception:
        _repl_completion_words = []


def _get_session_user_id() -> str:
    try:
        from peerpedia_core.cli.helpers import _read_session
        s = _read_session()
        return s["user_id"] if s else ""
    except Exception:
        return ""


# Lazy imports to avoid circular dependency (cli/__init__.py imports repl.run).
_build_parser = None
_stars = None


def _get_parser():
    global _build_parser
    if _build_parser is None:
        from peerpedia_core.cli import build_parser as bp
        _build_parser = bp
    return _build_parser()


def _get_stars():
    global _stars
    if _stars is None:
        from peerpedia_core.cli.display import _stars as s
        _stars = s
    return _stars
