# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Article commands — create, show, list, edit, publish, delete, scan, diff, compile."""

from __future__ import annotations

import difflib
import sys
from pathlib import Path

from peerpedia_core.app.commandspec import spec_for_cmd_id
from peerpedia_core.app.result import AppResult
from peerpedia_core.app.readmodels.articles import (
    list_articles as _list_articles_orm,
    list_author_ids_batch,
)
from peerpedia_core.cli.decorators import with_context
from peerpedia_core.cli.display import (
    display_article_meta, display_diff, display_empty_article_list,
    display_full_content,
)
from peerpedia_core.cli.info import _open_file, _out, _page, console
from peerpedia_core.compiler import compile_article
from peerpedia_core.editor import (
    open_editor as _open_editor,
    prompt_commit_message as _prompt_commit_message,
)
import peerpedia_core.app.commands.article as _article


# ── Helpers ───────────────────────────────────────────────────────────────

def _get_article_content(args) -> str:
    """Resolve article content from --content, editor, or --no-editor."""
    content = getattr(args, "content", "") or ""
    if content:
        content = content.replace("\\n", "\n").replace("\\t", "\t")
    if not content and not getattr(args, "no_editor", False):
        if not sys.stdout.isatty():
            _out(args, "NO_CONTENT")
        content = _open_editor("")
    return content


def _compute_edit_diff(old_text: str, new_text: str | None,
                        new_title: str | None, content_changed: bool) -> str:
    """Build a diff summary for the commit-message editor template."""
    if content_changed:
        return "\n".join(difflib.unified_diff(
            old_text.splitlines(), (new_text or "").splitlines(),
            fromfile="a/article.md", tofile="b/article.md",
        ))
    if new_title:
        return f"Title: {new_title}"
    return ""


# ── Create ────────────────────────────────────────────────────────────────

@with_context
def _cmd_article_create(ctx, args):
    """Create a new article."""
    return _article.create(
        ctx, title=args.title,
        format=getattr(args, "format", "markdown"),
        content=_get_article_content(args),
        publish=getattr(args, "publish", False),
        scores_str=getattr(args, "scores", None),
    )


# ── Read ──────────────────────────────────────────────────────────────────

@with_context
def _cmd_article_show(ctx, args):
    """Show article details: title, status, authors, score, abstract, content."""
    result = _article.show(ctx, article_ref=args.id)
    if args.json or getattr(args, "show", "meta") != "full":
        return result
    # ── Full content (CLI-specific pager) ──
    src = _article.get_source_path(ctx, article_ref=args.id)
    display_full_content(src.data.get("content", ""), src.data.get("id", ""))
    return result


@with_context
def _cmd_article_list(ctx, args):
    """List articles with optional AND filters."""
    result = _article.list_articles(ctx,
        search_query=args.search or None,
        status_arg=getattr(args, "status", None),
        mine=getattr(args, "mine", False),
        feed=getattr(args, "feed", False),
        bookmarked=getattr(args, "bookmarked", False),
        user_ref=getattr(args, "user", None),
        server=getattr(args, "server", None),
        limit=20,
    )
    items: list[dict] = result.data.get("items", [])
    if not items:
        if getattr(args, "feed", False):
            display_empty_article_list("N_NO_ARTICLES_FEED")
            display_empty_article_list("N_NO_ARTICLES_FEED_HINT")
        elif getattr(args, "mine", False):
            display_empty_article_list("N_NO_ARTICLES_MINE")
            display_empty_article_list("N_NO_ARTICLES_MINE_HINT")
        else:
            display_empty_article_list("N_NO_ARTICLES")
        # Empty-state messages already rendered — suppress double-print
        return AppResult(code="", data=None, params=result.params, notices=result.notices)
    # ── Display search results ──
    author_map = list_author_ids_batch(ctx.db, [a["id"] for a in items])
    item_ids = {a["id"] for a in items}
    for a in _list_articles_orm(ctx.db, limit=len(items)):
        if a.id in item_ids:
            display_article_meta(ctx.db, a, author_ids=author_map.get(a.id, []))
    # Rich already rendered — don't let _render_result double-print raw data
    return AppResult(code="", data=None, params=result.params, notices=result.notices)


# ── Edit ──────────────────────────────────────────────────────────────────

@with_context
def _cmd_article_edit(ctx, args):
    """Edit an article's content or title."""
    article_ref = args.id
    # ── Read current content ──
    result = _article.get_source_path(ctx, article_ref=article_ref)
    raw = result.data.get("content", "")

    new_content = args.content if args.content is not None else (
        _open_editor(raw) if not args.no_editor else None)
    content_changed = new_content is not None and new_content != raw
    title_changed = args.title is not None

    if not content_changed and not title_changed:
        _out(None, "N_NO_EDIT_CHANGES")
        return

    if content_changed:
        message = _prompt_commit_message(
            _compute_edit_diff(raw, new_content, args.title, content_changed))
    elif title_changed:
        message = f"Title: {args.title}"
    else:
        message = "Edit article"
    return _article.edit(ctx, article_ref=article_ref,
        content=new_content, title=args.title, message=message)


# ── Publish / Delete / Scan ───────────────────────────────────────────────

@with_context
def _cmd_article_publish(ctx, args):
    """Publish an article into the sedimentation pool."""
    return spec_for_cmd_id("article.publish").handler(ctx, {
        "id": args.id, "scores": args.scores,
    })


@with_context
def _cmd_article_delete(ctx, args):
    """Delete an article."""
    return spec_for_cmd_id("article.delete").handler(ctx, {"id": args.id})


@with_context
def _cmd_article_scan(ctx, args):
    """Manually trigger sedimentation → published transition."""
    return spec_for_cmd_id("article.scan").handler(ctx, {})


# ── Diff ──────────────────────────────────────────────────────────────────

@with_context
def _cmd_article_diff(ctx, args):
    """Diff two commits of an article."""
    result = spec_for_cmd_id("article.diff").handler(ctx, {
        "id": args.id, "hash1": args.hash1, "hash2": args.hash2,
    })
    diff_text = result.data.get("diff_text", "")
    if not diff_text.strip():
        _out(None, "N_SAME_REVISION")
    else:
        display_diff(diff_text, result.data.get("stats", {}))
    return result


# ── Compile ───────────────────────────────────────────────────────────────

@with_context
def _cmd_compile(ctx, args):
    """Compile an article to PDF/SVG/PNG/HTML."""
    source_result = _article.get_source_path(ctx, article_ref=args.id)
    source_path = source_result.data.get("path", "")
    if not source_path:
        _out(args, "SOURCE_NOT_FOUND", article_id=args.id)
        return
    with console.status("[info]Compiling...[/]", spinner="dots"):
        result = compile_article(Path(source_path), args.format)

    if not result.success:
        code = result.error_code or "COMPILE_FAILED"
        _out(args, code, error=result.error or "", fmt=result.format)

    if result.output_path:
        _out(None, "N_COMPILED", fmt=result.format.upper())
        _out(None, "N_COMPILED_PATH", path=str(result.output_path))
        _open_file(str(result.output_path))
    if result.html_content:
        if len(result.html_content) > 500:
            _page(result.html_content)
        else:
            console.print(result.html_content)
