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

from peerpedia_core.types.scores import SCORE_DIMENSIONS

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
    for i, h in enumerate(headers):
        table.add_column(h, style="bold" if i == 0 else "")
    for row in rows:
        table.add_row(*row)
    console.print(table)


def _status_badge(status: str) -> str:
    """Colored status label: draft=white, sedimentation=yellow, published=green."""
    colors = {"draft": "white", "sedimentation": "yellow", "published": "green"}
    return f"[{colors.get(status, 'white')}]{status}[/]"


def display_article(title: str, status: str, authors: list[str], score: dict | None, abstract: str | None) -> None:
    """Render article metadata panel — pure display, zero side effects."""
    scores_str = _stars(score) if score else "[muted]no scores[/]"
    body = (
        f"[bold info]{title}[/]      {_status_badge(status)}\n"
        f"Authors: {', '.join(authors)}\n"
        f"Score:   {scores_str}\n"
        f"Abstract: {abstract or '[muted]none[/]'}"
    )
    _print_panel("Article", body)


def display_user(name: str, affiliation: str, expertise: list[str], reputation: dict | None, user_id: str) -> None:
    """Render user metadata panel — pure display, zero side effects."""
    body = f"[bold info]{name}[/]"
    if affiliation:
        body += f"\nAffiliation: {affiliation}"
    if expertise:
        body += f"\nExpertise: {', '.join(expertise)}"
    if reputation:
        body += f"\nReputation: {_stars(reputation)}"
    body += f"\nID: [accent]{user_id[:8]}[/]"
    _print_panel("User", body)


def display_diff(diff_text: str, stats: dict) -> None:
    """Render a unified diff with GitHub-style colorization.

    + lines: green, - lines: red, @@ hunk headers: bold cyan,
    file/index lines: bold, context: dim.
    """
    totals = stats.get("total", {})
    ins = totals.get("insertions", 0)
    dels = totals.get("deletions", 0)
    files = stats.get("files", [])

    header = f"[bold]{', '.join(files)}[/]  " if files else ""
    header += f"[success]+{ins}[/]  [error]-{dels}[/]"
    console.print()
    console.print(Panel(header, title="Diff", border_style="muted", title_align="left"))
    console.print()

    for line in diff_text.split("\n"):
        if line.startswith("@@") and line.rstrip().endswith("@@"):
            console.print(f"[bold cyan]{line}[/]")
        elif line.startswith("+++") or line.startswith("---"):
            console.print(f"[bold]{line}[/]")
        elif line.startswith("diff --git") or line.startswith("index "):
            console.print(f"[bold]{line}[/]")
        elif line.startswith("+") and not line.startswith("+++"):
            console.print(f"[green]{line}[/]")
        elif line.startswith("-") and not line.startswith("---"):
            console.print(f"[red]{line}[/]")
        else:
            console.print(f"[dim]{line}[/]", markup=False)

    console.print()


def _stars(score: dict | None, dims: list[str] | None = None) -> str:
    """Render 5-dim scores as stars, e.g. ★★★★☆ 4/5."""
    if not score:
        return "[muted]no score[/]"
    if dims is None:
        dims = list(SCORE_DIMENSIONS.values())
    return "\n".join(
        f"  {d:<14} [accent]{'★'*v}[/][muted]{'☆'*(5-v)}[/]  {v}/5"
        for d in dims
        for v in [int(score.get(d, 0))]
    )
