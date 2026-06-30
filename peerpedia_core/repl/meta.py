# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""REPL meta utilities — theme, inbox, sink progress.

``_meta_user`` and ``_meta_article`` (context-setting) removed in Phase 0.
User and article pages are now handled by the page stack in ``repl/pages/``.
"""

from __future__ import annotations

from datetime import datetime, timezone

from peerpedia_core.config.params import params

from peerpedia_core.app.context import read_session as _read_session
from peerpedia_core.core import get_notifications_for_user
from peerpedia_core.presentation.rich.components import (
    guest_hint, inbox_empty_msg, notification_table, progress_bar,
    sink_progress_label, theme_label, theme_unknown,
)
from peerpedia_core.repl.state import console, new_session
import peerpedia_core.repl.state as _st


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
