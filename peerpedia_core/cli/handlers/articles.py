# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Article commands — create, show, list, edit, publish, delete, scan."""

from __future__ import annotations

from datetime import timedelta

from peerpedia_core.config.params import params
from peerpedia_core.policies.articles import visible_statuses_for_user

from peerpedia_core.cli.helpers import (
    _with_db, _get_session_user, _get_session_key, _resolve_and_display_article,
    _resolve_article_id, _resolve_user,
    _find_article_file, _open_editor,
    _prompt_commit_message, _parse_scores, _page, _ok, _die, _json_out,
    _empty_state, _require_resolved_article,
)
from peerpedia_core.cli.display import console, display_diff
import os as _os

from peerpedia_core.cli.bundle_utils import _resolve_server_url, _try_sync
from peerpedia_core.bundle.pending import add as _queue_push
from peerpedia_core.social import discover_articles
from peerpedia_core.transport import is_online
from peerpedia_core.commands import (
    assert_article_integrity, create_article_with_content,
    diff_article, get_article, get_article_view, get_author_ids_batch, get_user,
    list_article_views, list_articles, parse_frontmatter, publish_article,
    publish_ready_articles, delete_article, update_article_content,
)
from peerpedia_core.commands.articles._helpers import require_user


@_with_db
def _cmd_article_create(db, args):
    """Create a new article.

    args: --title, --format [markdown|typst], --content, --no-editor,
          --publish, --scores, --json

    1. Get content from --content, editor, or empty (--no-editor).
    3. Create article + initial git commit via commands layer.
    4. Optionally publish immediately (--publish).
    5. Display result (rich panel or JSON).
    """
    user_id = _get_session_user()
    key_bytes = _get_session_key()
    user = require_user(db, user_id)
    content = args.content or ""
    # Unescape shell-literal \n \t from --content (editor path writes real newlines).
    if content and args.content:
        content = content.replace("\\n", "\n").replace("\\t", "\t")
    if not content and not args.no_editor:
        import sys
        if not sys.stdout.isatty():
            _die("No --content provided and no terminal for editor.",
                 suggestion="Use --content '<text>' or --no-editor to create an empty article.")
        content = _open_editor("")
    result = create_article_with_content(
        db, title=args.title, content=content, format=args.format,
        author_ids=[user_id],
        signing_key_bytes=key_bytes,
        pubkey_hex=user.public_key,
    )
    if args.publish:
        self_review = _parse_scores(args.scores) if args.scores else None
        result = publish_article(
            db, result["id"], user_id, self_review,
            signing_key_bytes=key_bytes, pubkey_hex=user.public_key,
        )
    db.commit()
    _try_sync(db)
    _queue_if_offline(result["id"])
    if args.json:
        _json_out(result)
    else:
        article = get_article(db, result["id"])
        _resolve_and_display_article(db, article, author_ids=[user_id])
        console.print(
            f"[dim]Created [accent]{result['id'][:8]}[/] \"{result['title']}\" (draft)[/]"
        )
        if not args.publish:
            console.print(
                f"[dim]Next: [accent]peerpedia article publish {result['id'][:8]}[/] "
                "--scores \"orig=4,rigor=3,comp=4,ped=3,imp=4\"[/]"
            )


@_with_db
def _cmd_article_show(db, args):
    """Show article details: title, status, authors, score, abstract, content.

    args: id [positional], --show [full|meta|content], --json

    """
    article = _resolve_article_id(db, args.id)
    assert_article_integrity(db, article.id)
    if args.json:
        _json_out(get_article_view(db, article.id))
        return

    show_mode = getattr(args, "show", "meta")
    _resolve_and_display_article(db, article)
    if show_mode == "full":
        raw = _find_article_file(article.id, db=db).read_text()
        console.print("\n[bold]── Content ──[/]")
        # If content is just YAML frontmatter with no body, show a hint.
        body = raw.split("---\n", 2)[-1].strip() if raw.count("---") >= 2 else raw
        if not body:
            console.print(
                "[muted]No content yet. Use [accent]peerpedia article edit "
                f"{article.id[:8]}[/] to add content.[/]"
            )
        else:
            _page(raw)


