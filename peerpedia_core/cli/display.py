# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Rich-powered terminal display helpers.

Imports from ``app/commands/display.py`` for data lookups — never
from ``core/`` directly.
"""

from __future__ import annotations

from rich.panel import Panel
from rich.table import Table

from peerpedia_core.app.commands.display import (
    list_author_ids,
    read_frontmatter,
    resolve_author_names,
    source_path,
)
from peerpedia_core.cli.info import console, _page
from peerpedia_core.types.scores import SCORE_DIMENSIONS


# ── Output formatting — shared display helpers for all commands ────────────


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


def display_article(title: str, status: str, authors: list[str],
                    score: dict | None, abstract: str | None) -> None:
    """Render article metadata panel — pure display, zero side effects."""
    scores_str = _stars(score) if score else "[muted]no scores[/]"
    body = (
        f"[bold info]{title}[/]      {_status_badge(status)}\n"
        f"Authors: {', '.join(authors)}\n"
        f"Score:\n{scores_str}"
    )
    if abstract:
        body += f"\nAbstract: {abstract}"
    _print_panel("Article", body)


def display_user(name: str, affiliation: str, expertise: list[str],
                 reputation: dict | None, user_id: str) -> None:
    """Render user metadata panel — pure display, zero side effects."""
    body = f"[bold info]{name}[/]"
    if affiliation:
        body += f"\nAffiliation: {affiliation}"
    if expertise:
        body += f"\nExpertise: {', '.join(expertise)}"
    if reputation:
        body += f"\nReputation:\n{_stars(reputation)}"
    body += f"\nID: [accent]{user_id}[/]"
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
            console.print(line, style="dim")

    console.print()


# ── Score display component ──────────────────────────────────────────────

SCORE_DIM_NAMES: list[str] = list(SCORE_DIMENSIONS.values())


def _score_lines(score: dict | None, dims: list[str] | None = None) -> list[str]:
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


def _stars(score: dict | None, dims: list[str] | None = None) -> str:
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


# ── Pager ────────────────────────────────────────────────────────────────


def display_full_content(raw: str, article_id: str = "") -> None:
    """Render the full article source with optional empty-state guidance."""
    body = raw.split("---\n", 2)[-1].strip() if raw.count("---") >= 2 else raw
    if body:
        console.print("\n[bold]── Content ──[/]")
        _page(raw)
    elif article_id:
        display_empty_article_list("N_NO_CONTENT", id=article_id)


def display_empty_article_list(code: str, **fmt) -> None:
    """Show context-sensitive guidance when an article list is empty."""
    from peerpedia_core.messages import lookup as _lookup
    _, m = _lookup(code)
    if m.text:
        console.print(m.text.format(**fmt) if fmt else m.text)


# ── Article meta ─────────────────────────────────────────────────────────


def display_article_meta(db, article, *,
                         author_ids: list[str] | None = None) -> None:
    """Resolve full article metadata from DB + source file, then display.

    If *author_ids* is passed, it is used directly (allows batch
    preloading in list handlers).  Otherwise queries via the app layer.
    """
    ids = author_ids or list_author_ids(db, article.id)
    names = resolve_author_names(db, ids)

    f = source_path(article.id)
    if f is not None:
        raw = f.read_text()
        fm = read_frontmatter(raw)
        display_article(
            title=fm.get("title", article.title), status=article.status,
            authors=names, score=article.score,
            abstract=fm.get("abstract", article.abstract),
        )
    else:
        display_article(
            title=article.title, status=article.status,
            authors=names, score=article.score,
            abstract=article.abstract,
        )
