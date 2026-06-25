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
from prompt_toolkit.application import Application
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.history import FileHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import HSplit, Layout, VSplit, Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.lexers import PygmentsLexer
from prompt_toolkit.styles import Style
from pygments.lexers.shell import BashLexer
from rich.console import Console
from rich.theme import Theme

from peerpedia_core.cli.parser import get_cmd_map
from peerpedia_core.commands import get_user, get_user_by_name, list_articles, publish_ready_articles
from peerpedia_core.storage.db import db_repl_setup
from peerpedia_core.storage.db.models import Article

# Lazy imports to avoid circular dependency (cli/__init__.py imports repl.run).
_build_parser = None
_stars = None


def _get_parser():
    global _build_parser
    if _build_parser is None:
        from peerpedia_core.cli import build_parser as bp
        _build_parser = bp
    return _build_parser()


def _get_stars():
    global _stars
    if _stars is None:
        from peerpedia_core.cli.display import _stars as s
        _stars = s
    return _stars

# ── Rich console (same theme as CLI) ─────────────────────────────────────

_PARCHMENT_THEME = Theme({
    "success": "#777C5C bold",    # olive
    "error": "#B84040 bold",      # brick red
    "warning": "#D4893C bold",    # amber
    "info": "#A85F3B bold",       # primary terracotta
    "accent": "#B08A57 bold",     # gold-brown
    "muted": "#6F665E dim",       # warm gray
})

_EMBER_THEME = Theme({
    "success": "#8F9A82 bold",    # sage
    "error": "#CC5544 bold",      # ember red
    "warning": "#D4A03C bold",    # golden amber
    "info": "#D18462 bold",       # primary rose
    "accent": "#B89A66 bold",     # dark gold
    "muted": "#BDB3A6 dim",       # warm gray (night)
})

_PARCHMENT_STYLE = Style.from_dict({
    "prompt": "#A85F3B bold",
    "separator": "#D8CBBB",
})

_EMBER_STYLE = Style.from_dict({
    "prompt": "#D18462 bold",
    "separator": "#454037",
})

theme = _PARCHMENT_THEME
repl_style = _PARCHMENT_STYLE
console = Console(theme=theme)

# ── Database ─────────────────────────────────────────────────────────────

from peerpedia_core.config.params import params
from peerpedia_core.config.paths import DB_PATH, DB_URL, REPL_HISTORY_FILE

# ── Commands for tab completion ──────────────────────────────────────────

_META_COMMANDS = [":help", ":h", ":user", ":u", ":article", ":a", ":theme",
                  ":feed", ":school", ":inbox", ":quit", ":q"]
COMMANDS = sorted(get_cmd_map().keys()) + _META_COMMANDS
FLAGS = ["--title", "--format", "--content", "--user", "--json", "--rich", "--force",
         "--scores", "--comment", "--commit-hash", "--target", "--status",
         "--publish", "--no-editor", "--server"]

# ── Session state ────────────────────────────────────────────────────────

_repl_user: str | None = None
_repl_article_id: str | None = None
_repl_article_title: str = ""  # cached for prompt display
_repl_article_commit: str = ""  # latest commit hash (arXiv-style identifier)
_repl_theme: str = "parchment"  # "parchment" | "ember"
_repl_db = None


def _ensure_db():
    global _repl_db
    if _repl_db is None:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        _repl_engine, _repl_db = db_repl_setup(DB_URL)
    return _repl_db


def _prompt_text():
    user = _repl_user or "guest"
    # Notification badge
    try:
        from peerpedia_core.cli.helpers import _read_session
        from peerpedia_core.commands import count_unread_notifications
        db = _ensure_db()
        sid = _read_session()
        if sid:
            unread = count_unread_notifications(db, sid["user_id"])
            badge = f" ({unread})" if unread > 0 else ""
        else:
            badge = ""
    except Exception:
        badge = ""
    parts = [("class:prompt", f"{user}{badge}")]
    if _repl_article_id:
        label = _repl_article_title or _repl_article_id[:8]
        parts.append(("class:separator", f" ▸ {label}"))
        if _repl_article_commit:
            parts.append(("class:separator", f" @{_repl_article_commit[:7]}"))
    parts.append(("class:separator", "> "))
    return parts


