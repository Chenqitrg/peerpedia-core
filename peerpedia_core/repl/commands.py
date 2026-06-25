# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""REPL meta-commands and command dispatch."""

from __future__ import annotations

import shlex
import sys

from peerpedia_core.repl.typography import (
    styled_title as _T_raw, styled_author as _A_raw, styled_date as _D_raw,
    styled_status as _S_raw, styled_score_val as _SC_raw,
)

def _T(s, *args, **kwargs):
    import peerpedia_core.repl.state as _st
    return _T_raw(s, *args, **kwargs) if _st._repl_unicode else s

def _A(s, *args, **kwargs):
    import peerpedia_core.repl.state as _st
    return _A_raw(s, *args, **kwargs) if _st._repl_unicode else s

def _D(s, *args, **kwargs):
    import peerpedia_core.repl.state as _st
    return _D_raw(s, *args, **kwargs) if _st._repl_unicode else s

def _S(s, *args, **kwargs):
    import peerpedia_core.repl.state as _st
    return _S_raw(s, *args, **kwargs) if _st._repl_unicode else s

def _SC(s, *args, **kwargs):
    import peerpedia_core.repl.state as _st
    return _SC_raw(s, *args, **kwargs) if _st._repl_unicode else s

from peerpedia_core.cli.parser import get_cmd_map
from peerpedia_core.commands import get_user, get_user_by_name, list_articles
from peerpedia_core.storage.db.models import Article

from peerpedia_core.repl.state import (
    _ensure_db, _repl_user, _repl_article_id, _repl_article_title,
    _repl_article_commit, _repl_theme, _repl_compact,
    _PARCHMENT_THEME, _EMBER_THEME, _PARCHMENT_STYLE, _EMBER_STYLE,
    theme, repl_style, console,
)

_META_COMMANDS = [":help", ":h", ":user", ":u", ":article", ":a", ":theme",
                  ":compact", ":unicode", ":write", ":feed", ":school", ":inbox", ":quit", ":q"]


# ── Meta-command handlers ────────────────────────────────────────────────


def _meta_help():
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text

    cmd_table = Table(show_header=False, border_style="muted", padding=(0, 1))
    cmd_table.add_column("cmd", style=f"bold {theme.styles['accent']}", width=14)
    cmd_table.add_column("desc", style="muted")
    rows = [
        ("register",       "Register a new account"),
        ("whoami",         "Show current user"),
        ("create",         "Write a new article  --title <t> [--content <c>]"),
        ("show <id>",      "View an article"),
        ("list",           "Browse articles  [--mine] [--feed] [--status <s>]"),
        ("edit <id>",      "Edit an article"),
        ("publish <id>",   "Submit to sedimentation pool  --scores <s>"),
        ("delete <id>",    "Delete a draft"),
        ("review submit",  "Submit peer review  <id> --scores <s> --comment <c>"),
        ("review list",    "List reviews for an article  <id>"),
        ("review reply",   "Reply to a review  <id> --to <user>"),
        ("review invite",  "Invite a reviewer  <id> --user <u>"),
        ("review accept",  "Accept a review invitation  <id>"),
        ("review decline", "Decline a review invitation  <id>"),
        ("follow @name",   "Follow a user"),
        ("unfollow @name", "Unfollow a user"),
        ("bookmark add",   "Bookmark an article  <id>"),
        ("share add",      "Share an article  <id>"),
        ("fork <id>",      "Fork a published article"),
        ("sync status",    "Check peer connection + pending ops"),
    ]
    for cmd, desc in rows:
        cmd_table.add_row(cmd, desc)

    meta_table = Table(show_header=False, border_style="muted", padding=(0, 1))
    meta_table.add_column("cmd", style=f"bold {theme.styles['info']}", width=14)
    meta_table.add_column("desc", style="muted")
    meta_rows = [
        (":user <name>",   "Set sticky user (auto-injects --user)"),
        (":article <ref>", "Set article context (auto-injects ID)"),
        (":feed",          "Your feed — articles from followed users"),
        (":school",        "User leaderboard (interactive)"),
        (":inbox",         "Notification inbox"),
        (":compact",       "Toggle compact / rich output"),
        (":theme <l|d>",   "Switch light (parchment) / dark (ember) theme"),
        (":help",          "Show this reference"),
        (":quit, :q",      "Exit REPL"),
    ]
    for cmd, desc in meta_rows:
        meta_table.add_row(cmd, desc)

    console.print(Panel(cmd_table, title="Commands", border_style="muted", title_align="left"))
    console.print(Panel(meta_table, title="Meta", border_style="muted", title_align="left"))
    keys = Text()
    keys.append("Ctrl+J", style="bold")
    keys.append(" submit  ·  ")
    keys.append("Enter", style="bold")
    keys.append(" newline  ·  ")
    keys.append("--json", style="accent")
    keys.append(" for machine output")
    console.print(f"  [dim]{keys}[/]")


