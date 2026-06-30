# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""REPL meta-command handlers — pure business logic, no presentation.

Each handler fetches data and makes decisions.  All Rich rendering
(Table construction, Rich markup strings, progress bars, theme labels)
lives in ``presentation/rich/components.py``.
"""

from __future__ import annotations

from datetime import datetime, timezone

from peerpedia_core.config.params import params

import peerpedia_core.repl.state as _st
from peerpedia_core.app.context import read_session as _read_session
from peerpedia_core.core import (
    get_head_hash as _get_article_head_hash,
    get_notifications_for_user, get_user, list_users_by_name,
    search_articles,
)
from peerpedia_core.presentation.rich.components import (
    article_context_cleared, article_context_line,
    article_search_feedback, guest_hint, inbox_empty_msg,
    notification_table, progress_bar, sink_progress_label,
    theme_label, theme_unknown, user_ambiguous_hint,
    user_found_msg, user_list_table, user_not_found_msg,
)
from peerpedia_core.repl.state import console, new_session


def _meta_user(name):
    db = new_session()
    try:
        u = get_user(db, name)
        if u is None:
            users = list_users_by_name(db, name)
            if len(users) == 1:
                u = users[0]
            elif len(users) > 1:
                console.print(user_list_table(
                    users, title=f"Multiple users matching '{name}'",
                ))
                console.print(user_ambiguous_hint())
                return
        if u:
            _st.set_user(name)
            console.print(user_found_msg(u))
        else:
            console.print(user_not_found_msg(name))
    finally:
        db.close()


def _format_sink_bar(article) -> str:
    """Compute sedimentation progress, return Rich-markup label or ''."""
    if article.status != "sedimentation" or not article.sink_start:
        return ""
    now = datetime.now(timezone.utc)
    start = article.sink_start.replace(tzinfo=timezone.utc) if article.sink_start.tzinfo is None else article.sink_start
    elapsed = (now - start).days
    total = article.sink_duration_days or params.sink.new_article_default_days
    remaining = max(0, total - elapsed)
    bar = progress_bar(min(total, max(0, elapsed)), total)
    return sink_progress_label(bar, remaining, _st.theme.styles["muted"])


def _resolve_article_ref(db, ref: str):
    """Search for *ref*, handle ambiguity.  Returns article or None."""
    candidates = search_articles(db, ref)
    feedback = article_search_feedback(ref, candidates)
    if feedback is not None:
        console.print(feedback)
        return None
    return candidates[0]


def _meta_article(ref: str):
    db = new_session()
    try:
        if not ref:
            _st.set_article_context(None)
            console.print(article_context_cleared())
            return
        article = _resolve_article_ref(db, ref)
        if article is None:
            return
        _st.set_article_context(article.id, article.title, _get_article_head_hash(article.id))
        console.print(article_context_line(
            article.id, article.title, _st.session.article_commit or "",
            _format_sink_bar(article),
        ))
    finally:
        db.close()


def _meta_theme(mode: str):
    mode = mode.strip().lower() or "parchment"
    theme_name = _st.set_theme(mode)
    label = theme_label(theme_name)
    if label:
        console.print(label)
    else:
        console.print(theme_unknown(mode))


def _show_inbox():
    db = new_session()
    try:
        session_data = _read_session()
        if not session_data:
            console.print(guest_hint())
            return
        notifications = get_notifications_for_user(db, session_data["user_id"])
        if not notifications:
            console.print(inbox_empty_msg())
            return
        console.print(notification_table(notifications[:20]))
    finally:
        db.close()
