# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""REPL startup banner — user stats and welcome message."""

from __future__ import annotations

import logging
from collections.abc import Mapping

from rich.panel import Panel
from rich.text import Text

from peerpedia_core.core import count_articles
from peerpedia_core.repl.state import console, theme

logger = logging.getLogger(__name__)


def _greeting_panel() -> Text:
    """Build the peerpedia greeting Text object."""
    greeting = Text()
    greeting.append("✧ ", style=theme.styles['accent'])
    greeting.append("PeerPedia", style=f"bold {theme.styles['info']}")
    return greeting


def _format_user_article_stats(db, user_id: str) -> str:
    """Return a formatted article stats line for one user."""
    try:
        drafts = count_articles(db, statuses={"draft"}, author_id=user_id)
        in_review = count_articles(db, statuses={"sedimentation"}, author_id=user_id)
        published = count_articles(db, statuses={"published"}, author_id=user_id)
    except Exception:
        logger.warning("Failed to load REPL dashboard stats", exc_info=True)
        return "?"

    parts: list[str] = []

    if drafts:
        parts.append(f"[bold]{drafts}[/] draft(s)")

    if in_review:
        parts.append(f"[bold]{in_review}[/] in review")

    if published:
        parts.append(f"[bold]{published}[/] published")

    return " · ".join(parts) if parts else "no articles yet"


def _print_logged_in_banner(db, session_data: Mapping[str, str]) -> None:
    """Print startup banner for a logged-in user."""
    user_id = session_data.get("user_id", "")
    user_name = session_data.get("name", "?")

    greeting = _greeting_panel()
    greeting.append("  scholarly terminal", style="muted")

    console.print(Panel(greeting, border_style="muted", padding=(0, 2)))

    user_line = Text("  ")
    user_line.append(user_name, style=f"bold {theme.styles['accent']}")
    user_line.append(f"  {user_id}", style="muted")

    console.print(user_line)
    console.print(f"  [muted]{_format_user_article_stats(db, user_id)}[/]")


def _print_logged_out_banner() -> None:
    """Print startup banner for an anonymous user."""
    greeting = _greeting_panel()

    console.print(Panel(greeting, border_style="muted", padding=(0, 2)))
    console.print(
        "  [muted]Not logged in.  "
        "[accent]register --name <name>[/] to begin.[/]"
    )


def show_startup_banner(db, session_data: Mapping[str, str] | None) -> None:
    """Print the REPL welcome banner with user stats or a registration prompt."""
    console.print()

    if session_data:
        _print_logged_in_banner(db, session_data)
    else:
        _print_logged_out_banner()

    console.print(
        "  [dim]Enter submit  ·  Ctrl+J newline  ·  "
        ":help commands  ·  :quit exit[/]"
    )
    console.print()
