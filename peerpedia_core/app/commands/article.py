# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

r"""Article commands — read, list, create, update, publish, delete.

Each function takes an ``AppContext`` and typed keyword arguments,
calls ``core/`` functions, and returns an ``AppResult`` or raises an
``AppError``.
"""

from __future__ import annotations

from peerpedia_core.app.context import AppContext
from peerpedia_core.app.parsers import parse_scores
from peerpedia_core.app.refs import require_article, require_user, require_user_by_ref
from peerpedia_core.app.result import AppResult
from peerpedia_core.config.params import ARTICLE_EXTENSIONS, article_filename
from peerpedia_core.config.paths import article_repo_path
from peerpedia_core.core import (
    create_article_with_content,
    delete_article,
    diff_article,
    get_article_view,
    get_user,
    list_article_views,
    publish_article,
    publish_ready_articles,
    reconcile_integrity,
    update_article_content,
)
from peerpedia_core.core.sync_social import discover_articles
from peerpedia_core.exceptions import BadRequestError
from peerpedia_core.storage.db._validators import require_draft_status
from peerpedia_core.types import short_id


def show(ctx: AppContext, *, article_ref: str) -> AppResult:
    """Show article metadata (and optionally full content in CLI handler).

    Returns the full article view — the CLI handler decides how much to
    display (``--show meta`` vs ``--show full``).
    """
    # ── Resolve ──
    article = require_article(ctx.db, article_ref)
    # ── Integrity ──
    reconcile_integrity(ctx.db, article.id)
    # ── View ──
    view = get_article_view(ctx.db, article.id)
    return AppResult("", data=view)


def list_articles(
    ctx: AppContext, *,
    search_query: str | None = None,
    status_arg: str | None = None,
    mine: bool = False,
    feed: bool = False,
    bookmarked: bool = False,
    user_ref: str | None = None,
    server: str | None = None,
    limit: int = 20,
) -> AppResult:
    """List articles with optional AND filters.

    Accepts raw CLI flags and resolves them internally: user refs,
    visibility rules, remote discovery.  Returns article views.
    """
    # ── Resolve ──
    resolved_user_id = _resolve_user_ref(ctx, user_ref)
    # ── Remote discovery ──
    if server and resolved_user_id:
        discover_articles(ctx.db, ctx.transport, server, resolved_user_id)
        ctx.db.commit()
    # ── Filters ──
    filters = _article_list_filters(ctx, status_arg=status_arg, mine=mine,
                                    feed=feed, bookmarked=bookmarked,
                                    user_ref=resolved_user_id)
    # ── Query ──
    views = list_article_views(
        ctx.db, search_query=search_query, limit=limit, **filters,
    )
    return AppResult("", data={"items": views})


# ── Write operations ─────────────────────────────────────────────────────


def create(ctx: AppContext, *, title: str, format: str = "markdown",
           content: str = "", publish: bool = False,
           scores_str: str | None = None) -> AppResult:
    """Create a new article, optionally publishing immediately."""
    # ── Resolve ──
    user_id = require_user(ctx)
    # ── Execute ──
    user = get_user(ctx.db, user_id)
    result = create_article_with_content(
        ctx.db, title=title, content=content, format=format,
        author_ids=[user_id],
        signing_key_bytes=ctx.signing_key_bytes,
        pubkey_hex=user.public_key if user else None,
    )
    if publish:
        scores = parse_scores(scores_str)
        result = publish_article(
            ctx.db, result["id"], user_id, scores,
            signing_key_bytes=ctx.signing_key_bytes,
            pubkey_hex=user.public_key if user else None,
        )
    ctx.db.commit()
    return AppResult("ARTICLE_CREATED", data=result,
        params={"id_short": short_id(result["id"]), "title": result["title"]})


def edit(ctx: AppContext, *, article_ref: str, content: str | None = None,
         title: str | None = None, message: str, user_id: str | None = None) -> AppResult:
    """Edit an article's content or title."""
    # ── Resolve ──
    user_id = user_id or require_user(ctx)
    article = require_article(ctx.db, article_ref)
    # ── Execute ──
    user = get_user(ctx.db, user_id)
    result = update_article_content(
        ctx.db, article.id, content=content, title=title, user_id=user_id,
        message=message, signing_key_bytes=ctx.signing_key_bytes,
        pubkey_hex=user.public_key if user else None,
    )
    ctx.db.commit()
    return AppResult("ARTICLE_UPDATED", data=result,
        params={"id_short": short_id(article.id), "title": result.get("title", "")})


