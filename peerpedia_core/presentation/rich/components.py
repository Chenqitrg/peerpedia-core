# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Shared Rich rendering components — pure display, zero side effects.

Every function takes a *console* parameter so both CLI and REPL can pass
their own ``rich.console.Console`` instance.  No module-level console.

Architecture: imports only from ``types/`` and stdlib.  Never from
``cli/``, ``repl/``, ``app/``, ``core/``, or ``storage/``.
"""

from __future__ import annotations

from rich.console import Console
from rich.markup import escape as _escape
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from peerpedia_core.types.scores import SCORE_DIMENSIONS


# ── Score dimensions ─────────────────────────────────────────────────────────

SCORE_DIM_NAMES: list[str] = list(SCORE_DIMENSIONS.values())


# ── Scores ───────────────────────────────────────────────────────────────────

def score_lines(score: dict | None, dims: list[str] | None = None) -> list[str]:
    """Return one plain-text line per dimension, e.g. ``'originality    ★★★☆☆  3/5'``."""
    if not score:
        return ["—"]
    if dims is None:
        dims = SCORE_DIM_NAMES
    return [
        f"  {d:<14} {'★'*v}{'☆'*(5-v)}  {v}/5"
        for d in dims
        for v in [int(score.get(d, 0))]
    ]


def score_stars(score: dict | None, dims: list[str] | None = None) -> str:
    """Render 5-dim scores with Rich markup, e.g. ``[accent]★★★★☆[/][muted]☆[/]  4/5``."""
    if not score:
        return "[muted]no score[/]"
    if dims is None:
        dims = SCORE_DIM_NAMES
    return "\n".join(
        f"  {d:<14} [accent]{'★'*v}[/][muted]{'☆'*(5-v)}[/]  {v}/5"
        for d in dims
        for v in [int(score.get(d, 0))]
    )


# ── Badges ───────────────────────────────────────────────────────────────────

def status_badge(status: str) -> str:
    """Colored status label: draft=white, sedimentation=yellow, published=green."""
    colors = {"draft": "white", "sedimentation": "yellow", "published": "green"}
    return f"[{colors.get(status, 'white')}]{status}[/]"


# ── Tables & panels ──────────────────────────────────────────────────────────

def print_table(console: Console, headers: list[str], rows: list[list[str]],
                title: str | None = None) -> None:
    """Render a list of rows as a Rich Table."""
    table = Table(title=title, border_style="muted")
    for i, h in enumerate(headers):
        table.add_column(h, style="bold" if i == 0 else "")
    for row in rows:
        table.add_row(*[str(v) for v in row])
    console.print(table)


def print_panel(console: Console, title: str, content: str | Text,
                border_style: str = "muted") -> None:
    """Show a single item's details in a bordered panel."""
    console.print(Panel(content, title=title, border_style=border_style,
                        title_align="left"))


# ── User display ─────────────────────────────────────────────────────────────

def display_user(console: Console, name: str, user_id: str, *,
                 affiliation: str = "",
                 expertise: list[str] | None = None,
                 reputation: dict | None = None,
                 follower_count: int | None = None,
                 public_key: str | None = None,
                 created_at: str | None = None) -> None:
    """Render user metadata panel — pure display, zero side effects."""
    body = Text()
    body.append(str(name), style="bold info")
    if follower_count is not None:
        body.append(f"      {follower_count} follower(s)", style="muted")
    body.append(f"\n{user_id}", style="accent")
    if public_key:
        body.append(f"\nPublic key: {public_key[:16]}…", style="dim")
    if affiliation:
        body.append("\nAffiliation: ")
        body.append(str(affiliation), style="info")
    if expertise:
        body.append(f"\nExpertise: {', '.join(_escape(str(e)) for e in expertise)}")
    if reputation:
        body.append("\nReputation:\n")
        body.append(Text.from_markup(score_stars(reputation)))
    if created_at:
        body.append(f"\nCreated: {created_at}", style="dim")
    print_panel(console, "User", body)