@_with_db
def _cmd_article_list(db, args):
    """List articles with optional AND filters.

    args: --search, --status, --feed, --mine, --bookmarked, --user, --server, --json
    """
    # Resolve --user ref early — both server and local listing need full UUID.
    resolved_user_id = None
    if args.user:
        resolved_user_id = _resolve_user(db, args.user)

    # Remote fetch: pull article metadata or bookmarks from a peer.
    if args.server:
        server = _resolve_server_url(args)
        if resolved_user_id:
            n = discover_articles(db, server, resolved_user_id)
            db.commit()
            if n > 0:
                console.print(f"[dim]Discovered {n} new article(s) from {server}[/]")

    author_id = None
    viewer_id = None
    bookmarked_by = None
    me = _get_session_user()
    if args.feed:
        viewer_id = me
    if args.mine:
        author_id = me
    if resolved_user_id:
        author_id = resolved_user_id
    if args.bookmarked:
        bookmarked_by = resolved_user_id or me

    # Default: only publicly readable articles.  Drafts imply --mine.
    if args.status == "draft" and not args.mine:
        args.mine = True
    if args.mine:
        status = args.status or None
    elif args.status:
        status = args.status
    else:
        user_obj = get_user(db, me) if me else None
        status = visible_statuses_for_user(user_obj)

    # Feed view must not leak drafts from followed authors.
    if args.feed and not args.mine:
        status = status - {"draft"}

    if args.json:
        _json_out(list_article_views(
            db, status=status, search_query=args.search or None,
            author_id=author_id, viewer_id=viewer_id,
            bookmarked_by=bookmarked_by, limit=20,
        ))
        return

    articles = list_articles(
        db,
        status=status,
        search_query=args.search or None,
        author_id=author_id,
        viewer_id=viewer_id,
        bookmarked_by=bookmarked_by,
        limit=20,
    )
    if not articles:
        if args.feed:
            console.print("[muted]Your feed is empty — you're not following anyone yet.[/]")
            console.print("\n  [accent]peerpedia school[/]              ← discover users")
            console.print("  [accent]peerpedia follow @username[/]   ← follow someone")
        elif args.mine:
            console.print("[muted]No articles yet.[/]")
            console.print(f"\n  [accent]peerpedia article create --title \"My Paper\"[/]")
        else:
            _empty_state("No articles.")
        return
    author_map = get_author_ids_batch(db, [a.id for a in articles])
    for a in articles:
        _resolve_and_display_article(db, a, author_ids=author_map.get(a.id, []))


@_with_db
def _cmd_article_edit(db, args):
    """Edit an article's content or title. Author only.

    args: id [positional], --content, --title, --no-editor, --json
    """
    article, article_id = _require_resolved_article(db, args.id)
    import difflib

    user_id = _get_session_user()
    key_bytes = _get_session_key()
    user = require_user(db, user_id)
    raw = _find_article_file(article_id).read_text()

    if args.content is not None:
        new_content = args.content
    elif not args.no_editor:
        new_content = _open_editor(raw)
    else:
        new_content = None

    content_changed = new_content is not None and new_content != raw
    title_changed = args.title is not None

    if not content_changed and not title_changed:
        console.print("[muted]No changes — nothing to commit.[/]")
        return

    old_text = raw if content_changed else ""
    new_text = new_content if content_changed else ""
    diff = "\n".join(difflib.unified_diff(
        old_text.splitlines(), new_text.splitlines(),
        fromfile="a/article.md", tofile="b/article.md",
    )) if content_changed else ""
    if args.title and not content_changed:
        diff = f"Title: {args.title}"
    message = _prompt_commit_message(diff)

    result = update_article_content(
        db, article_id, content=new_content, title=args.title, user_id=user_id,
        message=message,
        signing_key_bytes=key_bytes, pubkey_hex=user.public_key,
    )
    db.commit()
    _try_sync(db)
    _queue_if_offline(article_id)
    if args.json:
        _json_out(result)
    else:
        _ok(f"Updated [accent]{article_id[:8]}[/] — {result['title']}")
        article = get_article(db, article_id)
        _resolve_and_display_article(db, article)


