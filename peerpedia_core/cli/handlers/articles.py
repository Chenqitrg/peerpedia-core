# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Article commands — create, show, list, edit, publish, delete, scan."""

from __future__ import annotations

from peerpedia_core.policies.articles import PUBLIC_READABLE_STATUSES

from peerpedia_core.cli.helpers import (
    _with_db, _get_session_user, _get_session_key, _resolve_and_display_article, _resolve_article_id,
    _find_article_file, _open_editor,
    _prompt_commit_message, _parse_scores, _page, _ok, _die, _json_out,
)
from peerpedia_core.cli.display import console, display_diff
from peerpedia_core.cli.bundle_utils import _sync_server, _try_sync
from peerpedia_core.social import discover_articles
from peerpedia_core.commands import (
    assert_article_integrity, create_article_with_content,
    diff_article, get_article, get_article_view, get_author_ids_batch,
    list_article_views, list_articles, publish_article,
    publish_ready_articles, delete_article, update_article_content, get_user,
)


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
    user = get_user(db, user_id)
    if user is None:
        _die(f"User '{user_id}' not found in local database.",
             suggestion="Your session references a user that no longer exists. "
                        "Run 'peerpedia account recover' or 'account register'.",
             see_also=["account recover", "account register"])
    content = args.content or ""
    if not content and not args.no_editor:
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
    # TODO(P2P-sync): auto-queue the new article for push to peer server.
    # Currently articles are only synced when manually queued via
    # ``pending.add('push', article_id)``.  After create/publish, the
    # article should be queued automatically if PEERPEDIA_SERVER is set.
    _try_sync(db)
    if args.json:
        _json_out(result)
    else:
        article = get_article(db, result["id"])
        _resolve_and_display_article(db, article)


@_with_db
def _cmd_article_show(db, args):
    """Show article details: title, status, authors, score, abstract, content.

    args: id [positional], --show [full|meta|content], --json

    """
    assert_article_integrity(db, args.id)
    article = _resolve_article_id(db, args.id)
    if args.json:
        _json_out(get_article_view(db, args.id))
        return

    show_mode = getattr(args, "show", "meta")
    _resolve_and_display_article(db, article)
    if show_mode == "full":
        raw = _find_article_file(article.id).read_text()
        console.print("\n[bold]── Content ──[/]")
        _page(raw)


@_with_db
def _cmd_article_list(db, args):
    """List articles with optional AND filters.

    args: --search, --status, --feed, --mine, --bookmarked, --user, --server, --json
    """
    # Remote fetch: pull article metadata or bookmarks from a peer.
    if args.server:
        server = _sync_server(args)
        if args.user:
            n = discover_articles(db, server, args.user)
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
    if args.user:
        author_id = args.user
    if args.bookmarked:
        bookmarked_by = args.user or me

    # Default: only publicly readable articles.  Drafts require --mine.
    if args.mine:
        status = args.status or None
    elif args.status:
        if args.status == "draft":
            _die("--status draft requires --mine",
                 suggestion="Drafts are private. Add --mine to see your own drafts, "
                            "or omit --status to browse published articles.",
                 see_also=["article list --mine"])
        status = args.status
    else:
        status = PUBLIC_READABLE_STATUSES

    articles = list_articles(
        db,
        status=status,
        search_query=args.search or None,
        author_id=author_id,
        viewer_id=viewer_id,
        bookmarked_by=bookmarked_by,
        limit=20,
    )
    if args.json:
        _json_out(list_article_views(
            db, search_query=args.search or None, author_id=author_id,
            viewer_id=viewer_id, bookmarked_by=bookmarked_by, limit=20,
        ))
        return
    if not articles:
        console.print("[muted]No articles.[/]")
        return
    author_map = get_author_ids_batch(db, [a.id for a in articles])
    for a in articles:
        _resolve_and_display_article(db, a, author_ids=author_map.get(a.id, []))


@_with_db
def _cmd_article_edit(db, args):
    """Edit an article's content or title. Author only.

    args: id [positional], --content, --title, --no-editor, --json
    """
    article = _resolve_article_id(db, args.id)
    article_id = article.id
    assert_article_integrity(db, article_id)
    import difflib

    user_id = _get_session_user()
    key_bytes = _get_session_key()
    user = get_user(db, user_id)
    if user is None:
        _die(f"User '{user_id}' not found — DB inconsistency.")
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
    article = _resolve_article_id(db, args.id)
    article_id = article.id
    assert_article_integrity(db, article_id)
    user_id = _get_session_user()
    key_bytes = _get_session_key()
    user = get_user(db, user_id)
    if user is None:
        _die(f"User '{user_id}' not found — DB inconsistency.")
    scores = _parse_scores(args.scores)
    result = publish_article(db, article_id, user_id, scores,
                             signing_key_bytes=key_bytes, pubkey_hex=user.public_key)
    db.commit()
    _try_sync(db)
    if args.json:
        _json_out(result)
    else:
        _ok(f"Published [accent]{article_id[:8]}[/] to sedimentation pool")
        article = get_article(db, article_id)
        _resolve_and_display_article(db, article)


@_with_db
def _cmd_article_delete(db, args):
    """Delete an article.

    args: id [positional], --json
    """
    user_id = _get_session_user()
    article = _resolve_article_id(db, args.id)

    console.print(f"[warning]Delete [bold]{article.title}[/] (id: {article.id[:8]})?[/]")
    try:
        answer = input("  [y/N] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        console.print("\n[muted]Cancelled.[/]")
        return
    if answer not in ("y", "yes"):
        console.print("[muted]Cancelled.[/]")
        return
    delete_article(db, article.id, user_id=user_id)
    _ok(f"Deleted [accent]{article.id[:8]}[/]")


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
        _ok(f"Published [accent]{count}[/] article(s)")


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
    else:
        display_diff(result["diff_text"], result["stats"])
        