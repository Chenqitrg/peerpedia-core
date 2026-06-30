# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""REPL startup banner — user stats and welcome message."""

from __future__ import annotations

from rich.panel import Panel
from rich.text import Text

import peerpedia_core.repl.state as _st
from peerpedia_core.repl.state import console, theme
from peerpedia_core.core import count_articles


def show_startup_banner(db, session_data: dict | None) -> None:
    """Print the REPL welcome banner with user stats (or registration prompt)."""
    console.print()
    if session_data:
        user_id = session_data.get("user_id", "")
        user_name = session_data.get("name", "?")
        try:
            drafts = count_articles(db, statuses={"draft"}, author_id=user_id)
            in_review = count_articles(db, statuses={"sedimentation"}, author_id=user_id)
            published = count_articles(db, statuses={"published"}, author_id=user_id)
            parts = []
            if drafts: parts.append(f"[bold]{drafts}[/] draft(s)")
            if in_review: parts.append(f"[bold]{in_review}[/] in review")
            if published: parts.append(f"[bold]{published}[/] published")
            status_line = " · ".join(parts) if parts else "no articles yet"
        except Exception:
            import logging
            logging.getLogger(__name__).warning(
                "Failed to load REPL dashboard stats", exc_info=True
            )
            status_line = "?"
        greeting = Text()
        greeting.append("✧ ", style=theme.styles['accent'])
        greeting.append("PeerPedia", style=f"bold {theme.styles['info']}")
        greeting.append("  scholarly terminal", style="muted")
        console.print(Panel(greeting, border_style="muted", padding=(0, 2)))
        user_line = Text()
        user_line.append(user_name, style=f"bold {theme.styles['accent']}")
        user_line.append(f"  {user_id}", style="muted")
        console.print(f"  {user_line}")
        console.print(f"  [muted]{status_line}[/]")
    else:
        greeting = Text()
        greeting.append("✧ ", style=theme.styles['accent'])
        greeting.append("PeerPedia", style=f"bold {theme.styles['info']}")
        console.print(Panel(greeting, border_style="muted", padding=(0, 2)))
        console.print("  [muted]Not logged in.  [accent]register --name <name>[/] to begin.[/]")
    console.print("  [dim]Enter submit  ·  Ctrl+J newline  ·  :help commands  ·  :quit exit[/]")
    console.print()