def _meta_user(name):
    global _repl_user
    db = _ensure_db()
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
                t.add_row(str(i), user.id[:8], user.affiliation or "—")
            console.print(t)
            console.print(f"[muted]Use [accent]:user <id prefix>[/] to pick.[/]")
            return
    if u:
        _repl_user = name
        console.print(f"[success]✓[/] User set to [accent]{u.name}[/] [muted]({u.id[:8]})[/]")
    else:
        console.print(f"[error]✗[/] User '{name}' not found. [muted]register --name {name}[/] to create.[/]")


def _meta_article(ref: str):
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
        # Sedimentation countdown
        sink_info = ""
        if article.status == "sedimentation" and article.sink_start:
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc)
            start = article.sink_start.replace(tzinfo=timezone.utc) if article.sink_start.tzinfo is None else article.sink_start
            elapsed = (now - start).days
            total = article.sink_duration_days or 7
            remaining = max(0, total - elapsed)
            bar_filled = min(total, max(0, elapsed))
            bar = "█" * bar_filled + "░" * (total - bar_filled)
            sink_info = f"  [{theme.styles['muted']}]{bar}[/] {remaining}d left"
        console.print(f"[success]▸[/] {_T(article.title)} [muted]({article.id[:8]}{commit_str})[/]{sink_info}")
    else:
        console.print(f"[error]✗[/] Article '{ref}' not found.")


def _meta_theme(mode: str):
    global theme, repl_style, _repl_theme
    mode = mode.strip().lower() or "parchment"
    if mode in ("dark", "ember", "night"):
        theme = _EMBER_THEME
        repl_style = _EMBER_STYLE
        _repl_theme = "ember"
        console.push_theme(theme)
        console.print("🌙  Ember (dark) theme.")
    elif mode in ("light", "parchment", "day"):
        theme = _PARCHMENT_THEME
        repl_style = _PARCHMENT_STYLE
        _repl_theme = "parchment"
        console.push_theme(theme)
        console.print("☀   Parchment (light) theme.")
    else:
        console.print(f"[warning]Unknown theme '{mode}'. Use [accent]light[/] or [accent]dark[/].[/]")


def _show_inbox():
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


def _meta_write(parser) -> bool:
    """Guided article creation wizard. Returns True to continue REPL."""
    from rich.prompt import Prompt

    console.print(f"[bold {theme.styles['info']}]▔▔▔ New Article ▔▔▔[/]")
    try:
        title = Prompt.ask(f"  [{theme.styles['accent']}]Title[/]")
    except (EOFError, KeyboardInterrupt):
        console.print("[muted]Cancelled.[/]")
        return True

    if not title.strip():
        console.print("[muted]Cancelled — empty title.[/]")
        return True

    console.print(f"  [muted]Content (Ctrl+D or empty line to finish):[/]")
    lines = []
    try:
        while True:
            line = Prompt.ask("", default="")
            if line == "":
                break
            lines.append(line)
    except (EOFError, KeyboardInterrupt):
        pass

    content = "\n".join(lines) if lines else ""
    if not content:
        console.print("[muted]Created with empty content.[/]")

    # Build and dispatch
    escaped_content = content.replace('"', '\\"').replace('\n', '\\n')
    cmd = f'create --title "{title}" --content "{escaped_content}"'
    console.print(f"  [dim]{cmd[:80]}...[/]")
    result = _dispatch(cmd, parser)

    # Offer to publish
    if result and _repl_article_id:
        try:
            pub = Prompt.ask(
                f"  [{theme.styles['accent']}]Publish now?[/] [muted][y/N][/]",
                default="n"
            )
            if pub.lower() in ("y", "yes"):
                return _dispatch(
                    f'publish {_repl_article_id} --scores "orig=4,rig=3,comp=4,ped=3,imp=4"',
                    parser
                )
        except (EOFError, KeyboardInterrupt):
            pass

    return True