# ── Meta-commands ────────────────────────────────────────────────────────


def _meta_help():
    console.print(f"""
[bold {theme.styles['info']}]▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔[/]
[bold]Commands[/] [muted](same as CLI, without 'peerpedia' prefix)[/]

[bold {theme.styles['accent']}]Account[/]   register --name <name>   |  whoami
[bold {theme.styles['accent']}]Article[/]  create --title <t> [--content <c>]
         show <id>  |  list [--status <s>]  |  edit <id>
         publish <id> --scores <s>  |  delete <id>
[bold {theme.styles['accent']}]Review[/]   submit <id> --scores <s> [--comment <c>]
         list <id>  |  reply <id> --to <user>  |  invite <id> --user <u>
[bold {theme.styles['accent']}]Social[/]   follow @name  |  unfollow @name  |  school
         bookmark add <id>  |  share add <id>
[bold {theme.styles['accent']}]Sync[/]     status  |  push  |  pull  |  discover
[bold {theme.styles['accent']}]Fork[/]     fork <id>
[bold {theme.styles['accent']}]Merge[/]    propose <fork> --target <target>
         accept <proposal> --target <id>  |  withdraw <proposal>

[bold {theme.styles['info']}]Meta[/]      :user <name>  → set sticky user
         :article <ref> → set article context
         :feed          → your feed
         :school        → user leaderboard
         :inbox         → notifications
         :theme <l|d>    → light / dark mode
         :help          → show this
         :quit, :q      → exit

[muted]Ctrl+J to submit, Enter for newline.  Type --json for machine output.[/]
""")


def _meta_user(name):
    global _repl_user
    db = _ensure_db()
    # Try exact ID or prefix match first
    u = get_user(db, name)
    if u is None:
        users = get_user_by_name(db, name)
        if len(users) == 1:
            u = users[0]
        elif len(users) > 1:
            from rich.table import Table
            t = Table(title=f"Multiple users matching '{name}'", border_style="muted")
            t.add_column("#", style="muted", width=3)
            t.add_column("ID", style="accent", width=10)
            t.add_column("Affiliation", style="muted")
            for i, user in enumerate(users, 1):
                t.add_column(str(i), user.id[:8], user.affiliation or "—")
            console.print(t)
            console.print(f"[muted]Use [accent]:user <id prefix>[/] to pick.  Example: :user {users[0].id[:8]}[/]")
            return
    if u:
        _repl_user = name
        console.print(f"[success]✓[/] User set to [accent]{u.name}[/] [muted]({u.id[:8]})[/]")
    else:
        console.print(f"[error]✗[/] User '{name}' not found. [muted]register --name {name}[/] to create.[/]")


def _meta_article(ref: str):
    """Set or clear the current article context.  ``:article <ref>`` sets,
    ``:article`` (no argument) clears."""
    global _repl_article_id, _repl_article_title, _repl_article_commit
    db = _ensure_db()
    if not ref:
        _repl_article_id = None
        _repl_article_title = ""
        _repl_article_commit = ""
        console.print("[muted]Article context cleared.[/]")
        return
    article = db.query(Article).filter(
        (Article.id == ref) | (Article.id.startswith(ref))
    ).first()
    if article is None:
        articles = list_articles(db, search_query=ref, limit=5)
        if len(articles) == 1:
            article = articles[0]
        elif len(articles) > 1:
            console.print(f"[warning]Multiple matches for '{ref}':[/]")
            for a in articles:
                console.print(f"  {a.id[:8]}  {a.title}")
            return
    if article:
        _repl_article_id = article.id
        _repl_article_title = article.title
        # Fetch latest commit hash (arXiv-style identifier).
        try:
            from peerpedia_core.storage.git_backend import DEFAULT_ARTICLES_DIR, get_head_hash
            rp = DEFAULT_ARTICLES_DIR / article.id
            if (rp / ".git").is_dir():
                _repl_article_commit = get_head_hash(rp)
            else:
                _repl_article_commit = ""
        except Exception:
            _repl_article_commit = ""
        commit_str = f" @{_repl_article_commit[:7]}" if _repl_article_commit else ""
        console.print(f"[success]▸[/] [accent]{article.title}[/] [muted]({article.id[:8]}{commit_str})[/]")
    else:
        console.print(f"[error]✗[/] Article '{ref}' not found.")