def publish(ctx: AppContext, *, article_ref: str, scores_str: str) -> AppResult:
    """Publish an article into the sedimentation pool."""
    # ── Resolve + Guard ──
    user_id = require_user(ctx)
    article = require_article(ctx.db, article_ref)
    require_draft_status(article)
    scores = parse_scores(scores_str)
    # ── Execute ──
    user = get_user(ctx.db, user_id)
    result = publish_article(
        ctx.db, article.id, user_id, scores,
        signing_key_bytes=ctx.signing_key_bytes,
        pubkey_hex=user.public_key if user else None,
    )
    ctx.db.commit()
    return AppResult("ARTICLE_PUBLISHED", data=result,
        params={"id_short": short_id(article.id)})


def delete(ctx: AppContext, *, article_ref: str) -> AppResult:
    """Delete an article."""
    # ── Resolve ──
    user_id = require_user(ctx)
    article = require_article(ctx.db, article_ref)
    # ── Execute ──
    delete_article(ctx.db, article.id, user_id=user_id)
    ctx.db.commit()
    return AppResult("ARTICLE_DELETED",
        data={"id": article.id, "deleted": True},
        params={"id_short": short_id(article.id)})


def scan(ctx: AppContext) -> AppResult:
    """Manually trigger sedimentation → published transition."""
    count = publish_ready_articles(ctx.db)
    ctx.db.commit()
    code = "ARTICLE_SCANNED" if count else "ARTICLE_SCANNED_EMPTY"
    return AppResult(code, data={"published": count}, params={"count": count})


def diff(ctx: AppContext, *, article_ref: str, hash1: str | None = None,
         hash2: str | None = None) -> AppResult:
    """Diff two commits of an article."""
    article = require_article(ctx.db, article_ref)
    try:
        result = diff_article(article.id, hash1, hash2)
    except ValueError as e:
        raise BadRequestError(code="DIFF_INVALID_HASH", error=str(e))
    except FileNotFoundError as e:
        raise BadRequestError(code="DIFF_REPO_MISSING", error=str(e))
    return AppResult("", data=result)


def get_source_path(ctx: AppContext, *, article_ref: str) -> AppResult:
    """Return the source file path for an article (for full-content display)."""
    article = require_article(ctx.db, article_ref)
    rp = article_repo_path(article.id)
    for ext in ARTICLE_EXTENSIONS:
        f = rp / article_filename(ext)
        if f.exists():
            return AppResult("", data={"id": article.id, "path": str(f), "content": f.read_text()})
    return AppResult("", data={"id": article.id, "path": "", "content": ""})


# ═══════════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════════


def _resolve_user_ref(ctx: AppContext, user_ref: str | None) -> str | None:
    """Resolve a user reference to a canonical ID, or return None."""
    if not user_ref:
        return None
    return require_user_by_ref(ctx.db, user_ref).id


def _article_list_filters(
    ctx: AppContext, *,
    status_arg: str | None = None,
    mine: bool = False,
    feed: bool = False,
    bookmarked: bool = False,
    user_ref: str | None = None,
) -> dict:
    """Convert CLI flags → filter dict for list_article_views.  Pure data transform."""
    me = ctx.current_user_id or ""

    author_id = user_ref
    if mine:
        author_id = me

    if status_arg == "draft" and not mine:
        mine = True
    if mine:
        status = status_arg or None
    elif status_arg:
        status = status_arg
    else:
        from peerpedia_core.rules.articles import visible_statuses_for_user
        user_obj = get_user(ctx.db, me) if me else None
        status = visible_statuses_for_user(user_obj)

    if feed and not mine:
        status = status - {"draft"} if status else None

    return {
        "status": status,
        "author_id": author_id,
        "viewer_id": me if feed else None,
        "bookmarked_by": (user_ref or me) if bookmarked else None,
    }
