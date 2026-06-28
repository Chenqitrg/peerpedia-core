# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""REPL help subsystem — overview (``:help``) and topic-specific (``:help <cmd>``).

Renders CLI help ``.txt`` files with Rich styling: coloured section headers,
command examples in accent colour, dim comments, and bold flag names.
"""

from __future__ import annotations

import re
from pathlib import Path

from rich.panel import Panel
from rich.table import Table
from rich.text import Text

import peerpedia_core.repl.state as _st
from peerpedia_core.cli.parser import COMMAND_GROUPS, get_cmd_map
from peerpedia_core.repl.state import console

_CLI_HELP_DIR = Path(__file__).resolve().parent.parent / "cli" / "help"
_REPL_HELP_DIR = Path(__file__).resolve().parent / "help"


# ── Public entry points ───────────────────────────────────────────────────


def _meta_help(topic: str = ""):
    """Show REPL help — overview or topic-specific.

    ``:help`` (no argument) shows the 3-tier overview:
    1.  Welcome + quick-start examples
    2.  Meta-commands table (everything starting with ``:``)
    3.  Keyboard shortcuts

    ``:help <topic>`` shows detailed, example-driven help for one command
    or REPL concept.
    """
    if topic:
        _show_topic_help(topic)
        return

    # ═══════════════════════════════════════════════════════════════════════
    # Tier 1 — Welcome + quick start
    # ═══════════════════════════════════════════════════════════════════════
    welcome_path = _REPL_HELP_DIR / "_welcome.txt"
    intro = Text.from_markup(welcome_path.read_text().strip())
    console.print(Panel(intro, border_style="muted", padding=(0, 2)))

    # ═══════════════════════════════════════════════════════════════════════
    # Tier 2 — Meta-commands
    # ═══════════════════════════════════════════════════════════════════════
    meta_table = Table(show_header=False, border_style="muted", padding=(0, 1))
    meta_table.add_column("cmd", style=f"bold {_st.theme.styles['info']}", width=16)
    meta_table.add_column("desc", style="muted")
    for cmd, desc in _parse_kv(_REPL_HELP_DIR / "_meta_commands.txt"):
        meta_table.add_row(cmd, desc)

    console.print(Panel(meta_table, title="REPL Commands", border_style="muted",
                        title_align="left", padding=(0, 2)))

    # ═══════════════════════════════════════════════════════════════════════
    # Tier 3 — Keyboard shortcuts
    # ═══════════════════════════════════════════════════════════════════════
    keys_table = Table(show_header=False, border_style="muted", padding=(0, 1))
    keys_table.add_column("key", style="bold", width=10)
    keys_table.add_column("action", style="muted")
    for key, action in _parse_kv(_REPL_HELP_DIR / "_keys.txt"):
        keys_table.add_row(key, action)

    console.print(Panel(keys_table, title="Keys", border_style="muted",
                        title_align="left", padding=(0, 2)))


def _show_topic_help(topic: str):
    """Display detailed help for *topic* in a Rich Panel.

    Looks up the topic in three places (in order):
    1.  ``repl/help/<topic>.txt`` — REPL-specific concepts
    2.  ``cli/help/<group>_<subcommand>.txt`` — CLI command help
    3.  Partial match — if *topic* is a group name, show its primary
        subcommand's help with a list of related subcommands.
    """
    cmd_map = get_cmd_map()

    # ── 1. REPL-specific concept help ──────────────────────────────────
    repl_path = _REPL_HELP_DIR / f"{topic}.txt"
    if repl_path.is_file():
        _display_help_panel(repl_path.read_text(), title=f"REPL: {topic}")
        return

    # ── 2. Exact match in CLI help ─────────────────────────────────────
    if topic in cmd_map:
        mapping = cmd_map[topic]
        cli_path = _cli_help_path(mapping)
        if cli_path and cli_path.is_file():
            _display_help_panel(cli_path.read_text(), title=topic)
            return
        # Fallback: generic description for commands without a help file
        console.print(f"[muted]No detailed help file for [accent]{topic}[/] yet.[/]")
        return

    # ── 3. Topic is a group name (e.g. "review", "sync") ──────────────
    # Show the primary subcommand's help + list related subcommands.
    group_subcommands = _find_subcommands_for_group(topic)
    if group_subcommands:
        primary = group_subcommands[0]
        primary_key = f"{topic} {primary}" if f"{topic} {primary}" in cmd_map else primary
        mapping = cmd_map.get(primary_key)
        if mapping:
            cli_path = _cli_help_path(mapping)
            if cli_path and cli_path.is_file():
                text = cli_path.read_text()
                extra_lines: list[str] = []
                if len(group_subcommands) > 1:
                    others = ", ".join(f"[accent]{s}[/]" for s in group_subcommands[1:])
                    extra_lines.append(f"\n\nOTHER {topic.upper()} COMMANDS\n  {others}\n")
                    extra_lines.append(f"\n  Type [accent]:help {topic} <cmd>[/] for any of the above.")
                _display_help_panel(text, title=topic, extra_markup=extra_lines)
                return

    # ── Not found ─────────────────────────────────────────────────────
    console.print(
        f"[warning]No help for [accent]{topic}[/]. "
        f"Try [accent]:help[/] (no argument) to see all commands.[/]"
    )


# ── Internal helpers ──────────────────────────────────────────────────────


def _cli_help_path(mapping: list[str]) -> Path | None:
    """Build the ``cli/help/`` file path for a cmd_map entry.

    ``["article", "create"]`` → ``cli/help/article_create.txt``
    ``["fork"]``              → ``cli/help/fork.txt``
    """
    if len(mapping) == 2:
        return _CLI_HELP_DIR / f"{mapping[0]}_{mapping[1]}.txt"
    elif len(mapping) == 1:
        return _CLI_HELP_DIR / f"{mapping[0]}.txt"
    return None


def _find_subcommands_for_group(group: str) -> list[str]:
    """Return subcommand names that belong to *group*, e.g. for ``"review"``
    returns ``["submit", "list", "reply", "invite", "accept", "decline", "rate"]``.
    """
    for name, _help, subcommands in COMMAND_GROUPS:
        if name == group:
            return [s[0] for s in subcommands if s[0]]
    return []


def _is_section_header(line: str) -> bool:
    """Return True if *line* looks like a section header (all caps, short)."""
    stripped = line.strip()
    if not stripped:
        return False
    # Must be at least 3 characters and contain at least one letter
    if len(stripped) < 3 or not any(c.isalpha() for c in stripped):
        return False
    # All characters must be uppercase, spaces, or punctuation
    return all(c.isupper() or c in " /-&()" for c in stripped)


def _render_help_text(text: str) -> Text:
    """Parse a CLI help ``.txt`` file into a Rich ``Text`` object.

    Rules (checked in order per line):
    1.  All-caps short line → bold ``info`` colour (section header)
    2.  Line starts with ``peerpedia`` (with optional indent) → ``accent``
    3.  Line starts with ``# →`` or ``#  `` (comment) → ``muted``
    4.  Flag-definition line (indented ``--flag …``) → bold the flag name
    5.  Everything else → default style

    A dim rule (``⋯⋯⋯``) is inserted between the boilerplate "HOW TO READ
    THIS HELP" block and the first real content section (EXAMPLES / FLAGS).
    """
    ACCENT = _st.theme.styles.get("accent", "bold")
    INFO = f"bold {_st.theme.styles.get('info', '')}"
    MUTED = _st.theme.styles.get("muted", "dim")

    out = Text()
    lines = text.split("\n")
    in_boilerplate = False
    boilerplate_ended = False

    for i, line in enumerate(lines):
        stripped = line.strip()

        # ── Inject separator after "HOW TO READ THIS HELP" block ──────
        if stripped == "HOW TO READ THIS HELP":
            in_boilerplate = True
        elif in_boilerplate and stripped == "EXAMPLES":
            in_boilerplate = False
            if not boilerplate_ended:
                boilerplate_ended = True
                out.append("─" * 60 + "\n", style=MUTED)

        # ── 1. Section header ─────────────────────────────────────────
        if _is_section_header(stripped):
            out.append(line + "\n", style=INFO)
            continue

        # ── 2. Command example ────────────────────────────────────────
        if stripped.startswith("peerpedia") or stripped.startswith("$ "):
            out.append(line + "\n", style=ACCENT)
            continue

        # ── 3. Comment line (# → or #   ) ─────────────────────────────
        if re.match(r"^ {2,}# (→|  )", line):
            out.append(line + "\n", style=MUTED)
            continue
        # Also catch un-indented # comments inside examples
        if re.match(r"^# (→|  )", line):
            out.append(line + "\n", style=MUTED)
            continue

        # ── 4. Flag definition line ───────────────────────────────────
        flag_match = re.match(r"^( +)(--\S+)(.*)", line)
        if flag_match:
            out.append(flag_match.group(1))            # leading spaces
            out.append(flag_match.group(2), style="bold")  # --flag
            out.append(flag_match.group(3) + "\n")     # rest of line
            continue

        # ── 5. Default ────────────────────────────────────────────────
        out.append(line + "\n")

    return out


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
    rendered = _render_help_text(text.strip())
    if extra_markup:
        for markup in extra_markup:
            rendered.append_text(Text.from_markup(markup))
    console.print(Panel(rendered, title=title, border_style="muted",
                        title_align="left", padding=(1, 2)))
