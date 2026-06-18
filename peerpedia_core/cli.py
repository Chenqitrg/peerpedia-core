# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""PeerPedia CLI — self-contained academic peer review from the terminal.

Usage:
    peerpedia article create --title "..." --format markdown
    peerpedia article show <id>
    peerpedia review submit <article-id>
    peerpedia sync status
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.theme import Theme

from peerpedia_core.config.params import params
from peerpedia_core.storage.commands import (
    accept_merge,
    create_article_with_content,
    fork_article,
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
from peerpedia_core.storage.db.crud_user import create_user, get_user, get_user_by_username
from peerpedia_core.storage.db.engine import get_engine, get_session, init_db
from peerpedia_core.storage.git_backend import DEFAULT_ARTICLES_DIR, get_commit_history, get_diff_between
from peerpedia_core.sync import is_online, count as pending_count, push as sync_push

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
    lines = []
    for d in dims:
        v = int(score.get(d, 0))
        filled = "★" * v
        empty = "☆" * (5 - v)
        lines.append(f"  {d:<14} [accent]{filled}[/][muted]{empty}[/]  {v}/5")
    return "\n".join(lines)


def _ok(what: str) -> None:
    console.print(f"✓ [{theme.styles['success']}]{what}[/]")


def _die(msg: str) -> None:
    console.print(f"✗ [{theme.styles['error']}]{msg}[/]")
    sys.exit(1)


def _json_out(data: dict | list) -> None:
    print(json.dumps(data, indent=2, default=str))


# ── Account commands ─────────────────────────────────────────────────────


def _cmd_register(args):
    db = _get_db()
    try:
        from peerpedia_core.storage.db.crud_user import _new_username
        import bcrypt
        user = create_user(
            db, username=args.name or _new_username(),
            password_hash=bcrypt.hashpw(b"placeholder", bcrypt.gensalt()).decode(),
            name=args.name,
        )
        db.commit()
        if args.json:
            _json_out({"id": user.id, "username": user.username, "name": user.name})
        else:
            _ok(f"Registered [accent]{user.username}[/] (id: {user.id[:8]})")
    except Exception as e:
        db.rollback()
        _die(str(e))
    finally:
        db.close()


def _cmd_whoami(args):
    # Show current user from stored session (simplified: read last registered)
    db = _get_db()
    try:
        users = get_user(db, "nonexistent")  # placeholder
        if args.json:
            _json_out({"status": "not implemented"})
        else:
            console.print("[muted]Session tracking not yet implemented. Use register/login.[/]")
    finally:
        db.close()


# ── Article commands ─────────────────────────────────────────────────────


def _resolve_user(db, user_ref: str) -> str:
    """Resolve a user reference (name or ID) to a user ID."""
    u = get_user(db, user_ref)
    if u:
        return u.id
    u = get_user_by_username(db, user_ref)
    if u:
        return u.id
    _die(f"User '{user_ref}' not found. Register first: peerpedia account register --name {user_ref}")


def _cmd_article_create(args):
    db = _get_db()
    try:
        user_id = _resolve_user(db, args.user)
        content = args.content or ""
        if not content and not args.no_editor:
            content = _open_editor("")
        result = create_article_with_content(
            db, title=args.title, content=content, format=args.format,
            user_id=user_id, publish=args.publish,
            self_review=_parse_scores(args.scores) if args.scores else None,
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
    except Exception as e:
        db.rollback()
        _die(str(e))
    finally:
        db.close()


def _cmd_article_show(args):
    db = _get_db()
    try:
        article = get_article(db, args.id)
        if not article:
            _die(f"Article [accent]{args.id}[/] not found")
        if args.json:
            _json_out({"id": article.id, "title": article.title, "status": article.status})
            return

        # Read content from git
        content = ""
        rp = DEFAULT_ARTICLES_DIR / article.id
        for ext in [".md", ".typ"]:
            f = rp / f"article{ext}"
            if f.exists():
                content = f.read_text()[:2000]
                break

        scores_str = _stars(article.score) if article.score else "[muted]no scores[/]"
        body = (
            f"[bold info]{article.title}[/]      {_status_badge(article.status)}\n"
            f"Authors: {', '.join(get_author_ids(db, article.id))}\n"
            f"Score:   {scores_str}\n"
            f"Abstract: {article.abstract or '[muted]none[/]'}\n"
            f"\n── Content ──\n[muted]{content}[/]"
        )
        _print_panel("Article", body)
    except Exception as e:
        _die(str(e))
    finally:
        db.close()


def _cmd_article_list(args):
    db = _get_db()
    try:
        articles = list_articles(db, status=args.status or None)
        total = count_articles(db, status=args.status or None)
        if args.json:
            _json_out([{"id": a.id, "title": a.title, "status": a.status} for a in articles])
            return
        rows = [[a.id[:8], a.title, _status_badge(a.status)]
                for a in articles[:20]]
        _print_table(["ID", "Title", "Status"], rows,
                     title=f"{total} article(s)" + (f" — {args.status}" if args.status else ""))
    except Exception as e:
        _die(str(e))
    finally:
        db.close()


def _cmd_article_edit(args):
    db = _get_db()
    try:
        user_id = _resolve_user(db, args.user)
        result = update_article_content(
            db, args.id, content=args.content, title=args.title, user_id=user_id,
        )
        db.commit()
        if args.json:
            _json_out(result)
        else:
            _ok(f"Updated [accent]{args.id[:8]}[/] — {result['title']}")
    except Exception as e:
        db.rollback()
        _die(str(e))
    finally:
        db.close()


def _cmd_article_publish(args):
    db = _get_db()
    try:
        scores = _parse_scores(args.scores)
        result = update_article_content(
            db, args.id, publish=True, self_review=scores, user_id=_resolve_user(db, args.user),
        )
        db.commit()
        if args.json:
            _json_out(result)
        else:
            _ok(f"Published [accent]{args.id[:8]}[/] to sedimentation pool")
            console.print(_stars(scores))
    except Exception as e:
        db.rollback()
        _die(str(e))
    finally:
        db.close()


def _cmd_article_delete(args):
    db = _get_db()
    try:
        if not args.force:
            console.print("[warning]Use --force to confirm deletion[/]")
            return
        delete_article(db, args.id)
        db.commit()
        _ok(f"Deleted [accent]{args.id[:8]}[/]")
    except Exception as e:
        db.rollback()
        _die(str(e))
    finally:
        db.close()


# ── Review commands ──────────────────────────────────────────────────────


def _cmd_review_submit(args):
    db = _get_db()
    try:
        scores = _parse_scores(args.scores)
        result = submit_review(
            db, article_id=args.article_id, reviewer_id=_resolve_user(db, args.user),
            scores=scores, scope="pool",
            commit_hash=args.commit_hash or "unknown",
            comment=args.comment or "",
        )
        db.commit()
        if args.json:
            _json_out(result)
        else:
            _ok("Review submitted")
            console.print(_stars(scores))
    except Exception as e:
        db.rollback()
        _die(str(e))
    finally:
        db.close()


def _cmd_review_list(args):
    db = _get_db()
    try:
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
    except Exception as e:
        _die(str(e))
    finally:
        db.close()


# ── Fork / Merge / Bookmark commands ─────────────────────────────────────


def _cmd_fork(args):
    db = _get_db()
    try:
        result = fork_article(db, args.article_id, _resolve_user(db, args.user))
        db.commit()
        if args.json:
            _json_out(result)
        else:
            _ok(f"Forked → [accent]{result['id'][:8]}[/]")
    except Exception as e:
        db.rollback()
        _die(str(e))
    finally:
        db.close()


def _cmd_merge_propose(args):
    db = _get_db()
    try:
        mp = create_merge_proposal(db, args.fork_id, args.target, _resolve_user(db, args.user))
        db.commit()
        if args.json:
            _json_out({"id": mp.id, "status": mp.status})
        else:
            _ok(f"Merge proposed [accent]{mp.id[:8]}[/] → target {args.target[:8]}")
    except Exception as e:
        db.rollback()
        _die(str(e))
    finally:
        db.close()


def _cmd_merge_accept(args):
    db = _get_db()
    try:
        result = accept_merge(db, args.target, args.proposal_id, _resolve_user(db, args.user))
        db.commit()
        if args.json:
            _json_out(result)
        elif result.get("status") == "conflict":
            console.print(f"[warning]⚠ {result['message']}[/]")
        else:
            _ok(f"Merge accepted — [accent]{result['id'][:8]}[/]")
    except Exception as e:
        db.rollback()
        _die(str(e))
    finally:
        db.close()


def _cmd_bookmark_add(args):
    db = _get_db()
    try:
        add_bookmark(db, _resolve_user(db, args.user), args.article_id)
        db.commit()
        _ok(f"Bookmarked [accent]{args.article_id[:8]}[/]")
    except Exception as e:
        db.rollback()
        _die(str(e))
    finally:
        db.close()


def _cmd_bookmark_list(args):
    db = _get_db()
    try:
        articles = get_bookmarks_for_user(db, _resolve_user(db, args.user))
        if args.json:
            _json_out([{"id": a.id, "title": a.title} for a in articles])
            return
        if not articles:
            console.print("[muted]No bookmarks.[/]")
            return
        rows = [[a.id[:8], a.title] for a in articles]
        _print_table(["Article ID"], rows, title=f"{len(rows)} bookmark(s)")
    except Exception as e:
        _die(str(e))
    finally:
        db.close()


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


def _cmd_sync_push(args):
    server = args.server or os.environ.get("PEERPEDIA_SERVER", "http://localhost:8080")
    if not is_online(server):
        _die("Server unreachable")
    # Push pending ops from queue
    from peerpedia_core.sync.pending_queue import list_all, remove as pop_pending

    pushed = 0
    for op in list_all():
        result = sync_push(server, op["id"])
        if result.get("pushed"):
            pop_pending(op["id"])
            pushed += 1
    if pushed > 0:
        _ok(f"Pushed {pushed} article(s)")
    else:
        console.print("[muted]Nothing to push.[/]")


# ── Helpers ──────────────────────────────────────────────────────────────


def _parse_scores(scores_str: str | None) -> dict | None:
    """Parse 'originality=4,rigor=3,...' into a dict."""
    if not scores_str:
        return None
    result = {}
    for part in scores_str.split(","):
        k, v = part.strip().split("=")
        result[k.strip()] = int(v.strip())
    return result


def _open_editor(initial: str) -> str:
    """Open $EDITOR for the user to write content."""
    editor = os.environ.get("EDITOR", "vim")
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(initial)
        f.flush()
        subprocess.call([editor, f.name])
        return Path(f.name).read_text()


# ── Argument parser ──────────────────────────────────────────────────────


def _add_common_args(p: argparse.ArgumentParser):
    p.add_argument("--user", default="default", help="User ID for this action")
    p.add_argument("--json", action="store_true", help="Output as JSON")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser("peerpedia", description="PeerPedia — peer review from the terminal")
    subs = parser.add_subparsers(dest="command")

    # account
    acct = subs.add_parser("account", help="Account management")
    acct_subs = acct.add_subparsers(dest="subcommand")
    p = acct_subs.add_parser("register")
    p.add_argument("--name", required=True)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=_cmd_register)
    p = acct_subs.add_parser("whoami")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=_cmd_whoami)

    # article
    art = subs.add_parser("article", help="Article management")
    art_subs = art.add_subparsers(dest="subcommand")
    p = art_subs.add_parser("create")
    p.add_argument("--title", required=True)
    p.add_argument("--format", default="markdown", choices=["markdown", "typst"])
    p.add_argument("--content")
    p.add_argument("--no-editor", action="store_true")
    p.add_argument("--publish", action="store_true")
    p.add_argument("--scores")
    _add_common_args(p); p.set_defaults(func=_cmd_article_create)
    p = art_subs.add_parser("show")
    p.add_argument("id"); _add_common_args(p); p.set_defaults(func=_cmd_article_show)
    p = art_subs.add_parser("list")
    p.add_argument("--status"); _add_common_args(p); p.set_defaults(func=_cmd_article_list)
    p = art_subs.add_parser("edit")
    p.add_argument("id"); p.add_argument("--content"); p.add_argument("--title")
    _add_common_args(p); p.set_defaults(func=_cmd_article_edit)
    p = art_subs.add_parser("publish")
    p.add_argument("id"); p.add_argument("--scores", required=True)
    _add_common_args(p); p.set_defaults(func=_cmd_article_publish)
    p = art_subs.add_parser("delete")
    p.add_argument("id"); p.add_argument("--force", action="store_true")
    _add_common_args(p); p.set_defaults(func=_cmd_article_delete)

    # review
    rev = subs.add_parser("review")
    rev_subs = rev.add_subparsers(dest="subcommand")
    p = rev_subs.add_parser("submit")
    p.add_argument("article_id"); p.add_argument("--scores", required=True)
    p.add_argument("--comment"); p.add_argument("--commit-hash")
    _add_common_args(p); p.set_defaults(func=_cmd_review_submit)
    p = rev_subs.add_parser("list")
    p.add_argument("article_id"); _add_common_args(p); p.set_defaults(func=_cmd_review_list)

    # fork
    p = subs.add_parser("fork"); p.add_argument("article_id")
    _add_common_args(p); p.set_defaults(func=_cmd_fork)

    # merge
    merge = subs.add_parser("merge")
    merge_subs = merge.add_subparsers(dest="subcommand")
    p = merge_subs.add_parser("propose")
    p.add_argument("fork_id"); p.add_argument("--target", required=True)
    _add_common_args(p); p.set_defaults(func=_cmd_merge_propose)
    p = merge_subs.add_parser("accept")
    p.add_argument("proposal_id"); p.add_argument("--target", required=True)
    _add_common_args(p); p.set_defaults(func=_cmd_merge_accept)

    # bookmark
    bm = subs.add_parser("bookmark")
    bm_subs = bm.add_subparsers(dest="subcommand")
    p = bm_subs.add_parser("add"); p.add_argument("article_id")
    _add_common_args(p); p.set_defaults(func=_cmd_bookmark_add)
    p = bm_subs.add_parser("list"); _add_common_args(p); p.set_defaults(func=_cmd_bookmark_list)

    # sync
    sync = subs.add_parser("sync")
    sync_subs = sync.add_subparsers(dest="subcommand")
    p = sync_subs.add_parser("status"); p.add_argument("--server")
    p.set_defaults(func=_cmd_sync_status)
    p = sync_subs.add_parser("push"); p.add_argument("--server")
    p.set_defaults(func=_cmd_sync_push)

    return parser


def main():
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