def _meta_theme(mode: str):
    """Switch between parchment (light) and ember (dark) themes."""
    global theme, repl_style, _repl_theme
    mode = mode.strip().lower() or "parchment"
    if mode in ("dark", "ember", "night"):
        theme = _EMBER_THEME
        repl_style = _EMBER_STYLE
        _repl_theme = "ember"
        console.push_theme(theme)
        console.print("[muted]🌙  Ember (dark) theme.[/]")
    elif mode in ("light", "parchment", "day"):
        theme = _PARCHMENT_THEME
        repl_style = _PARCHMENT_STYLE
        _repl_theme = "parchment"
        console.push_theme(theme)
        console.print("[muted]☀   Parchment (light) theme.[/]")
    else:
        console.print(f"[warning]Unknown theme '{mode}'. Use [accent]light[/] or [accent]dark[/].[/]")


def _show_inbox():
    """Display recent notifications in a styled table."""
    from peerpedia_core.cli.helpers import _read_session
    from peerpedia_core.commands import get_notifications_for_user
    db = _ensure_db()
    session_data = _read_session()
    if not session_data:
        console.print("[muted]Not logged in.[/]")
        return
    notifications = get_notifications_for_user(db, session_data["user_id"])
    if not notifications:
        console.print("[muted]No notifications.[/]")
        return
    from rich.table import Table
    t = Table(title="Notifications", border_style="muted")
    t.add_column("Time", style="muted", width=16)
    t.add_column("Event", style="accent")
    for n in notifications[:20]:
        ts_raw = n.get("created_at", "")
        ts = ts_raw[:16].replace("T", " ") if ts_raw else ""
        marker = "[bold]●[/] " if not n.get("read") else "  "
        t.add_row(ts, f"{marker}{n.get('message', '')}")
    console.print(t)


# ── Interactive browsing ──────────────────────────────────────────────────


