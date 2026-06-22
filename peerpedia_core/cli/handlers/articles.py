# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Article commands — create, show, list, edit, publish, delete, scan."""

from __future__ import annotations

from peerpedia_core.cli.helpers import (
    _with_db, _resolve_user, _resolve_user_with_key, _find_article_file, _open_editor,
    _prompt_commit_message, _parse_scores, _page, _ok, _die, _json_out,
)
from peerpedia_core.cli.display import (
    _print_panel, _print_table, _status_badge, _stars, console,
)
from peerpedia_core.cli.sync_utils import _try_sync
from peerpedia_core.commands import (
    create_article_with_content, get_article, get_author_ids,
    list_articles, parse_frontmatter, publish_article,
    publish_ready_articles, delete_article, update_article_content, get_user,
)


@_with_db
def _cmd_article_create(db, args):
    """Create a new article.

    args: --title, --format [markdown|typst], --content, --no-editor,
          --publish, --scores, --user, --json

    1. Resolve the author from --user.
    2. Get content from --content, editor, or empty (--no-editor).
    3. Create article + initial git commit via commands layer.
    4. Optionally publish immediately (--publish).
    5. Display result (rich panel or JSON).
    """
    user_id, key_bytes = _resolve_user_with_key(db, args.user)
    user = get_user(db, user_id)
    if user is None:
        _die(f"User '{user_id}' not found — DB inconsistency.")
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
        )
    db.commit()
    _try_sync(db)
    if args.json:
        _json_out(result)
    else:
        _print_panel("Article Created",
            f"[bold]{result['title']}[/]\n"
            f"ID:     [accent]{result['id'][:8]}[/]\n"
            f"Status: {_status_badge(result['status'])}\n"
            f"Hash:   [accent]{result['commit_hash'][:7]}[/]")


@_with_db
def _cmd_article_show(db, args):
    """Show article details: title, status, authors, score, abstract, content.

    args: id [positional], --show [full|meta|content], --user, --json

    TODO(search): accept partial title, author name, or keywords instead
    of requiring the full article ID.  Match against local articles; if
    multiple hits, show a brief list so the user can refine the query.
    """
    article = get_article(db, args.id)
    if not article:
        _die(f"Article [accent]{args.id}[/] not found")
    if args.json:
        _json_out({"id": article.id, "title": article.title, "status": article.status})
        return

    show_mode = getattr(args, "show", "full")

    if show_mode == "content":
        raw = _find_article_file(article.id).read_text()
        _page(raw)
        return

    raw = _find_article_file(article.id).read_text()
    fm = parse_frontmatter(raw)
    title = fm.get("title", article.title)
    abstract = fm.get("abstract", article.abstract)

    scores_str = _stars(article.score) if article.score else "[muted]no scores[/]"
    body = (
        f"[bold info]{title}[/]      {_status_badge(article.status)}\n"
        f"Authors: {', '.join(get_author_ids(db, article.id))}\n"
        f"Score:   {scores_str}\n"
        f"Abstract: {abstract or '[muted]none[/]'}"
    )
    _print_panel("Article", body)

    if show_mode == "full":
        console.print("\n[bold]── Content ──[/]")
        _page(raw)


@_with_db
def _cmd_article_list(db, args):
    """List articles, optionally filtered by status or author. Shows first 20.

    args: --status, --user, --json
    """
    author_id = _resolve_user(db, args.user) if args.user is not None else None
    articles = list_articles(db, status=args.status or None, author_id=author_id)
    if args.json:
        _json_out([{"id": a.id, "title": a.title, "status": a.status} for a in articles])
        return
    rows = [[a.id[:8], a.title, _status_badge(a.status)]
            for a in articles[:20]]
    _print_table(["ID", "Title", "Status"], rows,
                 title=f"{len(articles)} article(s)" + (f" — {args.status}" if args.status else ""))


@_with_db
def _cmd_article_edit(db, args):
    """Edit an article's content or title. Author only.

    args: id [positional], --content, --title, --no-editor, --user, --json
    """
    import difflib

    user_id, key_bytes = _resolve_user_with_key(db, args.user)
    user = get_user(db, user_id)
    if user is None:
        _die(f"User '{user_id}' not found — DB inconsistency.")
    raw = _find_article_file(args.id).read_text()

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
        db, args.id, content=new_content, title=args.title, user_id=user_id,
        message=message,
        signing_key_bytes=key_bytes, pubkey_hex=user.public_key,
    )
    db.commit()
    _try_sync(db)
    if args.json:
        _json_out(result)
    else:
        _ok(f"Updated [accent]{args.id[:8]}[/] — {result['title']}")


@_with_db
def _cmd_article_publish(db, args):
    """Publish an article into the sedimentation pool. Author only.

    args: id [positional], --scores, --user, --json
    """
    user_id = _resolve_user(db, args.user)
    scores = _parse_scores(args.scores)
    result = publish_article(db, args.id, user_id, scores)
    db.commit()
    _try_sync(db)
    if args.json:
        _json_out(result)
    else:
        _ok(f"Published [accent]{args.id[:8]}[/] to sedimentation pool")
        console.print(_stars(scores))


@_with_db
def _cmd_article_delete(db, args):
    """Delete an article.

    args: id [positional], --user, --json
    """
    user_id = _resolve_user(db, args.user)
    article = get_article(db, args.id)
    if not article:
        _die(f"Article [accent]{args.id}[/] not found")

    console.print(f"[warning]Delete [bold]{article.title}[/] (id: {args.id[:8]})?[/]")
    try:
        answer = input("  [y/N] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        console.print("\n[muted]Cancelled.[/]")
        return
    if answer not in ("y", "yes"):
        console.print("[muted]Cancelled.[/]")
        return
    delete_article(db, args.id, user_id=user_id)
    _ok(f"Deleted [accent]{args.id[:8]}[/]")


@_with_db
def _cmd_article_scan(db, args):
    """Manually trigger sedimentation → published transition.

    args: (none beyond common --user, --json)
    """
    count = publish_ready_articles(db)
    db.commit()
    if args.json:
        _json_out({"published": count})
    else:
        _ok(f"Published [accent]{count}[/] article(s)")
