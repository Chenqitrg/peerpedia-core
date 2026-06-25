# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Maintainer commands — manage who controls an article."""

from __future__ import annotations

from peerpedia_core.cli.helpers import _with_db, _get_session_user, _ok, _json_out, _output_result, _resolve_article_id, _require_resolved_article
from peerpedia_core.cli.display import _print_table, console
from peerpedia_core.commands import (
    add_maintainer_to_article,
    consent_to_publish,
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
                   f"Maintainer [accent]{args.target_user[:8]}[/] added to article [accent]{article_id[:8]}[/]")


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
                   f"Maintainer [accent]{args.target_user[:8]}[/] removed from article [accent]{article_id[:8]}[/]")


@_with_db
def _cmd_maintainer_list(db, args):
    """List all maintainers of an article.

    args: article_id [positional], --json
    """
    article = _resolve_article_id(db, args.article_id)
    ids = list_maintainers(db, article.id)
    if args.json:
        _json_out({"article_id": article.id, "maintainers": ids})
        return
    if not ids:
        console.print("[muted]No maintainers.[/]")
        return
    rows = [[uid[:8]] for uid in ids]
    _print_table(["Maintainer ID"], rows, title=f"{len(rows)} maintainer(s)")


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
                   f"Consent recorded for article [accent]{article_id[:8]}[/]")


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
                   f"Consent revoked for article [accent]{article_id[:8]}[/]")