def _browse_articles(db, viewer_id: str | None = None) -> str | None:
    """Launch a full-screen article browser.  Returns the selected article ID,
    or None if the user cancelled (Esc/q)."""
    from peerpedia_core.commands import count_articles, list_articles as _la

    articles = _la(db)
    if not articles:
        console.print("[muted]No articles.[/]")
        return None

    n = len(articles)
    selected = [0]  # mutable closure for key binding state

    # Build styled lines for each article
    def _render():
        lines = []
        for i, a in enumerate(articles):
            star = _get_stars()(a.score) if a.score else "[muted]  —  [/]"
            prefix = "▸" if i == selected[0] else " "
            style_class = "class:selected" if i == selected[0] else ""
            lines.append((style_class, f"{prefix} {a.id[:8]}  {a.title:<40} {a.status:<15} {star}\n"))
        return lines

    # Status bar
    def _status_text():
        a = articles[selected[0]]
        actions = "Enter: view  p: publish  e: edit  r: review  b: bookmark  q: back"
        return f" {selected[0]+1}/{n}  ▸ {a.title[:50]}  │  {actions}"

    # Key bindings for the browse mode
    browse_kb = KeyBindings()

    @browse_kb.add("up")
    def _(event):
        selected[0] = (selected[0] - 1) % n

    @browse_kb.add("down")
    def _(event):
        selected[0] = (selected[0] + 1) % n

    @browse_kb.add("enter")
    def _(event):
        event.app.exit(result=articles[selected[0]].id)

    @browse_kb.add("p")
    def _(event):
        event.app.exit(result=f"publish:{articles[selected[0]].id}")

    @browse_kb.add("e")
    def _(event):
        event.app.exit(result=f"edit:{articles[selected[0]].id}")

    @browse_kb.add("r")
    def _(event):
        event.app.exit(result=f"review:{articles[selected[0]].id}")

    @browse_kb.add("b")
    def _(event):
        event.app.exit(result=f"bookmark:{articles[selected[0]].id}")

    @browse_kb.add("q")
    @browse_kb.add("escape")
    def _(event):
        event.app.exit(result=None)

    header = Window(
        height=1,
        content=FormattedTextControl("[class:separator]▔▔▔ Articles ▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔"),
    )
    list_view = Window(
        content=FormattedTextControl(_render),
        always_hide_cursor=True,
    )
    status_bar = Window(
        height=1,
        content=FormattedTextControl(_status_text),
        style="class:status-bar",
    )
    root = HSplit([header, list_view, Window(height=1), status_bar])

    app = Application(
        layout=Layout(root),
        key_bindings=browse_kb,
        full_screen=True,
        mouse_support=True,
        style=repl_style,
    )
    return app.run()


def _dispatch_action(db, result: str, parser) -> None:
    """Handle a browse result like 'publish:<id>' or 'edit:<id>'."""
    if not result or ":" not in result:
        return
    action, article_id = result.split(":", 1)
    _meta_article(article_id)  # set context via meta command
    if action == "publish":
        _dispatch(f"publish {article_id} --scores \"orig=4,rig=3,comp=4,ped=3,imp=4\"", parser)
    elif action == "edit":
        _dispatch(f"edit {article_id}", parser)
    elif action == "review":
        _dispatch(f"review submit {article_id} --scores \"orig=4,rig=3,comp=4,ped=3,imp=4\"", parser)
    elif action == "bookmark":
        _dispatch(f"bookmark add {article_id}", parser)


# ── Command dispatch ─────────────────────────────────────────────────────


def _dispatch(cmd_str: str, parser) -> bool:
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
        elif meta == ":article" or meta == ":a":
            _meta_article(arg.strip())
            return True
        elif meta == ":theme":
            _meta_theme(arg.strip())
            return True
        elif meta == ":feed":
            # Directly invoke article list --feed (bypasses flat-command ambiguity).
            try:
                args = parser.parse_known_args(["article", "list", "--feed"])[0]
                if hasattr(args, "func"):
                    args.rich = True
                    args.json = False
                    args.func(args)
            except Exception as e:
                console.print(f"[error]✗ {e}[/]")
            return True
        elif meta == ":school":
            return _dispatch("school --local", parser)
        elif meta == ":inbox":
            _show_inbox()
            return True
        else:
            console.print(f"[error]Unknown meta-command: {meta}[/]. Try :help")
            return True

    # Map CLI subcommands to their argparse group.
    cmd_map = get_cmd_map()

    try:
        args_list = shlex.split(cmd_str)
    except ValueError as e:
        console.print(f"[error]✗ Parse error: {e}[/]")
        return True

    if not args_list:
        return True

    cmd = args_list[0]

    # Intercept bare 'list' → interactive browse when TTY available.
    # Must happen BEFORE --user injection so flags don't interfere.
    if cmd == "list" and len(args_list) == 1 and sys.stdout.isatty():
        db = _ensure_db()
        result = _browse_articles(db)
        if result:
            if ":" in result:
                _dispatch_action(db, result, parser)
            else:
                _meta_article(result)
                _dispatch(f"show {result}", parser)
        return True

    # Inject --user if sticky user is set and not already provided.
    # Skip for commands that use session user internally (feed, mine, bookmarked).
    _skip_user_inject = {"register", "whoami", "school",
                         ":help", ":h", ":user", ":u", ":article", ":a",
                         ":feed", ":school", ":theme", ":quit", ":q"}
    first_word = cmd
    if (_repl_user and "--user" not in cmd_str
            and first_word not in _skip_user_inject
            and not any(f in cmd_str for f in ("--feed", "--mine", "--bookmarked"))):
        cmd_str += f" --user {_repl_user}"
        try:
            args_list = shlex.split(cmd_str)
        except ValueError:
            pass

    # Auto-inject article ID from context for commands that need it.
    if _repl_article_id and first_word in ("show", "publish", "edit", "delete", "fork"):
        rest = cmd_str[len(first_word):].strip()
        if not rest or rest.startswith("-"):
            cmd_str = f"{first_word} {_repl_article_id}"
            if rest:
                cmd_str += f" {rest}"
            try:
                args_list = shlex.split(cmd_str)
            except ValueError:
                pass

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
            args = parser.parse_known_args(argv[1:])[0]  # skip "peerpedia"; ignore unknown flags
        except SystemExit:
            # argparse calls sys.exit on --help or errors
            console.print("[muted](type :help for available commands)[/]")
            return True
        finally:
            sys.stderr = old_stderr

        if hasattr(args, "func"):
            # REPL defaults to human-readable output, not JSON.
            if not getattr(args, "json", False):
                args.json = False
            args.rich = True
            args.func(args)
        else:
            parser.print_help()
    except Exception as e:
        console.print(f"[error]✗ {e}[/]")

    return True


