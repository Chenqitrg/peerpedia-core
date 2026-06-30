# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""REPL startup banner — user stats and welcome message."""

from __future__ import annotations

import logging
from collections.abc import Mapping

from rich.panel import Panel
from rich.text import Text

from peerpedia_core.core import count_articles
from peerpedia_core.presentation.rich.components import (
    banner_keyboard_hints, banner_stats_line, banner_subtitle,
    greeting_banner, guest_hint,
)
from peerpedia_core.repl.state import console, theme

logger = logging.getLogger(__name__)

def _format_user_article_stats(db, user_id: str) -> str:
    """Return a formatted article stats line for one user."""
    try:
        drafts = count_articles(db, statuses={"draft"}, author_id=user_id)
        in_review = count_articles(db, statuses={"sedimentation"}, author_id=user_id)
        published = count_articles(db, statuses={"published"}, author_id=user_id)
    except Exception:
        logger.warning("Failed to load REPL dashboard stats", exc_info=True)
        return "?"

    return banner_stats_line(drafts, in_review, published)


def _print_logged_in_banner(db, session_data: Mapping[str, str]) -> None:
    """Print startup banner for a logged-in user."""
    user_id = session_data.get("user_id", "")
    user_name = session_data.get("name", "?")

    greeting = greeting_banner(theme.styles['accent'], theme.styles['info'])
    greeting.append(banner_subtitle(), style="muted")

    console.print(Panel(greeting, border_style="muted", padding=(0, 2)))

    user_line = Text("  ")
    user_line.append(user_name, style=f"bold {theme.styles['accent']}")
    user_line.append(f"  {user_id}", style="muted")

    console.print(user_line)
    console.print(_format_user_article_stats(db, user_id))


def _print_logged_out_banner() -> None:
    """Print startup banner for an anonymous user."""
    greeting = greeting_banner(theme.styles['accent'], theme.styles['info'])

    console.print(Panel(greeting, border_style="muted", padding=(0, 2)))
    console.print(f"  {guest_hint()}")


def show_startup_banner(db, session_data: Mapping[str, str] | None) -> None:
    """Print the REPL welcome banner with user stats or a registration prompt."""
    console.print()

    if session_data:
        _print_logged_in_banner(db, session_data)
    else:
        _print_logged_out_banner()

    console.print(f"  {banner_keyboard_hints()}")
    console.print()
