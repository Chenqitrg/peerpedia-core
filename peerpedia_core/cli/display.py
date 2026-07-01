# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Rich-powered terminal display helpers.

Imports from ``app/readmodels/articles.py`` for data lookups — never
from ``core/`` directly.
"""

from __future__ import annotations

from rich.panel import Panel
from rich.text import Text

from peerpedia_core.cli.info import console, _page
from peerpedia_core.types.entities import ArticleMetaExchange, DiffResult, UserExchange
from peerpedia_core.messages import lookup as _lookup
from peerpedia_core.presentation.rich.components import (
    SCORE_DIM_NAMES,
    article_meta_panel as _shared_article_meta_panel,
    article_panels,
    diff_panel as _shared_diff_panel,
    display_user as _shared_display_user,
    print_panel as _shared_print_panel,
    print_table as _shared_print_table,
    score_lines as _shared_score_lines,
    score_stars as _shared_score_stars,
    status_badge as _shared_status_badge,
)


# ── Output formatting — shared display helpers for all commands ────────────


def _print_panel(title: str, content: str | Text) -> None:
    """Show a single item's details in a bordered panel."""
    _shared_print_panel(console, title, content)


def _print_table(headers: list[str], rows: list[list[str]], title: str | None = None) -> None:
    """Show a list as a table."""
    _shared_print_table(console, headers, rows, title=title)


def _status_badge(status: str) -> str:
    """Colored status label: draft=white, sedimentation=yellow, published=green."""
    return _shared_status_badge(status)


def display_article(meta: ArticleMetaExchange) -> None:
    """Render article metadata panel from an exchange object."""
    _shared_article_meta_panel(console, meta)


def display_user(user: UserExchange) -> None:
    """Render user metadata panel from an exchange object."""
    _shared_display_user(console, user)


def display_diff(diff: DiffResult) -> None:
    """Render a unified diff from a DiffResult."""
    _shared_diff_panel(console, diff)


# ── Score display component ──────────────────────────────────────────────

def _score_lines(score: dict | None, dims: list[str] | None = None) -> list[str]:
    """Return one plain-text line per dimension, e.g. ``'originality    ★★★☆☆  3/5'``."""
    return _shared_score_lines(score, dims)


def _stars(score: dict | None, dims: list[str] | None = None) -> str:
    """Render 5-dim scores with Rich markup, e.g. ``[accent]★★★★☆[/][muted]☆[/]  4/5``."""
    return _shared_score_stars(score, dims)


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
    _, m = _lookup(code)
    if m.text:
        console.print(m.text.format(**fmt) if fmt else m.text)


# ── Article list ──────────────────────────────────────────────────────────


def display_article_list(items: list[ArticleMetaExchange]) -> None:
    """Render Rich article meta panels for a batch of article views."""
    article_panels(console, items)