# ── Entry point ──────────────────────────────────────────────────────────


def run():
    """Start the interactive REPL."""
    from peerpedia_core.cli.helpers import _read_session
    from peerpedia_core.commands import count_articles

    global _repl_user
    db = _ensure_db()
    session_data = _read_session()

    # Auto-detect the logged-in user from the session file.
    if session_data and _repl_user is None:
        _repl_user = session_data.get("name")

    console.print()
    console.print(f"  [bold {theme.styles['info']}]PeerPedia[/] [muted]— scholarly terminal.[/]")
    if session_data:
        user_id = session_data.get("user_id", "")
        user_name = session_data.get("name", "?")
        try:
            drafts = count_articles(db, status="draft", author_id=user_id)
            in_review = count_articles(db, status="sedimentation", author_id=user_id)
            published = count_articles(db, status="published", author_id=user_id)
            parts = []
            if drafts: parts.append(f"{drafts} draft(s)")
            if in_review: parts.append(f"{in_review} in review")
            if published: parts.append(f"{published} published")
            status = ", ".join(parts) if parts else "no articles yet"
        except Exception:
            status = "?"
        console.print(f"  [muted]{user_name} ({user_id[:8]}) · {status}[/]")
    else:
        console.print(f"  [muted]Not logged in. Type [accent]register --name <name>[/] to begin.[/]")
    console.print(f"  [muted]Ctrl+J to submit  ·  :help for commands  ·  :quit to exit[/]")
    console.print()

    REPL_HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)

    completer = WordCompleter(COMMANDS + FLAGS, ignore_case=True, sentence=True)

    # Shift+Enter to submit, plain Enter to insert newline (like Mathematica).
    kb = KeyBindings()

    @kb.add("enter")
    def _(event):
        event.current_buffer.insert_text("\n")

    @kb.add("c-j")
    def _(event):
        """Ctrl+J submits the current input (Enter inserts a newline)."""
        event.current_buffer.validate_and_handle()

    session = PromptSession(
        history=FileHistory(str(REPL_HISTORY_FILE)),
        completer=completer,
        style=repl_style,
        mouse_support=True,
        key_bindings=kb,
        lexer=PygmentsLexer(BashLexer),
    )

    parser = _get_parser()
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

            should_continue = _dispatch(cmd, parser)

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
