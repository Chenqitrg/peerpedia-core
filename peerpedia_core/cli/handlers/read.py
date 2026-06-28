# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Show and list articles — read-side operations."""

from __future__ import annotations

from peerpedia_core.cli.bundle_utils import _TRANSPORT, _resolve_server_url
from peerpedia_core.cli.display import console
from peerpedia_core.cli.helpers import (
    _with_db, _get_session_user,
    _resolve_and_display_article, _resolve_user,
    _find_article_file, _page, _out, _json_out,
    _out, search_articles,
)
from peerpedia_core.core import (
    reconcile_integrity, get_article_view, get_author_ids_batch, get_user,
    list_article_views, list_articles,
)
from peerpedia_core.core.sync_social import discover_articles
from peerpedia_core.rules.articles import visible_statuses_for_user
from peerpedia_core.types import short_id


@_with_db
def _cmd_article_show(db, args):
    """Show article details: title, status, authors, score, abstract, content.

    args: id [positional], --show [full|meta|content], --json
    """
    results = search_articles(db, args.id)
    if len(results) != 1:
        _out(args, "ARTICLE_NOT_FOUND", article_id=args.id)
    article = results[0]
    reconcile_integrity(db, article.id)
    if args.json:
        _json_out(get_article_view(db, article.id))
        return

    show_mode = getattr(args, "show", "meta")
    _resolve_and_display_article(db, article)
    if show_mode == "full":
        raw = _find_article_file(article.id, db=db).read_text()
        console.print("\n[bold]── Content ──[/]")
        body = raw.split("---\n", 2)[-1].strip() if raw.count("---") >= 2 else raw
        if not body:
            console.print(
                "[muted]No content yet. Use [accent]peerpedia article edit "
                f"{short_id(article.id)}[/] to add content.[/]"
            )
        else:
            _page(raw)


@_with_db
def _cmd_article_list(db, args):
    """List articles with optional AND filters.

    args: --search, --status, --feed, --mine, --bookmarked, --user, --server, --json
    """
    params = _resolve_list_params(db, args)
    if args.json:
        _json_out(list_article_views(db, **params, limit=20))
        return

    articles = list_articles(db, **params, limit=20)
    if not articles:
        _show_empty_list_state(args)
        return
    author_map = get_author_ids_batch(db, [a.id for a in articles])
    for a in articles:
        _resolve_and_display_article(db, a, author_ids=author_map.get(a.id, []))


def _resolve_list_params(db, args) -> dict:
    """Resolve filter flags into kwargs for list_articles / list_article_views.

    Side effect: may discover articles from a remote peer when --server
    and --user are both given.
    """
    resolved_user_id = None
    if args.user:
        resolved_user_id = _resolve_user(db, args.user)

    if args.server and resolved_user_id:
        server = _resolve_server_url(args)
        n = discover_articles(db, _TRANSPORT, server, resolved_user_id)
        db.commit()
        if n > 0:
            console.print(f"[dim]Discovered {n} new article(s) from {server}[/]")

    me = _get_session_user()
    author_id = resolved_user_id
    viewer_id = me if args.feed else None
    if args.mine:
        author_id = me

    if args.status == "draft" and not args.mine:
        args.mine = True
    if args.mine:
        status = args.status or None
    elif args.status:
        status = args.status
    else:
        user_obj = get_user(db, me) if me else None
        status = visible_statuses_for_user(user_obj)

    if args.feed and not args.mine:
        status = status - {"draft"}

    return {
        "status": status,
        "search_query": args.search or None,
        "author_id": author_id,
        "viewer_id": viewer_id,
        "bookmarked_by": (resolved_user_id or me) if args.bookmarked else None,
    }


def _show_empty_list_state(args) -> None:
    """Display context-sensitive guidance when an article list is empty."""
    if args.feed:
        console.print("[muted]Your feed is empty — you're not following anyone yet.[/]")
        console.print("\n  [accent]peerpedia school[/]              ← discover users")
        console.print("  [accent]peerpedia follow @username[/]   ← follow someone")
    elif args.mine:
        console.print("[muted]No articles yet.[/]")
        console.print(f"\n  [accent]peerpedia article create --title \"My Paper\"[/]")
    else:
        _out(args, "EMPTY_ARTICLES")
