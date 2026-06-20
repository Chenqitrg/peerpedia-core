# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

r"""PeerPedia CLI -- self-contained academic peer review from the terminal.

Entry point for all user-facing commands.  Parses argv via argparse, creates
a DB session per command, and dispatches to ``commands/`` functions.

How a command flows through this file
--------------------------------------
::

    main()
      |-- Startup scan: publish_ready_articles(db)
      |-- No args -> repl.run()
      |-- Has args -> build_parser().parse_args()
      |
      v
    args.func(args)                          # e.g. _cmd_article_create
      |
      v
    @_with_db decorator                      # creates session, calls db.commit()
      |
      v
    _cmd_article_create(db, args)            # handler function
      |-- Parse args (--title, --content, etc.)
      |-- Resolve user (_resolve_user)
      |-- Call commands.create_article_with_content(db, ...)
      |-- db.commit()                        # decorator handles this
      |-- Print result or --json output

Key infrastructure
------------------
_get_db()               Open SQLite engine, init tables, return session.
                        DB path: ~/.peerpedia/peerpedia.db

_with_db(func)          Decorator.  Creates a session, calls func(db, args),
                        then calls db.commit().  If the function raises,
                        the session is rolled back.  This is the transaction
                        boundary -- every CLI command is one transaction.

_resolve_user(db, ref)  Look up a user by name or UUID.  Ref can be a full
                        UUID, a prefix (first 8 chars), or a username.

_parse_scores(str)      Parse "orig=4,rigor=3,..." into a scores dict.
                        Used by publish and review submit commands.

_open_editor(initial)   Open $EDITOR with initial content for article
                        creation/editing.

_output helpers         _ok (green checkmark), _die (red error + exit),
                        _json_out (machine-readable), _stars (score bars),
                        _status_badge (colored status label).

Design notes
------------
- CLI handlers import from ``commands/`` for write operations and directly
  from ``storage/db/crud_*.py`` for read-only queries.  This is intentional --
  crud reads have no side effects and don't need orchestration.
- ``db.commit()`` is called by the @_with_db decorator, not by individual
  handlers.  Handlers only call commands functions (which only flush).
- Startup scan and REPL periodic scan call ``publish_ready_articles``
  directly from the main entry point.
- ``--json`` flag on any command switches output to machine-readable JSON.

Reviewer's checklist
--------------------
- Does every write command go through a ``commands/`` function?
- Does every command handler have --json support?
- Are user-facing errors caught and displayed with _die, not raw tracebacks?
"""

from __future__ import annotations

import argparse
import functools
import json
import os
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.theme import Theme

from peerpedia_core.commands import (
    accept_merge,
    create_article_with_content,
    fork_article,
    publish_article,
    rollback_article,
    submit_review,
    update_article_content,
)
from peerpedia_core.storage.db.crud_article import (
    count_articles,
    delete_article,
    get_article,
    get_author_ids,
    list_articles,
)
from peerpedia_core.storage.db.crud_bookmark import add_bookmark, get_bookmarks_for_user, remove_bookmark
from peerpedia_core.storage.db.crud_merge import create_merge_proposal
from peerpedia_core.storage.db.crud_review import get_reviews_for_article
from peerpedia_core.storage.db.crud_user import create_user, get_user, get_user_by_name
from peerpedia_core.storage.db.engine import get_engine, get_session, init_db
from peerpedia_core.storage.git_backend import DEFAULT_ARTICLES_DIR, delete_article_repo
from peerpedia_core.sync import is_online, count as pending_count, client_sync as sync_push
from peerpedia_core.storage.compiler import MarkdownBackend, TypstBackend, detect_format

# ── Rich console with theme ──────────────────────────────────────────────

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


