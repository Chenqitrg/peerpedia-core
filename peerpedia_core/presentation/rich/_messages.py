# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""User-facing message strings and Rich text helpers — pure data, zero IO."""

from __future__ import annotations

from rich.text import Text

# ── Error display ────────────────────────────────────────────────────────

def error_lines(msg: str, *, suggestion: str = "",
                see_also: tuple[str, ...] = ()) -> list[str]:
    lines = [f"[error]✗ {msg}[/]"]
    if suggestion: lines.append(f"\n  [dim]→ {suggestion}[/]")
    if see_also: lines.append(f"  [muted]See also: {' · '.join(see_also)}[/]")
    return lines

# ── Theme ────────────────────────────────────────────────────────────────

def theme_label(name: str) -> str:
    return {"ember": "🌙  Ember (dark) theme.", "parchment": "☀   Parchment (light) theme."}.get(name, "")

def theme_unknown(mode: str) -> str:
    return f"[warning]Unknown theme '{mode}'. Use [accent]light[/] or [accent]dark[/].[/]"

# ── REPL ─────────────────────────────────────────────────────────────────

_REPL_TTY_REQUIRED = "\n".join([
    "[bold]PeerPedia REPL[/] requires a terminal.",
    "Use [accent]peerpedia <command>[/] for scripting, or [accent]peerpedia --help[/] for the command list.",
])

def repl_tty_required() -> str: return _REPL_TTY_REQUIRED
def repl_interrupt_msg() -> str: return "\n[muted](Ctrl-D to exit)[/]"
def repl_bye_msg() -> str: return "\n[muted]Bye.[/]"
def repl_cancelled_msg() -> str: return "\n[muted]Cancelled.[/]"
def repl_parse_error(e: object) -> str: return f"[error]✗ Parse error: {e}[/]"
def repl_unknown_cmd(cmd: str) -> str: return f"[error]✗ Unknown command: {cmd}[/]. Try :help"
def repl_unavailable_cmd(cmd_id: str) -> str: return f"[muted]{cmd_id} is not available in REPL.[/]"
def repl_internal_error(e: object) -> str: return f"[error]✗ Internal error: {e}[/]"

# ── CLI ──────────────────────────────────────────────────────────────────

# ── Banner / guest ───────────────────────────────────────────────────────

def banner_subtitle() -> str: return "  scholarly terminal"

def banner_keyboard_hints() -> str:
    return "[dim]Enter submit  ·  Ctrl+J newline  ·  :help commands  ·  :quit exit[/]"

def guest_hint(*, cli: bool = False) -> str:
    if cli:
        return "[muted]Not logged in.  [accent]peerpedia account register --name <your-name>[/] to begin.[/]"
    return "[muted]Not logged in.  [accent]register --name <name>[/] to begin.[/]"

def sink_progress_label(bar: str, remaining_days: int, muted_style: str) -> str:
    return f"  [{muted_style}]{bar}[/] {remaining_days}d left"

# ── Rich text ────────────────────────────────────────────────────────────

def greeting_banner(accent_style: str, info_style: str) -> Text:
    g = Text()
    g.append("✧ ", style=accent_style)
    g.append("PeerPedia", style=f"bold {info_style}")
    return g
