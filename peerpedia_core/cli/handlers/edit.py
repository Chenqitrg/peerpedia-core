# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Edit, publish, delete, diff, scan — write-side article operations."""

from __future__ import annotations

import sys

from peerpedia_core.cli.display import display_diff
from peerpedia_core.cli.decorators import with_context
from peerpedia_core.editor import open_editor as _open_editor, prompt_commit_message as _prompt_commit_message
from peerpedia_core.cli.info import _out
import peerpedia_core.app.commands.article as _article


def _get_article_content(args) -> str:
    """Resolve article content from --content, editor, or --no-editor.

    Shared by ``create.py`` and ``edit.py`` — CLI-specific TTY/editor logic.
    """
    content = getattr(args, "content", "") or ""
    if content:
        content = content.replace("\\n", "\n").replace("\\t", "\t")
    if not content and not getattr(args, "no_editor", False):
        if not sys.stdout.isatty():
            _out(args, "NO_CONTENT")
        content = _open_editor("")
    return content


# ── Handlers ─────────────────────────────────────────────────────────────


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

    message = _prompt_commit_message(
        _compute_edit_diff(raw, new_content, args.title, content_changed))
    return _article.edit(ctx, article_ref=article_ref,
        content=new_content, title=args.title, message=message)


@with_context
def _cmd_article_publish(ctx, args):
    """Publish an article into the sedimentation pool."""
    return _article.publish(ctx, article_ref=args.id, scores_str=args.scores)


@with_context
def _cmd_article_delete(ctx, args):
    """Delete an article."""
    return _article.delete(ctx, article_ref=args.id)


@with_context
def _cmd_article_scan(ctx, args):
    """Manually trigger sedimentation → published transition."""
    return _article.scan(ctx)


@with_context
def _cmd_article_diff(ctx, args):
    """Diff two commits of an article."""
    result = _article.diff(ctx, article_ref=args.id,
        hash1=args.hash1, hash2=args.hash2)
    diff_text = result.data.get("diff_text", "")
    if not diff_text.strip():
        _out(None, "N_SAME_REVISION")
    else:
        display_diff(diff_text, result.data.get("stats", {}))
    return result


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
