# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

r"""Interactive REPL for PeerPedia -- persistent session, same commands as CLI.

Usage::

    peerpedia repl          enter the REPL explicitly
    peerpedia               enter the REPL (when no subcommand given)

How it works
------------
::

    run()
      |-- _ensure_db()             persistent SQLite session (never closes
      |                             until REPL exits)
      |-- prompt_toolkit loop      blocks on session.prompt()
      |     |
      |     |-- user types "create --title ..."
      |     |-- _dispatch(cmd_str)
      |     |     |-- shlex.split  parse like a shell
      |     |     |-- cmd_map      flat command -> argparse group mapping
      |     |     |     "create" -> ["article", "create"]
      |     |     |     "review"  -> ["review"]
      |     |     |-- inject --user if sticky user set
      |     |     |-- build_parser().parse_args()
      |     |     |-- args.func(args)     same handler as CLI!
      |     |
      |     |-- periodic scan: if >1hr since last scan
      |           publish_ready_articles(db)

Key differences from CLI
------------------------
- **Persistent session**: One DB connection for the entire REPL session.
  CLI creates a new session per command.  This means ``db.commit()`` in
  the REPL commits ALL pending flushes from prior commands.
- **Sticky user**: ``:user alice`` sets a user that auto-injects ``--user``
  into every subsequent command.  No need to type ``--user`` every time.
- **Flat commands**: In the REPL you type ``create`` not ``article create``.
  The ``cmd_map`` dictionary translates flat names to argparse groups.
- **Periodic auto-publish**: After every command, the REPL checks if an
  hour has passed since the last scan and runs ``publish_ready_articles``.

Meta-commands
-------------
:help, :h       Show command reference
:user, :u       Set sticky user (e.g. ``:user alice``)
:quit, :q       Exit REPL

Reviewer's checklist
--------------------
- Are new CLI commands also registered in ``cmd_map`` and ``COMMANDS`` list?
- Does the periodic scan use ``_ensure_db()`` to get the session?
- Are exceptions caught and displayed without crashing the REPL?
"""

from __future__ import annotations

import shlex
import sys
import time
from pathlib import Path

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.history import FileHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.lexers import PygmentsLexer
from prompt_toolkit.styles import Style
from pygments.lexers.shell import BashLexer
from rich.console import Console
from rich.theme import Theme

from peerpedia_core.cli import build_parser
from peerpedia_core.cli.parser import get_cmd_map
from peerpedia_core.commands import get_user, get_user_by_name, publish_ready_articles
from peerpedia_core.storage.db import db_repl_setup

# ── Rich console (same theme as CLI) ─────────────────────────────────────

theme = Theme({
    "success": "bold green",
    "error": "bold red",
    "warning": "bold yellow",
    "info": "bold blue",
    "accent": "bold cyan",
    "muted": "dim",
})
console = Console(theme=theme)

# ── Database ─────────────────────────────────────────────────────────────

from peerpedia_core.config.params import params
from peerpedia_core.config.paths import DB_PATH, DB_URL, REPL_HISTORY_FILE

# ── Commands for tab completion ──────────────────────────────────────────

_META_COMMANDS = [":help", ":h", ":user", ":u", ":quit", ":q"]
COMMANDS = sorted(get_cmd_map().keys()) + _META_COMMANDS
FLAGS = ["--title", "--format", "--content", "--user", "--json", "--force",
         "--scores", "--comment", "--commit-hash", "--target", "--status",
         "--publish", "--no-editor", "--server"]

# ── REPL style ───────────────────────────────────────────────────────────

repl_style = Style.from_dict({
    "prompt": "#06B6D4 bold",     # cyan
    "separator": "#64748B",       # dim
})

# ── Session state ────────────────────────────────────────────────────────

_repl_user: str | None = None
_repl_db = None


def _ensure_db():
    global _repl_db
    if _repl_db is None:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        _repl_engine, _repl_db = db_repl_setup(DB_URL)
    return _repl_db


def _prompt_text():
    user = _repl_user or "guest"
    return [
        ("class:prompt", f"{user}"),
        ("class:separator", "> "),
    ]


# ── Meta-commands ────────────────────────────────────────────────────────


def _meta_help():
    console.print("""
[bold info]Commands[/] (same as CLI, without 'peerpedia' prefix):

[bold]Account[/]   register --name <name>   |  whoami
[bold]Article[/]   create --title <t> --format <md|typst> [--content <c>]
           show <id>   |  list [--status <s>]
           edit <id> --content <c>  |  delete <id> --force
           publish <id> --scores <s>
[bold]Review[/]    submit <article-id> --scores <s> [--comment <c>]
           list <article-id>
[bold]Fork[/]      fork <article-id>
[bold]Merge[/]     propose <fork-id> --target <original-id>
           accept <proposal-id> --target <article-id>
[bold]Bookmark[/]  add <article-id>  |  list
[bold]Sync[/]      status  |  push

[bold]Meta[/]      :user <name>  → set sticky user
           :help          → show this
           :quit          → exit

Flags: [muted]--json --user ...  (same as CLI)[/]
""")