@_with_db
def _cmd_article_publish(db, args):
    """Publish an article into the sedimentation pool. Author only.

    args: id [positional], --scores, --json
    """
    article, article_id = _require_resolved_article(db, args.id)
    user_id = _get_session_user()
    key_bytes = _get_session_key()
    user = require_user(db, user_id)
    scores = _parse_scores(args.scores)
    result = publish_article(db, article_id, user_id, scores,
                             signing_key_bytes=key_bytes, pubkey_hex=user.public_key)
    db.commit()
    _try_sync(db)
    _queue_if_offline(article_id)
    if args.json:
        _json_out(result)
    else:
        article = get_article(db, article_id)
        sink_end = ""
        if article.sink_start:
            end_date = article.sink_start + timedelta(days=params.sink.new_article_default_days)
            sink_end = end_date.strftime("%Y-%m-%d")
        _ok(f"Published [accent]{article_id[:8]}[/] to sedimentation pool")
        if sink_end:
            console.print(f"[dim]Review window: auto-publishes after {sink_end}.[/]")
        _resolve_and_display_article(db, article)
        console.print(
            f"[dim]Next: [accent]peerpedia share add {article_id[:8]}[/] "
            f"  [accent]peerpedia review invite {article_id[:8]} --user <id>[/][/]"
        )


@_with_db
def _cmd_article_delete(db, args):
    """Delete an article.

    args: id [positional], --json
    """
    user_id = _get_session_user()
    article, article_id = _require_resolved_article(db, args.id)

    if args.json and getattr(args, 'force', False):
        delete_article(db, article_id, user_id=user_id)
        _json_out({"id": article_id, "deleted": True})
        return

    console.print(f"[warning]Delete [bold]{article.title}[/] (id: {article_id[:8]})?[/]")
    try:
        answer = input("  [y/N] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        console.print("\n[muted]Cancelled.[/]")
        return
    if answer not in ("y", "yes"):
        console.print("[muted]Cancelled.[/]")
        return
    delete_article(db, article_id, user_id=user_id)
    _ok(f"Deleted [accent]{article_id[:8]}[/]")


@_with_db
def _cmd_article_scan(db, args):
    """Manually trigger sedimentation → published transition.

    args: (none)
    """
    count = publish_ready_articles(db)
    db.commit()
    if args.json:
        _json_out({"published": count})
    else:
        if count:
            _ok(f"Scan complete — [accent]{count}[/] article(s) auto-published")
        else:
            console.print("[muted]Scan complete — 0 articles ready for publish.[/]")


@_with_db
def _cmd_article_diff(db, args):
    """Diff two commits of an article.  Commits can be hashes, HEAD, or ~N.

    args: id [positional], hash1 [positional], hash2 [positional], --json
    """
    article = _resolve_article_id(db, args.id)
    try:
        result = diff_article(article.id, args.hash1, args.hash2)
    except ValueError as e:
        _die(str(e), code="BAD_REQUEST",
             suggestion="Valid commit refs: a full hash, a short prefix, HEAD, or ~N "
                        "(e.g. ~1 for the parent commit).",
             see_also=["article show --show full"])
    except FileNotFoundError as e:
        _die(str(e), code="NOT_FOUND",
             suggestion="The article's git repository is missing from disk. "
                        "Try 'sync pull' to restore it.")

    if args.json:
        _json_out(result)
    elif not result["diff_text"].strip():
        console.print("[muted]These are the same revision — no changes to show.[/]")
    else:
        display_diff(result["diff_text"], result["stats"])


def _queue_if_offline(article_id: str) -> None:
    """Queue an article for push if the peer server is unreachable.

    Called after state-changing commands (create, publish, edit) so that
    changes are pushed eventually even when the server is temporarily down.
    ``cli.handlers.bundle._cmd_sync_push`` drains this queue when the server comes back.
    """
    server = _os.environ.get("PEERPEDIA_SERVER")
    if server and not is_online(server):
        _queue_push("push", article_id)