def _get_db():
    """Get a SQLAlchemy session for the local database."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    engine = get_engine(DB_URL)
    init_db(engine)
    return get_session(engine)


def _with_db(func):
    """Decorate a CLI command: open DB session, handle errors, auto-close.

    The decorated function receives ``(db, args)`` instead of just ``args``.
    On exception the session is rolled back and the process exits.
    """

    @functools.wraps(func)
    def wrapper(args):
        db = _get_db()
        try:
            return func(db, args)
        except Exception as e:
            db.rollback()
            _die(str(e))
        finally:
            db.close()

    return wrapper


# ── Output helpers ───────────────────────────────────────────────────────


def _print_panel(title: str, content: str, style: str = "info") -> None:
    console.print(Panel(content, title=title, border_style="muted", title_align="left"))


def _print_table(headers: list[str], rows: list[list[str]], title: str | None = None) -> None:
    table = Table(title=title, border_style="muted")
    for h in headers:
        table.add_column(h, style="bold" if headers.index(h) == 0 else "")
    for row in rows:
        table.add_row(*row)
    console.print(table)


def _status_badge(status: str) -> str:
    colors = {"draft": "white", "sedimentation": "yellow", "published": "green"}
    return f"[{colors.get(status, 'white')}]{status}[/]"


def _stars(score: dict | None, dims: list[str] | None = None) -> str:
    """Render 5-dim scores as stars."""
    if not score:
        return "[muted]no score[/]"
    if dims is None:
        dims = ["originality", "rigor", "completeness", "pedagogy", "impact"]
    return "\n".join(
        f"  {d:<14} [accent]{'★'*v}[/][muted]{'☆'*(5-v)}[/]  {v}/5"
        for d in dims
        for v in [int(score.get(d, 0))]
    )


def _ok(what: str) -> None:
    console.print(f"✓ [{theme.styles['success']}]{what}[/]")


def _die(msg: str) -> None:
    console.print(f"✗ [{theme.styles['error']}]{msg}[/]")
    sys.exit(1)


def _json_out(data: dict | list) -> None:
    print(json.dumps(data, indent=2, default=str))


# ── Helpers ──────────────────────────────────────────────────────────────


def _resolve_user(db, user_ref: str) -> str:
    """Resolve a user reference (name or ID) to a user ID."""
    u = get_user(db, user_ref)
    if u:
        return u.id
    u = get_user_by_name(db, user_ref)
    if u:
        return u.id
    _die(f"User '{user_ref}' not found. Register first: peerpedia account register --name {user_ref}")


def _parse_scores(scores_str: str | None) -> dict | None:
    """Parse 'originality=4,rigor=3,...' into a dict."""
    if not scores_str:
        return None
    return {
        k.strip(): int(v.strip())
        for part in scores_str.split(",")
        for k, v in [part.strip().split("=")]
    }


def _open_editor(initial: str) -> str:
    """Open $EDITOR for the user to write content."""
    editor = os.environ.get("EDITOR", "vim")
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(initial)
        f.flush()
        subprocess.call([editor, f.name])
        return Path(f.name).read_text()


# ── Account commands ─────────────────────────────────────────────────────


@_with_db
def _cmd_register(db, args):
    import bcrypt
    user = create_user(
        db,
        name=args.name or f"u_{uuid.uuid4().hex[:12]}",
        password_hash=bcrypt.hashpw(b"placeholder", bcrypt.gensalt()).decode(),
    )
    db.commit()
    if args.json:
        _json_out({"id": user.id, "name": user.name})
    else:
        _ok(f"Registered [accent]{user.name}[/] (id: {user.id[:8]})")


@_with_db
def _cmd_whoami(db, args):
    if args.json:
        _json_out({"status": "not implemented"})
    else:
        console.print("[muted]Session tracking not yet implemented. Use register/login.[/]")


# ── Article commands ─────────────────────────────────────────────────────


@_with_db
def _cmd_article_create(db, args):
    user_id = _resolve_user(db, args.user)
    content = args.content or ""
    if not content and not args.no_editor:
        content = _open_editor("")
    result = create_article_with_content(
        db, title=args.title, content=content, format=args.format,
        author_ids=[user_id],
    )
    if args.publish:
        self_review = _parse_scores(args.scores) if args.scores else None
        result = publish_article(
            db, result["id"], user_id, self_review,
        )
    db.commit()
    if args.json:
        _json_out(result)
    else:
        _print_panel("Article Created",
            f"[bold]{result['title']}[/]\n"
            f"ID:     [accent]{result['id'][:8]}[/]\n"
            f"Status: {_status_badge(result['status'])}\n"
            f"Hash:   [accent]{result.get('commit_hash', '')[:7]}[/]")


@_with_db
def _cmd_article_show(db, args):
    article = get_article(db, args.id)
    if not article:
        _die(f"Article [accent]{args.id}[/] not found")
    if args.json:
        _json_out({"id": article.id, "title": article.title, "status": article.status})
        return

    raw = ""
    rp = DEFAULT_ARTICLES_DIR / article.id
    for ext in [".md", ".typ"]:
        f = rp / f"article{ext}"
        if f.exists():
            raw = f.read_text()
            break

    try:
        from peerpedia_core.storage.compiler import parse_frontmatter
        fm = parse_frontmatter(raw)
        title = fm.get("title", article.title)
        abstract = fm.get("abstract", article.abstract)
    except Exception:
        title = article.title
        abstract = article.abstract

    scores_str = _stars(article.score) if article.score else "[muted]no scores[/]"
    body = (
        f"[bold info]{title}[/]      {_status_badge(article.status)}\n"
        f"Authors: {', '.join(get_author_ids(db, article.id))}\n"
        f"Score:   {scores_str}\n"
        f"Abstract: {abstract or '[muted]none[/]'}\n"
        f"\n── Content ──\n[muted]{raw[:2000]}[/]"
    )
    _print_panel("Article", body)


@_with_db
def _cmd_article_list(db, args):
    articles = list_articles(db, status=args.status or None)
    total = count_articles(db, status=args.status or None)
    if args.json:
        _json_out([{"id": a.id, "title": a.title, "status": a.status} for a in articles])
        return
    rows = [[a.id[:8], a.title, _status_badge(a.status)]
            for a in articles[:20]]
    _print_table(["ID", "Title", "Status"], rows,
                 title=f"{total} article(s)" + (f" — {args.status}" if args.status else ""))


@_with_db
def _cmd_article_edit(db, args):
    user_id = _resolve_user(db, args.user)
    result = update_article_content(
        db, args.id, content=args.content, title=args.title, user_id=user_id,
    )
    db.commit()
    if args.json:
        _json_out(result)
    else:
        _ok(f"Updated [accent]{args.id[:8]}[/] — {result['title']}")


@_with_db
def _cmd_article_publish(db, args):
    user_id = _resolve_user(db, args.user)
    scores = _parse_scores(args.scores)
    result = publish_article(db, args.id, user_id, scores)
    db.commit()
    if args.json:
        _json_out(result)
    else:
        _ok(f"Published [accent]{args.id[:8]}[/] to sedimentation pool")
        console.print(_stars(scores))


@_with_db
def _cmd_article_delete(db, args):
    if not args.force:
        console.print("[warning]Use --force to confirm deletion[/]")
        return
    delete_article(db, args.id)  # commits internally
    delete_article_repo(DEFAULT_ARTICLES_DIR / args.id)
    _ok(f"Deleted [accent]{args.id[:8]}[/]")


@_with_db
def _cmd_article_scan(db, args):
    from peerpedia_core.commands import publish_ready_articles

    count = publish_ready_articles(db)
    db.commit()
    if args.json:
        _json_out({"published": count})
    else:
        _ok(f"已发布 [accent]{count}[/] 篇文章")


# ── Review commands ──────────────────────────────────────────────────────


@_with_db
def _cmd_review_submit(db, args):
    scores = _parse_scores(args.scores)
    result = submit_review(
        db, article_id=args.article_id, reviewer_id=_resolve_user(db, args.user),
        scores=scores,
        comment=args.comment or "",
    )
    db.commit()
    if args.json:
        _json_out(result)
    else:
        _ok("Review submitted")
        console.print(_stars(scores))


@_with_db
def _cmd_review_list(db, args):
    reviews = get_reviews_for_article(db, args.article_id)
    if args.json:
        _json_out([{"id": r.id, "reviewer_id": r.reviewer_id, "scores": r.scores} for r in reviews])
        return
    if not reviews:
        console.print("[muted]No reviews yet.[/]")
        return
    for r in reviews:
        console.print(f"[bold]{r.reviewer_id[:8]}[/]  {_stars(r.scores)}")
        console.print()


# ── Fork / Merge / Bookmark commands ─────────────────────────────────────


@_with_db
def _cmd_fork(db, args):
    result = fork_article(db, args.article_id, _resolve_user(db, args.user))
    db.commit()
    if args.json:
        _json_out(result)
    else:
        _ok(f"Forked → [accent]{result['id'][:8]}[/]")


@_with_db
def _cmd_merge_propose(db, args):
    mp = create_merge_proposal(db, args.fork_id, args.target, _resolve_user(db, args.user))
    db.commit()
    if args.json:
        _json_out({"id": mp.id, "status": mp.status})
    else:
        _ok(f"Merge proposed [accent]{mp.id[:8]}[/] → target {args.target[:8]}")


@_with_db
def _cmd_merge_accept(db, args):
    result = accept_merge(db, args.target, args.proposal_id, _resolve_user(db, args.user))
    db.commit()
    if args.json:
        _json_out(result)
    elif result.get("status") == "conflict":
        console.print(f"[warning]⚠ {result['message']}[/]")
    else:
        _ok(f"Merge accepted — [accent]{result['id'][:8]}[/]")


@_with_db
def _cmd_bookmark_add(db, args):
    add_bookmark(db, _resolve_user(db, args.user), args.article_id)
    db.commit()
    _ok(f"Bookmarked [accent]{args.article_id[:8]}[/]")


@_with_db
def _cmd_bookmark_list(db, args):
    articles = get_bookmarks_for_user(db, _resolve_user(db, args.user))
    if args.json:
        _json_out([{"id": a.id, "title": a.title} for a in articles])
        return
    if not articles:
        console.print("[muted]No bookmarks.[/]")
        return
    rows = [[a.id[:8], a.title] for a in articles]
    _print_table(["Article ID"], rows, title=f"{len(rows)} bookmark(s)")


# ── Sync commands ────────────────────────────────────────────────────────


def _cmd_sync_status(args):
    server = args.server or os.environ.get("PEERPEDIA_SERVER", "http://localhost:8080")
    online = is_online(server)
    n = pending_count()
    status = "[success]online[/]" if online else "[error]offline[/]"
    body = (
        f"Server:  {server} ({status})\n"
        f"Pending: {n} ops\n"
    )
    if n > 0:
        body += f"\n[warning]⚠ {n} changes not yet synced. Run sync push.[/]"
    _print_panel("Sync Status", body)


# ── Compile command ──────────────────────────────────────────────────────


def _cmd_compile(args):
    rp = DEFAULT_ARTICLES_DIR / args.id
    source = None
    for ext in [".md", ".typ"]:
        f = rp / f"article{ext}"
        if f.exists():
            source = f
            break
    if source is None:
        _die(f"No source file found for article {args.id}")

    fmt = args.format or detect_format(source)
    out_dir = rp / "compiled"
    out_dir.mkdir(exist_ok=True)

    if fmt == "typst":
        backend = TypstBackend()
        result = backend.compile(source, out_dir, fmt=args.format or "pdf")
    else:
        backend = MarkdownBackend()
        result = backend.compile(source, out_dir)

    if result.success:
        if result.output_path:
            _ok(f"Compiled → {result.output_path}")
            console.print(f"[muted]Format: {result.format}[/]")
        if result.html_content:
            console.print(result.html_content[:500])
    else:
        _die(result.error or "Compilation failed")


@_with_db
def _cmd_sync_push(db, args):
    server = args.server or os.environ.get("PEERPEDIA_SERVER", "http://localhost:8080")
    if not is_online(server):
        _die("Server unreachable")
    # Push pending ops from queue
    from peerpedia_core.sync.pending_queue import list_all, remove as pop_pending

    pushed = 0
    for op in list_all():
        result = sync_push(db, server, op["id"])
        if result.get("synced"):
            pop_pending(op["id"])
            pushed += 1
    if pushed > 0:
        db.commit()
        _ok(f"Pushed {pushed} article(s)")
    else:
        console.print("[muted]Nothing to push.[/]")


# ── Argument parser ──────────────────────────────────────────────────────


def _add_common_args(p: argparse.ArgumentParser):
    p.add_argument("--user", default="default", help="User ID for this action")
    p.add_argument("--json", action="store_true", help="Output as JSON")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser("peerpedia", description="PeerPedia — peer review from the terminal")
    subs = parser.add_subparsers(dest="command")

    # ── account ──────────────────────────────────────────────────────────

    acct = subs.add_parser("account", help="Account management")
    acct_subs = acct.add_subparsers(dest="subcommand")

    p = acct_subs.add_parser("register")
    p.add_argument("--name", required=True)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=_cmd_register)

    p = acct_subs.add_parser("whoami")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=_cmd_whoami)

    # ── article ──────────────────────────────────────────────────────────

    art = subs.add_parser("article", help="Article management")
    art_subs = art.add_subparsers(dest="subcommand")

    p = art_subs.add_parser("create")
    p.add_argument("--title", required=True)
    p.add_argument("--format", default="markdown", choices=["markdown", "typst"])
    p.add_argument("--content")
    p.add_argument("--no-editor", action="store_true")
    p.add_argument("--publish", action="store_true")
    p.add_argument("--scores")
    _add_common_args(p)
    p.set_defaults(func=_cmd_article_create)

    p = art_subs.add_parser("show")
    p.add_argument("id")
    _add_common_args(p)
    p.set_defaults(func=_cmd_article_show)

    p = art_subs.add_parser("list")
    p.add_argument("--status")
    _add_common_args(p)
    p.set_defaults(func=_cmd_article_list)

    p = art_subs.add_parser("edit")
    p.add_argument("id")
    p.add_argument("--content")
    p.add_argument("--title")
    _add_common_args(p)
    p.set_defaults(func=_cmd_article_edit)

    p = art_subs.add_parser("publish")
    p.add_argument("id")
    p.add_argument("--scores", required=True)
    _add_common_args(p)
    p.set_defaults(func=_cmd_article_publish)

    p = art_subs.add_parser("delete")
    p.add_argument("id")
    p.add_argument("--force", action="store_true")
    _add_common_args(p)
    p.set_defaults(func=_cmd_article_delete)

    p = art_subs.add_parser("scan")
    p.set_defaults(func=_cmd_article_scan)

    # ── review ───────────────────────────────────────────────────────────

    rev = subs.add_parser("review")
    rev_subs = rev.add_subparsers(dest="subcommand")

    p = rev_subs.add_parser("submit")
    p.add_argument("article_id")
    p.add_argument("--scores", required=True)
    p.add_argument("--comment")
    _add_common_args(p)
    p.set_defaults(func=_cmd_review_submit)

    p = rev_subs.add_parser("list")
    p.add_argument("article_id")
    _add_common_args(p)
    p.set_defaults(func=_cmd_review_list)

    # ── fork ─────────────────────────────────────────────────────────────

    p = subs.add_parser("fork")
    p.add_argument("article_id")
    _add_common_args(p)
    p.set_defaults(func=_cmd_fork)

    # ── merge ────────────────────────────────────────────────────────────

    merge = subs.add_parser("merge")
    merge_subs = merge.add_subparsers(dest="subcommand")

    p = merge_subs.add_parser("propose")
    p.add_argument("fork_id")
    p.add_argument("--target", required=True)
    _add_common_args(p)
    p.set_defaults(func=_cmd_merge_propose)

    p = merge_subs.add_parser("accept")
    p.add_argument("proposal_id")
    p.add_argument("--target", required=True)
    _add_common_args(p)
    p.set_defaults(func=_cmd_merge_accept)

    # ── bookmark ─────────────────────────────────────────────────────────

    bm = subs.add_parser("bookmark")
    bm_subs = bm.add_subparsers(dest="subcommand")

    p = bm_subs.add_parser("add")
    p.add_argument("article_id")
    _add_common_args(p)
    p.set_defaults(func=_cmd_bookmark_add)

    p = bm_subs.add_parser("list")
    _add_common_args(p)
    p.set_defaults(func=_cmd_bookmark_list)

    # ── compile ──────────────────────────────────────────────────────────

    p = subs.add_parser("compile")
    p.add_argument("id")
    p.add_argument("--format", choices=["pdf", "svg", "png", "html"])
    _add_common_args(p)
    p.set_defaults(func=_cmd_compile)

    # ── sync ─────────────────────────────────────────────────────────────

    sync = subs.add_parser("sync")
    sync_subs = sync.add_subparsers(dest="subcommand")

    p = sync_subs.add_parser("status")
    p.add_argument("--server")
    p.set_defaults(func=_cmd_sync_status)

    p = sync_subs.add_parser("push")
    p.add_argument("--server")
    p.set_defaults(func=_cmd_sync_push)

    return parser


def main():
    # Startup scan — publish any articles whose sink time has elapsed
    from peerpedia_core.storage.db.engine import get_session
    from peerpedia_core.commands import publish_ready_articles

    session = get_session()
    try:
        publish_ready_articles(session)
        session.commit()
    finally:
        session.close()

    # If no arguments, enter REPL
    if len(sys.argv) == 1:
        from peerpedia_core.repl import run
        run()
        return

    parser = build_parser()
    try:
        import argcomplete
        argcomplete.autocomplete(parser)
    except ImportError:
        pass
    args = parser.parse_args()
    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
