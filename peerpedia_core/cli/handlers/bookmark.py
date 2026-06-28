# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Bookmark commands."""

from __future__ import annotations

from peerpedia_core.cli.bundle_utils import _try_sync
from peerpedia_core.cli.helpers import (
    _with_db, _get_session_user, _out, search_articles,
)
from peerpedia_core.core import add_bookmark, remove_bookmark
from peerpedia_core.types import short_id


@_with_db
def _cmd_bookmark_add(db, args):
    """Bookmark an article.  args: article_id [positional], --json"""
    results = search_articles(db, args.article_id)
    if len(results) != 1:
        _out(args, "ARTICLE_NOT_FOUND", article_id=args.article_id)
    article = results[0]
    add_bookmark(db, _get_session_user(), article.id)
    db.commit()
    _out(args, "BOOKMARKED", {"bookmarked": True}, name=args.article_id)


@_with_db
def _cmd_bookmark_remove(db, args):
    """Remove a bookmark.  args: article_id [positional], --json"""
    results = search_articles(db, args.article_id)
    if len(results) != 1:
        _out(args, "ARTICLE_NOT_FOUND", article_id=args.article_id)
    article = results[0]
    remove_bookmark(db, _get_session_user(), article.id)
    db.commit()
    _try_sync(db)
    _out(args, "BOOKMARK_REMOVED", {"removed": True}, id_short=short_id(article.id))
