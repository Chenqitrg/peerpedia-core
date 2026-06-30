# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""REPL help subsystem — overview (``:help``) and topic-specific (``:help <cmd>``).

Renders CLI help ``.txt`` files with Rich styling: coloured section headers,
command examples in accent colour, dim comments, and bold flag names.
"""

from __future__ import annotations

from pathlib import Path

from rich.panel import Panel
from rich.table import Table
from rich.text import Text

import peerpedia_core.repl.state as _st
from peerpedia_core.app.commandspec import COMMAND_GROUPS
from peerpedia_core.presentation.rich.components import (
    help_group_extra_lines, help_not_found_msg, render_help_text,
)
from peerpedia_core.repl.state import console

_CLI_HELP_DIR = Path(__file__).resolve().parent.parent / "cli" / "help"
_REPL_HELP_DIR = Path(__file__).resolve().parent / "help"
_CMD_COL_WIDTH = 16


# ── Public entry points ───────────────────────────────────────────────────


def _print_kv_panel(filepath: Path, title: str, columns: list[tuple[str, str, int]]) -> None:
    """Read a KV file, build a Table, print in a Panel."""
    t = Table(show_header=False, border_style="muted", padding=(0, 1))
    for name, style, width in columns:
        t.add_column(name, style=style, width=width)
    for k, v in _parse_kv(filepath):
        t.add_row(k, v)
    console.print(Panel(t, title=title, border_style="muted", title_align="left", padding=(0, 2)))


def _meta_help(topic: str = ""):
    """Show REPL help — overview or topic-specific."""
    if topic:
        _show_topic_help(topic)
        return

    welcome_path = _REPL_HELP_DIR / "_welcome.txt"
    console.print(Panel(
        Text.from_markup(welcome_path.read_text().strip()),
        border_style="muted", padding=(0, 2),
    ))

    _print_kv_panel(_REPL_HELP_DIR / "_meta_commands.txt", "REPL Commands", [
        ("cmd", f"bold {_st.theme.styles['info']}", _CMD_COL_WIDTH),
        ("desc", "muted", 0),
    ])
    _print_kv_panel(_REPL_HELP_DIR / "_keys.txt", "Keys", [
        ("key", "bold", 10),
        ("action", "muted", 0),
    ])


def _try_repl_help(topic: str) -> bool:
    """Try REPL-specific help file.  Returns True if found."""
    path = _REPL_HELP_DIR / f"{topic}.txt"
    if path.is_file():
        _display_help_panel(path.read_text(), title=f"REPL: {topic}")
    return path.is_file()


def _try_cli_help(topic: str) -> bool:
    """Try exact CLI help file match.  Returns True if found."""
    name = topic.replace(" ", "_") if " " in topic else topic
    path = _CLI_HELP_DIR / f"{name}.txt"
    if path.is_file():
        _display_help_panel(path.read_text(), title=topic)
    return path.is_file()


def _try_group_help(topic: str) -> bool:
    """Try group fallback (e.g. 'review' → review_submit help).  Returns True if found."""
    subs = _find_subcommands_for_group(topic)
    if not subs:
        return False
    path = _CLI_HELP_DIR / f"{topic}_{subs[0]}.txt"
    if not path.is_file():
        return False
    extra = help_group_extra_lines(topic, subs[1:]) if len(subs) > 1 else []
    _display_help_panel(path.read_text(), title=topic, extra_markup=extra)
    return True


def _show_topic_help(topic: str):
    """Display detailed help for *topic*, trying 3 lookup strategies."""
    if _try_repl_help(topic) or _try_cli_help(topic) or _try_group_help(topic):
        return
    console.print(help_not_found_msg(topic))


# ── Internal helpers ──────────────────────────────────────────────────────


def _find_subcommands_for_group(group: str) -> list[str]:
    """Return subcommand names that belong to *group*."""
    for grp in COMMAND_GROUPS:
        if grp.name == group:
            return sorted(c.action for c in grp.commands if c.action)
    return []


def _parse_kv(filepath: Path) -> list[tuple[str, str]]:
    """Parse a ``key :: value`` file into (key, value) pairs.

    Blank lines and lines starting with ``#`` are skipped.
    """
    pairs: list[tuple[str, str]] = []
    for line in filepath.read_text().strip().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if " :: " in line:
            k, v = line.split(" :: ", 1)
            pairs.append((k.strip(), v.strip()))
    return pairs


def _display_help_panel(text: str, title: str = "Help",
                        extra_markup: list[str] | None = None):
    """Display help text in a Rich Panel with muted border.

    *text* is plain text from a ``.txt`` help file — parsed and styled.
    *extra_markup* are optional Rich-markup lines appended after the
    rendered text (used for the "OTHER … COMMANDS" group listing).
    """
    rendered = render_help_text(
        text.strip(),
        accent=_st.theme.styles.get("accent", "bold"),
        info=f"bold {_st.theme.styles.get('info', '')}",
        muted=_st.theme.styles.get("muted", "dim"),
    )
    if extra_markup:
        for markup in extra_markup:
            rendered.append_text(Text.from_markup(markup))
    console.print(Panel(rendered, title=title, border_style="muted",
                        title_align="left", padding=(1, 2)))
