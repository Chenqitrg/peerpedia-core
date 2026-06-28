# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Show and list articles — read-side operations."""

from __future__ import annotations

from peerpedia_core.cli.display import display_empty_article_list, display_full_content
from peerpedia_core.cli.handler import with_context
from peerpedia_core.core import list_author_ids_batch, list_articles
import peerpedia_core.app.commands.article as _article


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
    items = result.data.get("items", [])
    if not items:
        display_empty_article_list(args)
        return result
    author_map = list_author_ids_batch(ctx.db, [a["id"] for a in items])
    for a in list_articles(ctx.db, search_query=None, limit=20):
        from peerpedia_core.cli.helpers import _resolve_and_display_article
        _resolve_and_display_article(ctx.db, a, author_ids=author_map.get(a.id, []))
    return result


