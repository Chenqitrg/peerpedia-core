# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Article display — panels, context line, stats."""

from __future__ import annotations

from rich.console import Console
from rich.text import Text

from peerpedia_core.presentation.rich._common import abbrev_commit, print_panel
from peerpedia_core.presentation.rich._scores import score_stars
from peerpedia_core.types.entities import ArticleMetaExchange
from peerpedia_core.types.status import ArticleStatus


def status_badge(status: ArticleStatus) -> str:
    """Colored status label: draft=white, sedimentation=yellow, published=green."""
    colors = {ArticleStatus.DRAFT: "white", ArticleStatus.SEDIMENTATION: "yellow", ArticleStatus.PUBLISHED: "green"}
    return f"[{colors.get(status, 'white')}]{status}[/]"


def article_meta_panel(console: Console, meta: ArticleMetaExchange) -> None:
    """Render a single article as a Rich panel."""
    body = Text()
    body.append(str(meta.title), style="bold info")
    body.append(f"      {status_badge(meta.status)}\n")
    body.append(f"Authors: {', '.join(meta.authors)}\n")
    body.append("Score:\n")
    if meta.score:
        body.append(Text.from_markup(score_stars(meta.score)))
    else:
        body.append("no scores", style="muted")
    if meta.abstract:
        body.append(f"\nAbstract: {meta.abstract}")
    print_panel(console, "Article", body)


def article_panels(console: Console, items: list[ArticleMetaExchange]) -> None:
    """Render a list of articles as Rich panels."""
    for a in items:
        article_meta_panel(console, a)


def article_context_line(article_id: str, title: str, commit_hash: str,
                         sink_bar: str) -> str:
    """Styled article context display line with Rich markup."""
    commit = f" @{abbrev_commit(commit_hash)}" if commit_hash else ""
    return (
        f"[success]▸[/] {title} "
        f"[muted]({article_id}{commit})[/]"
        f"{sink_bar}"
    )


def article_context_cleared() -> str:
    """Rich-markup message when article context is cleared."""
    return "[muted]Article context cleared.[/]"


_SEARCH_PREVIEW_LIMIT = 20


def article_search_feedback(ref: str, candidates: list) -> str | None:
    """Rich-markup feedback for article search results.  None if exactly 1 match."""
    if not candidates:
        return f"[error]✗[/] ArticleMetaStorage '{ref}' not found."
    if len(candidates) > 1:
        lines = [f"[warning]{len(candidates)} articles match '{ref}':[/]"]
        for a in candidates[:_SEARCH_PREVIEW_LIMIT]:
            lines.append(f"  {a.id}  {a.title}")
        return "\n".join(lines)
    return None


def article_stats_line(drafts: int, in_review: int, published: int) -> str:
    """Rich-markup article stats: '3 draft(s) · 2 in review · 1 published'."""
    parts = []
    if drafts:
        parts.append(f"[bold]{drafts}[/] draft(s)")
    if in_review:
        parts.append(f"[bold]{in_review}[/] in review")
    if published:
        parts.append(f"[bold]{published}[/] published")
    return " · ".join(parts) if parts else "no articles yet"


def banner_stats_line(drafts: int, in_review: int, published: int) -> str:
    """Rich-markup banner stats line with muted wrapper and indent."""
    return f"  [muted]{article_stats_line(drafts, in_review, published)}[/]"
