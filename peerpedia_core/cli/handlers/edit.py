# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Edit, publish, delete, diff, scan — write-side article operations."""

from __future__ import annotations

import sys
from datetime import timedelta

from peerpedia_core.cli.bundle_utils import _try_sync
from peerpedia_core.cli.display import console, display_diff
from peerpedia_core.cli.helpers import (
    _with_db, _get_session_user, _get_session_key,
    _resolve_and_display_article, _find_article_file, _open_editor,
    _prompt_commit_message, _parse_scores, _show, _json_out, _die,
    _require_resolved_article, search_articles,
)
from peerpedia_core.config.params import params
from peerpedia_core.core import (
    diff_article, get_article, publish_article,
    publish_ready_articles, delete_article, update_article_content,
)
from peerpedia_core.storage.db.guards import require_user
from peerpedia_core.types import short_id


def _compute_edit_diff(old_text: str, new_text: str | None,
                      new_title: str | None, content_changed: bool) -> str:
    """Build a diff summary for the commit-message editor template."""
    import difflib
    if content_changed:
        return "\n".join(difflib.unified_diff(
            old_text.splitlines(), (new_text or "").splitlines(),
            fromfile="a/article.md", tofile="b/article.md",
        ))
    if new_title:
        return f"Title: {new_title}"
    return ""


def _get_article_content(args) -> str:
    """Resolve article content from --content, editor, or --no-editor."""
    content = args.content or ""
    if content and args.content:
        content = content.replace("\\n", "\n").replace("\\t", "\t")
    if not content and not args.no_editor:
        if not sys.stdout.isatty():
            _out(args, "NO_CONTENT")
        content = _open_editor("")
    return content


@_with_db
def _cmd_article_edit(db, args):
    """Edit an article's content or title.  args: id [positional], --content, --title, --no-editor, --json"""
    article, article_id = _require_resolved_article(db, args.id)
    user_id = _get_session_user()
    key_bytes = _get_session_key()
    user = require_user(db, user_id)
    raw = _find_article_file(article_id).read_text()

    new_content = args.content if args.content is not None else (
        _open_editor(raw) if not args.no_editor else None)
    content_changed = new_content is not None and new_content != raw
    title_changed = args.title is not None

    if not content_changed and not title_changed:
        console.print("[muted]No changes — nothing to commit.[/]")
        return

    diff = _compute_edit_diff(raw, new_content, args.title, content_changed)
    message = _prompt_commit_message(diff)

    result = update_article_content(
        db, article_id, content=new_content, title=args.title, user_id=user_id,
        message=message, signing_key_bytes=key_bytes, pubkey_hex=user.public_key,
    )
    db.commit()
    _try_sync(db)
    _out(args, "ARTICLE_UPDATED", result,
         id_short=short_id(article_id), title=result["title"])
    article = get_article(db, article_id)
    _resolve_and_display_article(db, article)


@_with_db
def _cmd_article_publish(db, args):
    """Publish an article into the sedimentation pool.  args: id [positional], --scores, --json"""
    article, article_id = _require_resolved_article(db, args.id)
    user_id = _get_session_user()
    key_bytes = _get_session_key()
    user = require_user(db, user_id)
    scores = _parse_scores(args.scores)
    result = publish_article(db, article_id, user_id, scores,
                             signing_key_bytes=key_bytes, pubkey_hex=user.public_key)
    db.commit()
    _try_sync(db)

    if args.json:
        _json_out(result)
        return

    article = get_article(db, article_id)
    sink_end = ""
    if article.sink_start:
        end_date = article.sink_start + timedelta(days=params.sink.new_article_default_days)
        sink_end = end_date.strftime("%Y-%m-%d")
    _out(args, "ARTICLE_PUBLISHED", result,
         id_short=short_id(article_id))
    if sink_end:
        console.print(f"[dim]Review window: auto-publishes after {sink_end}.[/]")
    _resolve_and_display_article(db, article)
    console.print(
        f"[dim]Next: [accent]peerpedia share add {short_id(article_id)}[/] "
        f"  [accent]peerpedia review invite {short_id(article_id)} --user <id>[/][/]"
    )


@_with_db
def _cmd_article_delete(db, args):
    """Delete an article.  args: id [positional], --json"""
    user_id = _get_session_user()
    article, article_id = _require_resolved_article(db, args.id)

    if args.json and getattr(args, 'force', False):
        delete_article(db, article_id, user_id=user_id)
        _out(args, "", {"id": article_id, "deleted": True})
        return

    console.print(f"[warning]Delete [bold]{article.title}[/] (id: {short_id(article_id)})?[/]")
    try:
        answer = input("  [y/N] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        console.print("\n[muted]Cancelled.[/]")
        return
    if answer not in ("y", "yes"):
        console.print("[muted]Cancelled.[/]")
        return
    delete_article(db, article_id, user_id=user_id)
    _out(args, "ARTICLE_DELETED", id_short=short_id(article_id))


@_with_db
def _cmd_article_scan(db, args):
    """Manually trigger sedimentation → published transition.  args: (none)"""
    count = publish_ready_articles(db)
    db.commit()
    code = "ARTICLE_SCANNED" if count else "ARTICLE_SCANNED_EMPTY"
    _out(args, code, {"published": count}, count=count)


@_with_db
def _cmd_article_diff(db, args):
    """Diff two commits of an article.  args: id [positional], hash1, hash2, --json"""
    results = search_articles(db, args.id)
    if len(results) != 1:
        _out(args, "ARTICLE_NOT_FOUND", article_id=args.id)
    article = results[0]
    try:
        result = diff_article(article.id, args.hash1, args.hash2)
    except ValueError as e:
        _out(args, "DIFF_INVALID_HASH", error=str(e))
    except FileNotFoundError as e:
        _out(args, "DIFF_REPO_MISSING", error=str(e))

    if args.json:
        _out(args, "", result)
    elif not result["diff_text"].strip():
        console.print("[muted]These are the same revision — no changes to show.[/]")
    else:
        display_diff(result["diff_text"], result["stats"])
