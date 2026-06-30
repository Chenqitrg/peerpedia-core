# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""REPL state — theme definitions, session variables, prompt.

Architecture: ``repl/`` only imports from ``app/`` and its own modules.
No circular dependency: ``cli/`` never imports from ``repl/``.
"""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager

from prompt_toolkit.styles import Style
from rich.console import Console
from rich.theme import Theme

logger = logging.getLogger(__name__)

from peerpedia_core.app.context import read_session
from peerpedia_core.config.paths import DB_PATH, DB_URL
from peerpedia_core.core import (
    count_unread_notifications, db_repl_dispose, db_repl_init,
    db_repl_new_session, list_articles, list_users,
)

# ── REPL database sessions (per-command unit of work) ────────────────────


def new_session():
    """Return a **new** database session.  Engine is cached; session is not.

    Each command gets a fresh session, avoiding stale identity maps and
    cross-command transaction pollution.  The caller owns the session
    lifecycle — it must ``.close()`` when done.
    """
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db_repl_init(DB_URL)
    return db_repl_new_session(DB_URL)


@contextmanager
def session_scope():
    """Context manager: fresh session with auto commit/rollback/close.

    Usage::

        with session_scope() as db:
            result = do_work(db)
    """
    db = new_session()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def close_db():
    """Dispose the cached engine (final cleanup on REPL exit)."""
    db_repl_dispose()


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


def set_article_context(article_id: str | None, title: str = "", commit: str = "") -> None:
    """Set the current article context for prompt display.  Public setter."""
    global _repl_article_id, _repl_article_title, _repl_article_commit
    _repl_article_id = article_id
    _repl_article_title = title
    _repl_article_commit = commit


def set_user(name: str) -> None:
    """Set the current REPL user name."""
    global _repl_user
    _repl_user = name


def set_compact(compact: bool) -> None:
    """Toggle compact output mode."""
    global _repl_compact
    _repl_compact = compact


def set_theme(mode: str) -> str:
    """Switch to *mode* theme ('light'/'dark').  Returns the theme name."""
    global theme, repl_style, _repl_theme
    if mode in ("dark", "ember", "night"):
        theme = _EMBER_THEME
        repl_style = _EMBER_STYLE
        _repl_theme = "ember"
    elif mode in ("light", "parchment", "day"):
        theme = _PARCHMENT_THEME
        repl_style = _PARCHMENT_STYLE
        _repl_theme = "parchment"
    else:
        return ""  # unknown mode — caller handles
    console.push_theme(theme)
    return _repl_theme

# Cache for notification count — only refresh every 30s, not on every
# keystroke (prompt_toolkit calls _prompt_text on each render cycle).
_notif_cache: tuple[float, int] = (0.0, 0)
# One-shot warning flag — _prompt_text is called on every keystroke,
# so we only warn once per session when notification lookup fails.
_notif_warned: bool = False

def _get_notification_badge() -> str:
    """Return a notification count badge string, cached for 30s."""
    try:
        now = time.time()
        global _notif_cache
        if now - _notif_cache[0] > 30.0:
            db = new_session()
            try:
                sid = _read_session()
                if sid:
                    unread = count_unread_notifications(db, sid["user_id"])
                    _notif_cache = (now, unread)
                else:
                    _notif_cache = (now, 0)
            finally:
                db.close()
        return f" ({_notif_cache[1]})" if _notif_cache[1] > 0 else ""
    except Exception:
        global _notif_warned
        if not _notif_warned:
            _notif_warned = True
            logger.warning("Failed to read notification count", exc_info=True)
        return ""


def _prompt_text():
    """Build the REPL prompt line with user badge, article context, notifications."""
    parts = [("class:prompt", f"{_repl_user or 'guest'}{_get_notification_badge()}")]
    if _repl_article_id:
        label = _repl_article_title or _repl_article_id
        parts.append(("class:separator", f" ▸ {label}"))
        if _repl_article_commit:
            parts.append(("class:separator", f" @{_repl_article_commit[:7]}"))
    parts.append(("class:separator", "> "))
    return parts


def _refresh_completions():
    """Rebuild dynamic completion word list from DB (article IDs + @names)."""
    global _repl_completion_words
    db = new_session()
    try:
        words = []
        for a in list_articles(db, limit=50):
            if a.id:
                words.append(a.id)
            if a.title:
                for w in a.title.split():
                    if len(w) > 2:
                        words.append(w)
        for u in list_users(db):
            if u.name:
                words.append(f"@{u.name}")
                words.append(u.id)
        _repl_completion_words = sorted(set(words))
    except Exception:
        logger.warning("Failed to refresh REPL completions", exc_info=True)
    finally:
        db.close()


# _get_session_user_id is in browse.py — use _get_session_user_id() from there.
