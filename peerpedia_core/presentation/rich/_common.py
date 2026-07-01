# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Shared rendering utilities — constants, text helpers, generic panels."""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

_COMMIT_HASH_LEN = 7
_STATUS_LABEL_LEN = 4
_PUBKEY_PREVIEW_LEN = 16
_TIMESTAMP_PREVIEW_LEN = 16

_BORDER_FOCUSED = "bold cyan"


def abbrev_commit(hash_str: str) -> str:
    """Abbreviate a git commit hash, e.g. ``'abc1234'``."""
    return hash_str[:_COMMIT_HASH_LEN]


def status_label(status: str | None) -> str:
    """Short status label, e.g. ``'DRAF'``.  Unknown → ``'?'``."""
    return status[:_STATUS_LABEL_LEN].upper() if status else "?"


def progress_bar(filled: int, total: int) -> str:
    """Plain-text progress bar, e.g. ``'████░░'``."""
    return "█" * filled + "░" * (total - filled)


def print_panel(console: Console, title: str, content: str | Text,
                border_style: str = "muted") -> None:
    """Show a single item's details in a bordered panel."""
    console.print(Panel(content, title=title, border_style=border_style,
                        title_align="left"))


def print_table(console: Console, headers: list[str], rows: list[list[str]],
                title: str | None = None) -> None:
    """Render a list of rows as a Rich Table."""
    table = Table(title=title, border_style="muted")
    for i, h in enumerate(headers):
        table.add_column(h, style="bold" if i == 0 else "")
    for row in rows:
        table.add_row(*[str(v) for v in row])
    console.print(table)


def data_table(headers: list[str], rows: list[list], *,
               title: str | None = None) -> Table:
    """Build a generic data table from headers and rows."""
    t = Table(title=title, border_style="muted")
    for i, h in enumerate(headers):
        t.add_column(str(h), style="bold" if i == 0 else "")
    for row in rows:
        t.add_row(*[str(v) for v in row])
    return t


def focused_panel(console: Console, title: str, content: str | Text,
                  *, is_focused: bool = False) -> None:
    """Print a panel with focus indicator (left bar) when selected."""
    border = _BORDER_FOCUSED if is_focused else "muted"
    console.print(Panel(content, title=title, border_style=border,
                        title_align="left"))
