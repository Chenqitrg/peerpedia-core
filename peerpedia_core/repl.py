# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Interactive REPL for PeerPedia.

Usage:
    peerpedia repl          → enter the REPL explicitly
    peerpedia               → enter the REPL (when no subcommand given)

Features:
    - Persistent DB session across commands
    - Sticky user (use :user to switch, no need to --user every time)
    - Full argparse under the hood — same commands, same flags
    - History, tab completion, syntax highlighting (prompt_toolkit)
"""

from __future__ import annotations

import shlex
import sys
from pathlib import Path

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.history import FileHistory
from prompt_toolkit.lexers import PygmentsLexer
from prompt_toolkit.styles import Style
from pygments.lexers.shell import BashLexer
from rich.console import Console
from rich.theme import Theme

from peerpedia_core.cli import build_parser
from peerpedia_core.storage.db.engine import get_engine, get_session, init_db

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

DB_PATH = Path.home() / ".peerpedia" / "peerpedia.db"
DB_URL = f"sqlite:///{DB_PATH}"

# ── Commands for tab completion ──────────────────────────────────────────

COMMANDS = [
    "register", "whoami",
    "create", "show", "list", "edit", "publish", "delete",
    "review", "fork", "merge", "bookmark",
    "search", "compile", "sync",
    ":help", ":user", ":quit",
]
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
        engine = get_engine(DB_URL)
        init_db(engine)
        _repl_db = get_session(engine)
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
    from peerpedia_core.storage.db.crud_user import get_user, get_user_by_name

    db = _ensure_db()
    u = get_user(db, name) or get_user_by_name(db, name)
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

    # Map CLI subcommands to their argparse group
    # The REPL uses flat commands: "create" maps to "article create"
    cmd_map = {
        "register": ["account", "register"],
        "whoami": ["account", "whoami"],
        "create": ["article", "create"],
        "show": ["article", "show"],
        "list": ["article", "list"],
        "edit": ["article", "edit"],
        "publish": ["article", "publish"],
        "delete": ["article", "delete"],
        "review": ["review"],
        "fork": ["fork"],
        "merge": ["merge"],
        "bookmark": ["bookmark"],
        "search": ["search"],
        "compile": ["compile"],
        "sync": ["sync"],
    }

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
        parser = build_parser()
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

    history_file = Path.home() / ".peerpedia" / ".repl_history"
    history_file.parent.mkdir(parents=True, exist_ok=True)

    completer = WordCompleter(COMMANDS + FLAGS, ignore_case=True, sentence=True)

    session = PromptSession(
        history=FileHistory(str(history_file)),
        completer=completer,
        style=repl_style,
        lexer=PygmentsLexer(BashLexer),
    )

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
            if not should_continue:
                console.print("[muted]Bye.[/]")
                break
    finally:
        if _repl_db is not None:
            _repl_db.close()
