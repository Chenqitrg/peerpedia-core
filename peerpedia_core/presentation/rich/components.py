# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Shared Rich rendering components — pure display, zero side effects.

Every function takes a *console* parameter so both CLI and REPL can pass
their own ``rich.console.Console`` instance.  No module-level console.

Architecture: imports only from foundation (``types/``, ``messages``, stdlib).
Never from ``cli/``, ``repl/``, ``app/``, ``core/``, ``storage/``, or ``server/``.
"""

from __future__ import annotations

from rich.console import Console
from rich.markup import escape as _escape
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from peerpedia_core.messages import lookup as _msg
from peerpedia_core.types.entities import ArticleMetaExchange, UserExchange
from peerpedia_core.types.scores import SCORE_DIMENSIONS


# ── Score dimensions ─────────────────────────────────────────────────────────

SCORE_DIM_NAMES: list[str] = list(SCORE_DIMENSIONS.values())


# ── Scores ───────────────────────────────────────────────────────────────────

def score_lines(score: dict | None, dims: list[str] | None = None) -> list[str]:
    """Return one plain-text line per dimension, e.g. ``'originality    ★★★☆☆  3/5'``."""
    if not score:
        return ["—"]
    if dims is None:
        dims = SCORE_DIM_NAMES
    return [
        f"  {d:<{_DIM_LABEL_WIDTH}} {'★'*v}{'☆'*(max_val-v)}  {v}/{max_val}"
        for d in dims
        for v in [int(score.get(d, 0))]
        for max_val in [_MAX_SCORE]
    ]


def score_stars(score: dict | None, dims: list[str] | None = None) -> str:
    """Render 5-dim scores with Rich markup, e.g. ``[accent]★★★★☆[/][muted]☆[/]  4/5``."""
    if not score:
        return "[muted]no score[/]"
    if dims is None:
        dims = SCORE_DIM_NAMES
    max_val = _MAX_SCORE
    return "\n".join(
        f"  {d:<{_DIM_LABEL_WIDTH}} [accent]{'★'*v}[/][muted]{'☆'*(max_val-v)}[/]  {v}/{max_val}"
        for d in dims
        for v in [int(score.get(d, 0))]
    )


_COMMIT_HASH_LEN = 7       # standard git abbreviation
_STATUS_LABEL_LEN = 4       # status abbreviation chars (e.g. 'DRAF')
_PUBKEY_PREVIEW_LEN = 16    # public key preview chars
_TIMESTAMP_PREVIEW_LEN = 16 # ISO timestamp preview chars ('2026-01-15 09:30')
_DIM_LABEL_WIDTH = 14       # score dimension label column width
_MAX_SCORE = 5              # max score value for star ratings


def abbrev_commit(hash_str: str) -> str:
    """Abbreviate a git commit hash, e.g. ``'abc1234'``."""
    return hash_str[:_COMMIT_HASH_LEN]


_NO_RATING = "  —  "


def star_string(value: int, max_val: int = _MAX_SCORE) -> str:
    """Plain-text star rating, e.g. ``'★★★☆☆'``."""
    return f"{'★' * value}{'☆' * (max_val - value)}"


def no_rating_stars() -> str:
    """Placeholder string for empty rating: '  —  '."""
    return _NO_RATING


def status_label(status: str | None) -> str:
    """Short status label, e.g. ``'DRAF'``.  Unknown → ``'?'``."""
    return status[:_STATUS_LABEL_LEN].upper() if status else "?"


def progress_bar(filled: int, total: int) -> str:
    """Plain-text progress bar, e.g. ``'████░░'``."""
    return "█" * filled + "░" * (total - filled)


def sink_progress_label(bar: str, remaining_days: int, muted_style: str) -> str:
    """Rich-markup sedimentation progress, e.g. '  [muted]████░░[/] 4d left'."""
    return f"  [{muted_style}]{bar}[/] {remaining_days}d left"


def theme_label(name: str) -> str:
    """Human-readable theme label: 'ember' → '🌙  Ember (dark) theme.'."""
    return {"ember": "🌙  Ember (dark) theme.", "parchment": "☀   Parchment (light) theme."}.get(name, "")


def theme_unknown(mode: str) -> str:
    """Rich-markup message for unknown theme name."""
    return f"[warning]Unknown theme '{mode}'. Use [accent]light[/] or [accent]dark[/].[/]"


def inbox_empty_msg() -> str:
    return _msg("EMPTY_NOTIFICATIONS")[1].text


def no_articles_msg() -> str:
    return _msg("EMPTY_ARTICLES")[1].text


def no_users_msg() -> str:
    return "[muted]No users found.[/]"


def no_reviews_msg() -> str:
    return _msg("EMPTY_REVIEWS")[1].text


def user_found_msg(u) -> str:
    """Rich-markup: user successfully resolved."""
    return f"[success]✓[/] UserStorage set to [accent]{u.name}[/] [muted]({u.id})[/]"


def user_not_found_msg(name: str) -> str:
    """Rich-markup: user not found with registration hint."""
    return f"[error]✗[/] UserStorage '{name}' not found. [muted]register --name {name}[/] to create.[/]"


def user_ambiguous_hint() -> str:
    """Rich-markup: hint to pick from multiple matching users."""
    return "[muted]Use [accent]:user <id prefix>[/] to pick.[/]"


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


_SEARCH_PREVIEW_LIMIT = 20  # max candidates to show on ambiguity


def article_search_feedback(ref: str, candidates: list) -> str | None:
    """Rich-markup feedback for article search results.  None if exactly 1 match."""
    if not candidates:
        return f"[error]✗[/] ArticleMetaStorage '{ref}' not found."
    if len(candidates) > 1:
        lines = [f"[warning]{len(candidates)} articles match '{ref}':[/]"]
        for a in candidates[:_SEARCH_PREVIEW_LIMIT]:
            lines.append(f"  {a.id}  {a.title}")
        return "\n".join(lines)
    return None  # exactly one match — caller handles


def error_lines(msg: str, *, suggestion: str = "",
                see_also: tuple[str, ...] = ()) -> list[str]:
    """Rich-markup error display lines: '✗ msg' + optional hints."""
    lines = [f"[error]✗ {msg}[/]"]
    if suggestion:
        lines.append("")
        lines.append(f"  [dim]→ {suggestion}[/]")
    if see_also:
        lines.append(f"  [muted]See also: {' · '.join(see_also)}[/]")
    return lines


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


def auto_publish_msg(count: int) -> str:
    """Rich-markup: N article(s) auto-published.  Delegates to message registry."""
    return _msg("ARTICLE_SCANNED")[1].text.format(count=count)


_REPL_TTY_REQUIRED = "\n".join([
    "[bold]PeerPedia REPL[/] requires a terminal.",
    "Use [accent]peerpedia <command>[/] for scripting, "
    "or [accent]peerpedia --help[/] for the command list.",
])


def repl_tty_required() -> str:
    """Rich-markup: REPL requires a TTY."""
    return _REPL_TTY_REQUIRED


def repl_interrupt_msg() -> str:
    """Rich-markup: Ctrl-C hint."""
    return "\n[muted](Ctrl-D to exit)[/]"


def repl_bye_msg() -> str:
    """Rich-markup: exit message."""
    return "\n[muted]Bye.[/]"


def repl_cancelled_msg() -> str:
    """Rich-markup: cancelled."""
    return "\n[muted]Cancelled.[/]"


def repl_parse_error(e: object) -> str:
    """Rich-markup: parse error."""
    return f"[error]✗ Parse error: {e}[/]"


def repl_unknown_cmd(cmd: str) -> str:
    """Rich-markup: unknown command."""
    return f"[error]✗ Unknown command: {cmd}[/]. Try :help"


def repl_unavailable_cmd(cmd_id: str) -> str:
    """Rich-markup: command not available in REPL."""
    return f"[muted]{cmd_id} is not available in REPL.[/]"


def repl_internal_error(e: object) -> str:
    """Rich-markup: internal error."""
    return f"[error]✗ Internal error: {e}[/]"


def cli_compiling_msg() -> str:
    """Rich-markup: compiling status."""
    return "[info]Compiling...[/]"


def cli_no_users_msg(query: str) -> str:
    return _msg("EMPTY_SEARCH")[1].text.format(query=query)


def unknown_meta_cmd_msg(meta: str) -> str:
    """Rich-markup: unknown meta-command."""
    return f"[error]Unknown meta-command: {meta}[/]. Try :help"


def compact_mode_msg(mode: str) -> str:
    """Rich-markup: output mode change."""
    return f"[muted]Output mode: {mode}.[/]"


def greeting_banner(accent_style: str, info_style: str) -> Text:
    """Rich Text banner: '✧ PeerPedia'."""
    g = Text()
    g.append("✧ ", style=accent_style)
    g.append("PeerPedia", style=f"bold {info_style}")
    return g


def banner_subtitle() -> str:
    """Plain text: 'scholarly terminal'."""
    return "  scholarly terminal"


def banner_keyboard_hints() -> str:
    """Rich-markup: REPL keyboard shortcuts footer."""
    return "[dim]Enter submit  ·  Ctrl+J newline  ·  :help commands  ·  :quit exit[/]"


def guest_hint(*, cli: bool = False) -> str:
    """Rich-markup login hint shared by CLI and REPL.

    REPL uses the short form (``register``), CLI uses the full form
    (``peerpedia account register``)."""
    if cli:
        return "[muted]Not logged in.  [accent]peerpedia account register --name <your-name>[/] to begin.[/]"
    return "[muted]Not logged in.  [accent]register --name <name>[/] to begin.[/]"


# ── Badges ───────────────────────────────────────────────────────────────────

def status_badge(status: str) -> str:
    """Colored status label: draft=white, sedimentation=yellow, published=green."""
    colors = {"draft": "white", "sedimentation": "yellow", "published": "green"}
    return f"[{colors.get(status, 'white')}]{status}[/]"


# ── Tables & panels ──────────────────────────────────────────────────────────

_USER_TABLE_RANK_W = 3
_USER_TABLE_ID_W = 10
_NOTIF_TABLE_TIME_W = 16


def user_list_table(users, *, title: str = "") -> Table:
    """Build a user picker table: #, ID, Affiliation."""
    t = Table(title=title, border_style="muted")
    t.add_column("#", style="muted", width=_USER_TABLE_RANK_W)
    t.add_column("ID", style="accent", width=_USER_TABLE_ID_W)
    t.add_column("Affiliation", style="muted")
    for i, u in enumerate(users, 1):
        t.add_row(str(i), u.id, u.affiliation or "—")
    return t


