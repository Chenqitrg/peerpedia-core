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
from dataclasses import dataclass, field

from prompt_toolkit.styles import Style
from rich.console import Console
from rich.theme import Theme

logger = logging.getLogger(__name__)

from peerpedia_core.app.context import read_session
from peerpedia_core.config.paths import DB_PATH, DB_URL
from peerpedia_core.core import (
    count_unread_notifications, db_repl_dispose, db_repl_init,
    db_repl_new_session, list_articles, list_active_users,
)

# ═══════════════════════════════════════════════════════════════════════════════
# REPL database sessions (per-command unit of work)
# ═══════════════════════════════════════════════════════════════════════════════


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


# ═══════════════════════════════════════════════════════════════════════════════
# Color themes
# ═══════════════════════════════════════════════════════════════════════════════

_PARCHMENT_THEME = Theme({
    "success": "#777C5C bold",
    "error": "#B84040 bold",
    "warning": "#D4893C bold",
    "info": "#A85F3B bold",
    "accent": "#B08A57 bold",
    "muted": "#6F665E dim",
})

_EMBER_THEME = Theme({
    "success": "#8F9A82 bold",
    "error": "#CC5544 bold",
    "warning": "#D4A03C bold",
    "info": "#D18462 bold",
    "accent": "#B89A66 bold",
    "muted": "#BDB3A6 dim",
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


# ═══════════════════════════════════════════════════════════════════════════════
# Session state — a single object instead of scattered module globals
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class ReplSession:
    """All mutable REPL state in one place."""

    compact: bool = False
    completion_words: list[str] = field(default_factory=list)
    theme_name: str = "parchment"


session = ReplSession()


def set_compact(compact: bool) -> None:
    session.compact = compact


def set_theme(mode: str) -> str:
    """Switch to *mode* theme ('light'/'dark').  Returns the theme name."""
    global theme, repl_style
    if mode in ("dark", "ember", "night"):
        theme = _EMBER_THEME
        repl_style = _EMBER_STYLE
        session.theme_name = "ember"
    elif mode in ("light", "parchment", "day"):
        theme = _PARCHMENT_THEME
        repl_style = _PARCHMENT_STYLE
        session.theme_name = "parchment"
    else:
        return ""
    console.push_theme(theme)
    return session.theme_name


# ═══════════════════════════════════════════════════════════════════════════════
# Notification badge (cached for 30s — called on every keystroke)
# ═══════════════════════════════════════════════════════════════════════════════

_NOTIF_CACHE_TTL = 30.0
_notif_cache: tuple[float, int] = (0.0, 0)
_notif_warned: bool = False


def _refresh_notif_cache() -> None:
    """Refresh the notification count cache if stale."""
    now = time.time()
    global _notif_cache
    if now - _notif_cache[0] <= _NOTIF_CACHE_TTL:
        return
    db = new_session()
    try:
        sid = read_session()
        unread = count_unread_notifications(db, sid["user_id"]) if sid else 0
        _notif_cache = (now, unread)
    finally:
        db.close()


def _get_notification_badge() -> str:
    """Return a notification count badge string, cached for 30s."""
    try:
        _refresh_notif_cache()
        return f" ({_notif_cache[1]})" if _notif_cache[1] > 0 else ""
    except Exception:
        global _notif_warned
        if not _notif_warned:
            _notif_warned = True
            logger.warning("Failed to read notification count", exc_info=True)
        return ""


# ═══════════════════════════════════════════════════════════════════════════════
# Prompt + completions
# ═══════════════════════════════════════════════════════════════════════════════


def _prompt_user_badge() -> tuple[str, str]:
    """Prompt fragment: 'alice (3)' or 'guest'."""
    sid = read_session()
    name = sid.get("name", "guest") if sid else "guest"
    return "class:prompt", f"{name}{_get_notification_badge()}"


def _prompt_text():
    """Build the REPL prompt line with user badge and notifications."""
    parts = [_prompt_user_badge()]
    parts.append(("class:separator", "> "))
    return parts


def _collect_completion_words(db) -> list[str]:
    """Collect completion candidates: article IDs, title words, @names, user IDs."""
    words: list[str] = []
    for a in list_articles(db, limit=50):
        if a.id:
            words.append(a.id)
        if a.title:
            words.extend(w for w in a.title.split() if len(w) > 2)
    for u in list_active_users(db):
        if u.name:
            words.append(f"@{u.name}")
            words.append(u.id)
    return sorted(set(words))


def _refresh_completions():
    """Rebuild dynamic completion word list from DB."""
    db = new_session()
    try:
        session.completion_words = _collect_completion_words(db)
    except Exception:
        logger.warning("Failed to refresh REPL completions", exc_info=True)
    finally:
        db.close()