# ── Dispatch ─────────────────────────────────────────────────────────────


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
        if meta in (":quit", ":q"):
            return False
        elif meta in (":help", ":h"):
            _meta_help()
            return True
        elif meta in (":user", ":u"):
            _meta_user(arg.strip())
            return True
        elif meta in (":article", ":a"):
            _meta_article(arg.strip())
            return True
        elif meta == ":theme":
            _meta_theme(arg.strip())
            return True
        elif meta == ":compact":
            global _repl_compact
            _repl_compact = not _repl_compact
            mode = "compact table" if _repl_compact else "rich panels"
            console.print(f"[muted]Output mode: {mode}.[/]")
            return True
        elif meta == ":unicode":
            import peerpedia_core.repl.state as _st
            _st._repl_unicode = not _st._repl_unicode
            status = "on" if _st._repl_unicode else "off"
            console.print(f"[muted]Unicode typography: {status}.[/]")
            return True
        elif meta == ":feed":
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
            if sys.stdout.isatty():
                from peerpedia_core.repl.browse import _browse_school
                db = _ensure_db()
                result = _browse_school(db)
                if result and result.startswith("follow:"):
                    target_id = result.split(":", 1)[1]
                    return _dispatch(f"follow {target_id}", parser)
            else:
                return _dispatch("school --local", parser)
            return True
        elif meta == ":inbox":
            _show_inbox()
            return True
        elif meta == ":write":
            return _meta_write(parser)
        else:
            console.print(f"[error]Unknown meta-command: {meta}[/]. Try :help")
            return True

    # Map CLI subcommands
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
    if cmd == "list" and len(args_list) == 1 and sys.stdout.isatty():
        from peerpedia_core.repl.browse import _browse_articles
        db = _ensure_db()
        result = _browse_articles(db)
        if result:
            if ":" in result:
                _dispatch_action(db, result, parser)
            else:
                _meta_article(result)
                return _dispatch(f"show {result}", parser)
        return True

    # Intercept 'review list' with article context → interactive browse.
    if (cmd == "review" and len(args_list) >= 2 and args_list[1] == "list"
            and sys.stdout.isatty()):
        aid = None
        if len(args_list) >= 3:
            aid = args_list[2]
        elif _repl_article_id:
            aid = _repl_article_id
        if aid:
            from peerpedia_core.repl.browse import _browse_reviews
            db = _ensure_db()
            result = _browse_reviews(db, aid)
            if result:
                if result.startswith("reply:"):
                    reviewer_id = result.split(":", 1)[1]
                    return _dispatch(f"review reply {aid} --to {reviewer_id}", parser)
                else:
                    console.print(f"[accent]{result[:8]}[/]")
            return True

    # Inject --user if sticky user is set.
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

    # Auto-inject article ID from context.
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

    mapping = cmd_map[cmd]
    argv = ["peerpedia"] + mapping + args_list[1:]

    try:
        import io
        old_stderr = sys.stderr
        sys.stderr = io.StringIO()
        try:
            args = parser.parse_known_args(argv[1:])[0]
        except SystemExit:
            console.print("[muted](type :help for available commands)[/]")
            return True
        finally:
            sys.stderr = old_stderr

        if hasattr(args, "func"):
            if not getattr(args, "json", False):
                args.json = False
            args.rich = True
            args.func(args)
        else:
            parser.print_help()
    except Exception as e:
        from rich.panel import Panel
        console.print(Panel(str(e), title="Error", border_style="error", title_align="left"))

    return True


def _dispatch_action(db, result: str, parser) -> None:
    """Handle a browse result like 'publish:<id>' or 'edit:<id>'."""
    if not result or ":" not in result:
        return
    action, article_id = result.split(":", 1)
    _meta_article(article_id)
    if action == "publish":
        _dispatch(f"publish {article_id} --scores \"orig=4,rig=3,comp=4,ped=3,imp=4\"", parser)
    elif action == "edit":
        _dispatch(f"edit {article_id}", parser)
    elif action == "review":
        _dispatch(f"review submit {article_id} --scores \"orig=4,rig=3,comp=4,ped=3,imp=4\"", parser)
    elif action == "bookmark":
        _dispatch(f"bookmark add {article_id}", parser)