def notification_table(notifications, *, title: str = "Notifications") -> Table:
    """Build a notification list table: Time, Event."""
    t = Table(title=title, border_style="muted")
    t.add_column("Time", style="muted", width=_NOTIF_TABLE_TIME_W)
    t.add_column("Event", style="accent")
    for n in notifications:
        ts_raw = n.get("created_at", "")
        ts = ts_raw[:_TIMESTAMP_PREVIEW_LEN].replace("T", " ") if ts_raw else ""
        marker = "[bold]●[/] " if not n.get("read") else "  "
        t.add_row(ts, f"{marker}{n.get('message', '')}")
    return t


def data_table(headers: list[str], rows: list[list], *,
               title: str | None = None) -> Table:
    """Build a generic data table from headers and rows."""
    t = Table(title=title, border_style="muted")
    for i, h in enumerate(headers):
        t.add_column(str(h), style="bold" if i == 0 else "")
    for row in rows:
        t.add_row(*[str(v) for v in row])
    return t


def user_line_text(u: dict) -> Text:
    """Build a single-line Rich Text renderable for a user dict."""
    uid = u.get("id") or u.get("user_id", "?")
    affiliation = f" · {u['affiliation']}" if u.get("affiliation") else ""
    return Text(f"{u.get('name', '?')} ({uid}){affiliation}")


