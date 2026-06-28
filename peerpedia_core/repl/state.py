# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""REPL state — theme definitions, session variables, prompt.

Architecture: ``repl/`` only imports from ``cli/``.  All data access goes
through ``cli.helpers`` — no direct ``commands/`` or ``storage/`` imports.
No circular dependency: ``cli/`` never imports from ``repl/``.
"""

from __future__ import annotations

import time

from prompt_toolkit.styles import Style
from rich.console import Console
from rich.theme import Theme

from peerpedia_core.app.context import read_session
from peerpedia_core.config.paths import DB_PATH, DB_URL
from peerpedia_core.core import (
    count_unread_notifications, db_repl_setup, list_articles, list_users,
)
from peerpedia_core.types import short_id

# ── REPL persistent DB session ───────────────────────────────────────────

_repl_engine = None
_repl_db = None


def ensure_db():
    """Return a persistent database session for the REPL."""
    global _repl_engine, _repl_db
    if _repl_db is None:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        _repl_engine, _repl_db = db_repl_setup(DB_URL)
    return _repl_db


def close_db():
    """Close the persistent REPL database session."""
    global _repl_db, _repl_engine
    if _repl_db is not None:
        _repl_db.close()
        _repl_db = None
    if _repl_engine is not None:
        _repl_engine.dispose()
        _repl_engine = None


# Backward-compat aliases
_ensure_db = ensure_db
_close_db = close_db
_read_session = read_session

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

# Module-level globals — mutated via ``_st.<field>`` by meta.py / dispatch.py.

# ── Session state ────────────────────────────────────────────────────────

_repl_user: str | None = None
_repl_article_id: str | None = None
_repl_article_title: str = ""
_repl_article_commit: str = ""
_repl_theme: str = "parchment"
_repl_compact: bool = False
_repl_completion_words: list = []  # dynamic completion: article IDs, @names

# Cache for notification count — only refresh every 30s, not on every
# keystroke (prompt_toolkit calls _prompt_text on each render cycle).
_notif_cache: tuple[float, int] = (0.0, 0)
# One-shot warning flag — _prompt_text is called on every keystroke,
# so we only warn once per session when notification lookup fails.
_notif_warned: bool = False

# Cached parser — built once on first use.
_build_parser = None


def _get_parser():
    global _build_parser
    if _build_parser is None:
        from peerpedia_core.cli import build_parser as bp
        _build_parser = bp
    return _build_parser()


def _prompt_text():
    """Build the REPL prompt line with user badge, article context, notifications."""
    user = _repl_user or "guest"
    # NotificationStorage badge — cached for 30s to avoid DB query on every keystroke.
    try:
        now = time.time()
        global _notif_cache
        if now - _notif_cache[0] > 30.0:
            db = _ensure_db()
            sid = _read_session()
            if sid:
                unread = count_unread_notifications(db, sid["user_id"])
                _notif_cache = (now, unread)
            else:
                _notif_cache = (now, 0)
        badge = f" ({_notif_cache[1]})" if _notif_cache[1] > 0 else ""
    except Exception:
        global _notif_warned
        if not _notif_warned:
            _notif_warned = True
            import logging
            logging.getLogger(__name__).warning(
                "Failed to read notification count", exc_info=True
            )
        badge = ""
    parts = [("class:prompt", f"{user}{badge}")]
    if _repl_article_id:
        label = _repl_article_title or short_id(_repl_article_id)
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
        # ArticleMetaStorage title words and ID prefixes
        for a in list_articles(db, limit=50):
            if a.id:
                words.append(short_id(a.id))
            if a.title:
                for w in a.title.split():
                    if len(w) > 2:
                        words.append(w)
        # @usernames
        for u in list_users(db):
            if u.name:
                words.append(f"@{u.name}")
                words.append(short_id(u.id))
        _repl_completion_words = sorted(set(words))
    except Exception:
        import logging
        logging.getLogger(__name__).warning(
            "Failed to refresh REPL completions", exc_info=True
        )


# _get_session_user_id is in cli.helpers — import from there.
