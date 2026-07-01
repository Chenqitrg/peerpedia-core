# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Shared Rich rendering components — pure display, zero side effects.

Architecture: imports only from foundation (``types/``, ``messages``, stdlib).
Never from ``cli/``, ``repl/``, ``app/``, ``core/``, ``storage/``, or ``server/``.
"""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from peerpedia_core.types.entities import DiffResult, NotificationExchange

# ── Re-exports: sub-modules ──────────────────────────────────────────────

from peerpedia_core.presentation.rich._common import (  # noqa: F401
    _COMMIT_HASH_LEN, _PUBKEY_PREVIEW_LEN, _STATUS_LABEL_LEN, _TIMESTAMP_PREVIEW_LEN,
    abbrev_commit, data_table, focused_panel, print_panel, print_table,
    progress_bar, status_label,
)
from peerpedia_core.presentation.rich._scores import (  # noqa: F401
    SCORE_DIM_NAMES, score_lines, score_stars,
)
from peerpedia_core.presentation.rich._articles import (  # noqa: F401
    article_context_cleared, article_context_line, article_meta_panel,
    article_panels, article_search_feedback, article_stats_line,
    banner_stats_line, status_badge,
)
from peerpedia_core.presentation.rich._users import (  # noqa: F401
    display_user, user_line_text, user_list_table, user_panels,
)
from peerpedia_core.presentation.rich._messages import (  # noqa: F401
    banner_keyboard_hints, banner_subtitle, error_lines,
    greeting_banner, guest_hint, repl_bye_msg, repl_cancelled_msg,
    repl_interrupt_msg, repl_internal_error, repl_parse_error,
    repl_tty_required, repl_unavailable_cmd, repl_unknown_cmd,
    sink_progress_label, theme_label, theme_unknown,
)

# ── Diff ─────────────────────────────────────────────────────────────────


def diff_panel(console: Console, diff: DiffResult) -> None:
    """Render a DiffResult with GitHub-style colorization."""
    header = Text()
    if diff.files:
        header.append(", ".join(diff.files), style="bold")
        header.append("  ")
    header.append(f"+{diff.insertions}", style="success")
    header.append("  ")
    header.append(f"-{diff.deletions}", style="error")
    console.print()
    console.print(Panel(header, title="Diff", border_style="muted", title_align="left"))
    console.print()

    for line in diff.diff_text.split("\n"):
        if line.startswith("@@") and line.rstrip().endswith("@@"):
            console.print(Text(line, style="bold cyan"))
        elif line.startswith("+++") or line.startswith("---"):
            console.print(Text(line, style="bold"))
        elif line.startswith("diff --git") or line.startswith("index "):
            console.print(Text(line, style="bold"))
        elif line.startswith("+") and not line.startswith("+++"):
            console.print(Text(line, style="green"))
        elif line.startswith("-") and not line.startswith("---"):
            console.print(Text(line, style="red"))
        else:
            console.print(Text(line, style="dim"))

    console.print()


# ── Notifications ────────────────────────────────────────────────────────

_NOTIF_TABLE_TIME_W = 16


def notification_table(notifications: list[NotificationExchange], *,
                       title: str = "Notifications") -> Table:
    """Build a notification list table from NotificationExchange objects."""
    t = Table(title=title, border_style="muted")
    t.add_column("Time", style="muted", width=_NOTIF_TABLE_TIME_W)
    t.add_column("Event", style="accent")
    for n in notifications:
        ts = n.created_at[:_TIMESTAMP_PREVIEW_LEN].replace("T", " ") if n.created_at else ""
        marker = "[bold]●[/] " if not n.read else "  "
        t.add_row(ts, f"{marker}{n.message}")
    return t


# ── Help text rendering ──────────────────────────────────────────────────

_MIN_SECTION_HEADER_LEN = 3
_COMMENT_INDENT = 2
_HELP_SEPARATOR_WIDTH = 60


def _is_section_header(stripped: str) -> bool:
    if len(stripped) < _MIN_SECTION_HEADER_LEN or not any(c.isalpha() for c in stripped):
        return False
    return all(c.isupper() or c in " /-&()" for c in stripped)


def style_help_line(line: str, stripped: str, accent_style: str,
                    info_style: str, muted_style: str) -> list[tuple[str, str]]:
    import re

    if _is_section_header(stripped):
        return [(info_style, line + "\n")]
    if stripped.startswith("peerpedia") or stripped.startswith("$ "):
        return [(accent_style, line + "\n")]
    if re.match(rf"^ {{{_COMMENT_INDENT},}}# (→|  )", line):
        return [(muted_style, line + "\n")]
    if re.match(r"^# (→|  )", line):
        return [(muted_style, line + "\n")]
    m = re.match(r"^( +)(--\S+)(.*)", line)
    if m:
        return [("", m.group(1)), ("bold", m.group(2)), ("", m.group(3) + "\n")]
    return []


def help_not_found_msg(topic: str) -> str:
    return (
        f"[warning]No help for [accent]{topic}[/]. "
        f"Try [accent]:help[/] (no argument) to see all commands.[/]"
    )


def help_group_extra_lines(topic: str, others: list[str]) -> list[str]:
    names = ", ".join(f"[accent]{s}[/]" for s in others)
    return [
        f"\n\nOTHER {topic.upper()} COMMANDS\n  {names}\n",
        f"\n  Type [accent]:help {topic} <cmd>[/] for any of the above.",
    ]


def render_help_text(text: str, accent: str, info: str, muted: str) -> Text:
    out = Text()
    in_boilerplate = False
    boilerplate_ended = False

    for line in text.split("\n"):
        stripped = line.strip()

        if stripped == "HOW TO READ THIS HELP":
            in_boilerplate = True
        elif in_boilerplate and stripped == "EXAMPLES":
            in_boilerplate = False
            if not boilerplate_ended:
                boilerplate_ended = True
                out.append("─" * _HELP_SEPARATOR_WIDTH + "\n", style=muted)

        styled = style_help_line(line, stripped, accent, info, muted)
        if styled:
            for s, t in styled:
                out.append(t, style=s if s else None)
        else:
            out.append(line + "\n")

    return out