def user_panels(console: Console, items: list[UserExchange]) -> None:
    """Render a list of UserExchange objects as Rich panels."""
    for u in items:
        display_user(
            console,
            u.name,
            u.id,
            affiliation=u.address,
            reputation=u.reputation,
        )


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


def diff_panel(console: Console, diff_text: str, stats: dict) -> None:
    """Render a unified diff with GitHub-style colorization."""
    totals = stats.get("total", {})
    ins = totals.get("insertions", 0)
    dels = totals.get("deletions", 0)
    files = stats.get("files", [])

    header = Text()
    if files:
        header.append(", ".join(files), style="bold")
        header.append("  ")
    header.append(f"+{ins}", style="success")
    header.append("  ")
    header.append(f"-{dels}", style="error")
    console.print()
    console.print(Panel(header, title="Diff", border_style="muted", title_align="left"))
    console.print()

    for line in diff_text.split("\n"):
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


def print_table(console: Console, headers: list[str], rows: list[list[str]],
                title: str | None = None) -> None:
    """Render a list of rows as a Rich Table."""
    table = Table(title=title, border_style="muted")
    for i, h in enumerate(headers):
        table.add_column(h, style="bold" if i == 0 else "")
    for row in rows:
        table.add_row(*[str(v) for v in row])
    console.print(table)