def _meta_user(name):
    global _repl_user
    db = _ensure_db()
    u = get_user(db, name)
    if u is None:
        users = get_user_by_name(db, name)
        if len(users) == 1:
            u = users[0]
        elif len(users) > 1:
            console.print(f"[warning]Multiple users named '{name}':[/]")
            for i, user in enumerate(users, 1):
                console.print(f"  {i}. {user.id} ({user.affiliation or 'no affiliation'})")
            console.print("Use [accent]/user <id>[/] to select a specific user.")
            return
    if u:
        _repl_user = name
        console.print(f"[success]✓[/] User set to [accent]{name}[/]")
    else:
        console.print(f"[error]✗[/] User '{name}' not found. Register: register --name {name}")


# ── Command dispatch ─────────────────────────────────────────────────────


def _dispatch(cmd_str: str) -> bool:
    """Parse and execute a single command. Returns False to exit REPL."""
    cmd_str = cmd_str.strip()
    if not cmd_str:
        return True

    # Meta-commands
    if cmd_str.startswith(":"):
        parts = cmd_str.split(maxsplit=1)
        meta = parts[0]
        arg = parts[1] if len(parts) > 1 else ""
        if meta == ":quit" or meta == ":q":
            return False
        elif meta == ":help" or meta == ":h":
            _meta_help()
            return True
        elif meta == ":user" or meta == ":u":
            _meta_user(arg.strip())
            return True
        else:
            console.print(f"[error]Unknown meta-command: {meta}[/]. Try :help")
            return True

    # Inject --user if sticky user is set and not already provided
    first_word = cmd_str.split()[0] if cmd_str.split() else ""
    if _repl_user and "--user" not in cmd_str and first_word not in ("register", ":help", ":user", ":quit", ":q", ":h", ":u", "whoami"):
        cmd_str += f" --user {_repl_user}"

    # Map CLI subcommands to their argparse group.
    # Built from parser.py's COMMAND_GROUPS+TOP_LEVEL — single source of truth.
    cmd_map = get_cmd_map()

    try:
        args_list = shlex.split(cmd_str)
    except ValueError as e:
        console.print(f"[error]✗ Parse error: {e}[/]")
        return True

    if not args_list:
        return True

    cmd = args_list[0]
    if cmd not in cmd_map:
        console.print(f"[error]✗ Unknown command: {cmd}[/]. Try :help")
        return True

    # Build the full CLI argv: peerpedia <group> <subcmd> <args...>
    mapping = cmd_map[cmd]
    argv = ["peerpedia"] + mapping + args_list[1:]

    try:
        # Suppress argparse error output
        import io
        old_stderr = sys.stderr
        sys.stderr = io.StringIO()
        try:
            args = parser.parse_args(argv[1:])  # skip "peerpedia" in argv
        except SystemExit:
            # argparse calls sys.exit on --help or errors
            console.print("[muted](type :help for available commands)[/]")
            return True
        finally:
            sys.stderr = old_stderr

        if hasattr(args, "func"):
            args.func(args)
        else:
            parser.print_help()
    except Exception as e:
        console.print(f"[error]✗ {e}[/]")

    return True


# ── Entry point ──────────────────────────────────────────────────────────


def run():
    """Start the interactive REPL."""
    console.print("[bold info]PeerPedia REPL[/]")
    console.print("[muted]Type :help for commands, :quit to exit.[/]")
    console.print()

    REPL_HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)

    completer = WordCompleter(COMMANDS + FLAGS, ignore_case=True, sentence=True)

    # Shift+Enter to submit, plain Enter to insert newline (like Mathematica).
    kb = KeyBindings()

    @kb.add("enter")
    def _(event):
        event.current_buffer.insert_text("\n")

    @kb.add("s-enter")
    def _(event):
        event.current_buffer.validate_and_handle()

    session = PromptSession(
        history=FileHistory(str(REPL_HISTORY_FILE)),
        completer=completer,
        style=repl_style,
        mouse_support=True,
        key_bindings=kb,
        lexer=PygmentsLexer(BashLexer),
    )

    _last_scan = 0.0

    try:
        while True:
            try:
                cmd = session.prompt(_prompt_text())
            except KeyboardInterrupt:
                console.print("\n[muted](Ctrl-D to exit)[/]")
                continue
            except EOFError:
                console.print("\n[muted]Bye.[/]")
                break

            should_continue = _dispatch(cmd)

            # Periodic scan: check for publishable articles
            now = time.time()
            if now - _last_scan > params.sink.scan_interval_seconds:
                db = _ensure_db()
                count = publish_ready_articles(db)
                db.commit()
                if count > 0:
                    console.print(f"[info]{count} 篇文章已自动发布[/]")
                _last_scan = now

            if not should_continue:
                console.print("[muted]Bye.[/]")
                break
    finally:
        if _repl_db is not None:
            _repl_db.close()
