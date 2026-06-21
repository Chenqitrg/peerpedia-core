# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Rich-powered terminal display helpers — inline use in handler code.

Layer 0 of the CLI package.  Only imports from ``rich`` — no dependency
on any other PeerPedia module.
"""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.theme import Theme

# ── Rich console with theme ──────────────────────────────────────────────

theme = Theme({
    "success": "bold green",
    "error": "bold red",
    "warning": "bold yellow",
    "info": "bold blue",
    "accent": "bold cyan",
    "muted": "dim",
})
console = Console(theme=theme)


# ── Output formatting — shared display helpers for all commands ───────────


def _print_panel(title: str, content: str, style: str = "info") -> None:
    """Show a single item's details in a bordered panel."""
    console.print(Panel(content, title=title, border_style="muted", title_align="left"))


def _print_table(headers: list[str], rows: list[list[str]], title: str | None = None) -> None:
    """Show a list as a table."""
    table = Table(title=title, border_style="muted")
    for h in headers:
        table.add_column(h, style="bold" if headers.index(h) == 0 else "")
    for row in rows:
        table.add_row(*row)
    console.print(table)


def _status_badge(status: str) -> str:
    """Colored status label: draft=white, sedimentation=yellow, published=green."""
    colors = {"draft": "white", "sedimentation": "yellow", "published": "green"}
    return f"[{colors.get(status, 'white')}]{status}[/]"


def _stars(score: dict | None, dims: list[str] | None = None) -> str:
    """Render 5-dim scores as stars, e.g. ★★★★☆ 4/5."""
    if not score:
        return "[muted]no score[/]"
    if dims is None:
        dims = ["originality", "rigor", "completeness", "pedagogy", "impact"]
    return "\n".join(
        f"  {d:<14} [accent]{'★'*v}[/][muted]{'☆'*(5-v)}[/]  {v}/5"
        for d in dims
        for v in [int(score.get(d, 0))]
    )