def print_panel(console: Console, title: str, content: str | Text,
                border_style: str = "muted") -> None:
    """Show a single item's details in a bordered panel."""
    console.print(Panel(content, title=title, border_style=border_style,
                        title_align="left"))


# ── Page-mode rendering ───────────────────────────────────────────────────────


_BORDER_FOCUSED = "bold cyan"


def focused_panel(console: Console, title: str, content: str | Text,
                  *, is_focused: bool = False) -> None:
    """Print a panel with focus indicator (left bar) when selected."""
    border = _BORDER_FOCUSED if is_focused else "muted"
    console.print(Panel(content, title=title, border_style=border,
                        title_align="left"))


# ── User display ─────────────────────────────────────────────────────────────

def display_user(console: Console, name: str, user_id: str, *,
                 affiliation: str = "",
                 expertise: list[str] | None = None,
                 reputation: dict | None = None,
                 follower_count: int | None = None,
                 public_key: str | None = None,
                 created_at: str | None = None) -> None:
    """Render user metadata panel — pure display, zero side effects."""
    body = Text()
    body.append(str(name), style="bold info")
    if follower_count is not None:
        body.append(f"      {follower_count} follower(s)", style="muted")
    body.append(f"\n{user_id}", style="accent")
    if public_key:
        body.append(f"\nPublic key: {public_key[:_PUBKEY_PREVIEW_LEN]}…", style="dim")
    if affiliation:
        body.append("\nAffiliation: ")
        body.append(str(affiliation), style="info")
    if expertise:
        body.append(f"\nExpertise: {', '.join(_escape(str(e)) for e in expertise)}")
    if reputation:
        body.append("\nReputation:\n")
        body.append(Text.from_markup(score_stars(reputation)))
    if created_at:
        body.append(f"\nCreated: {created_at}", style="dim")
    print_panel(console, "User", body)


# ── Help text rendering ──────────────────────────────────────────────────────


_MIN_SECTION_HEADER_LEN = 3


def _is_section_header(stripped: str) -> bool:
    """All-caps short line = section header."""
    if len(stripped) < _MIN_SECTION_HEADER_LEN or not any(c.isalpha() for c in stripped):
        return False
    return all(c.isupper() or c in " /-&()" for c in stripped)


_COMMENT_INDENT = 2  # minimum spaces before # comment in help text


def style_help_line(line: str, stripped: str, accent_style: str,
                    info_style: str, muted_style: str) -> list[tuple[str, str]]:
    """Apply help-text styling rules to a single line.

    Returns (style, text) pairs.  Empty list = use default style.
    """
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
    """Rich-markup: no help found for topic."""
    return (
        f"[warning]No help for [accent]{topic}[/]. "
        f"Try [accent]:help[/] (no argument) to see all commands.[/]"
    )


def help_group_extra_lines(topic: str, others: list[str]) -> list[str]:
    """Rich-markup extra lines for 'OTHER … COMMANDS' in group help."""
    names = ", ".join(f"[accent]{s}[/]" for s in others)
    return [
        f"\n\nOTHER {topic.upper()} COMMANDS\n  {names}\n",
        f"\n  Type [accent]:help {topic} <cmd>[/] for any of the above.",
    ]


_HELP_SEPARATOR_WIDTH = 60


def render_help_text(text: str, accent: str, info: str, muted: str) -> Text:
    """Parse a CLI help .txt file into a Rich Text object with styled lines."""
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
