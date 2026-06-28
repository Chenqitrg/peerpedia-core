# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Maintainer commands — manage who controls an article."""

from __future__ import annotations

# FIXME: search_articles should be get_article. import will disappear when fixed.
from peerpedia_core.cli.helpers import _with_db, _get_session_user, _ok, _json_out, _output_result, search_articles, _require_resolved_article
from peerpedia_core.cli.display import _print_table, console
from peerpedia_core.types import short_id
from peerpedia_core.core import (
    add_maintainer_to_article,
    consent_to_publish,
    get_users_by_ids,
    list_maintainers,
    remove_maintainer_from_article,
    revoke_publish_consent,
)


@_with_db
def _cmd_maintainer_add(db, args):
    """Add a maintainer to an article.

    args: article_id [positional], --target-user, --json
    """
    article, article_id = _require_resolved_article(db, args.article_id)
    caller_id = _get_session_user()
    result = add_maintainer_to_article(db, article_id, args.target_user, caller_id)
    db.commit()
    _output_result(args, result,
                   f"Maintainer [accent]{short_id(args.target_user)}[/] added to article [accent]{short_id(article_id)}[/]")


@_with_db
def _cmd_maintainer_remove(db, args):
    """Remove a maintainer from an article.

    args: article_id [positional], --target-user, --json
    """
    article, article_id = _require_resolved_article(db, args.article_id)
    caller_id = _get_session_user()
    result = remove_maintainer_from_article(db, article_id, args.target_user, caller_id)
    db.commit()
    _output_result(args, result,
                   f"Maintainer [accent]{short_id(args.target_user)}[/] removed from article [accent]{short_id(article_id)}[/]")


@_with_db
def _cmd_maintainer_list(db, args):
    """List all maintainers of an article.

    args: article_id [positional], --json
    """
    # FIXME: args.article_id is a known ID, should use get_article(db, args.article_id).
    results = search_articles(db, args.article_id)
    if len(results) != 1:
        _out(args, "ARTICLE_NOT_FOUND", article_id=args.article_id)
    article = results[0]
    ids = list_maintainers(db, article.id)
    if args.json:
        _json_out({"article_id": article.id, "maintainers": ids})
        return
    if not ids:
        console.print("[muted]No maintainers.[/]")
        return
    # Resolve UUIDs to display names.
    users = {u.id: u for u in get_users_by_ids(db, set(ids))}
    rows = [[f"{users[uid].name} ({short_id(uid)})" if uid in users else short_id(uid)] for uid in ids]
    _print_table(["Maintainer"], rows, title=f"{len(rows)} maintainer(s)")


@_with_db
def _cmd_maintainer_consent(db, args):
    """Record consent to publish/merge the article.

    args: article_id [positional], --json
    """
    article, article_id = _require_resolved_article(db, args.article_id)
    user_id = _get_session_user()
    result = consent_to_publish(db, article_id, user_id)
    db.commit()
    _output_result(args, result,
                   f"Consent recorded for article [accent]{short_id(article_id)}[/]")


@_with_db
def _cmd_maintainer_revoke(db, args):
    """Revoke consent to publish/merge the article.

    args: article_id [positional], --json
    """
    article, article_id = _require_resolved_article(db, args.article_id)
    user_id = _get_session_user()
    result = revoke_publish_consent(db, article_id, user_id)
    db.commit()
    _output_result(args, result,
                   f"Consent revoked for article [accent]{short_id(article_id)}[/]")
