# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

r"""CLI-level reference resolution — terminal on ambiguity.

REPL must NOT use these functions — they call ``_out(ERROR)`` on
zero/multiple matches instead of returning for interactive disambiguation.
"""

from __future__ import annotations

from peerpedia_core.types import short_id

from peerpedia_core.app.refs import (
    format_article_candidates, format_user_candidates,
    format_user_candidates_multiline,
)
from peerpedia_core.cli.info import _out
from peerpedia_core.cli.session import _get_session_user
from peerpedia_core.core import (
    find_users, list_users_by_ids, reconcile_integrity,
    resolve_username_or_alias, search_articles,
)

def _resolve_user_by_atname(db, name: str) -> str:
    """Resolve ``@name`` → user ID via username/alias lookup.

    Terminal: exits on zero or multiple matches.
    """
    session_user = _get_session_user()
    users = resolve_username_or_alias(db, session_user, name)

    if len(users) == 1:
        return users[0].id
    if len(users) > 1:
        _out(None, "AMBIGUOUS_NAME", name=f"@{name}",
             ids=format_user_candidates_multiline(users))
    _out(None, "USER_NOT_FOUND", name=f"@{name}")


# FIXME: wraps find_users with terminal exit — REPL can't use this.
def _resolve_user(db, user_ref: str) -> str:
    """Resolve a user reference to a user ID.

    ``@name`` → username/alias lookup.
    Plain string → delegates to ``find_users`` (UUID → prefix → name).

    Terminal: exits on zero or multiple matches.
    """
    if user_ref.startswith("@"):
        return _resolve_user_by_atname(db, user_ref[1:])

    results = find_users(db, user_ref)
    if len(results) == 1:
        return results[0].id
    if len(results) > 1:
        _out(None, "AMBIGUOUS_NAME", name=user_ref,
             ids=format_user_candidates(results))
        return ""  # unreachable
    _out(None, "USER_NOT_FOUND", name=user_ref)


def _resolve_author_names(db, author_ids: list[str]) -> list[str]:
    """Convert author UUIDs to display names.

    UUIDs that can't be resolved are shown as 8-char prefixes.
    """
    if not author_ids:
        return []
    users = {u.id: u for u in list_users_by_ids(db, set(author_ids))}
    return [users[uid].name if uid in users else short_id(uid) for uid in author_ids]


def _require_resolved_article(db, args_id: str, *, check_integrity: bool = True):
    """Search articles by *args_id* and require exactly one match.

    Terminal: exits on zero or multiple matches.
    """
    results = search_articles(db, args_id)
    if len(results) == 1:
        article = results[0]
        if check_integrity:
            reconcile_integrity(db, article.id)
        return article, article.id
    if len(results) > 1:
        _out(None, "ARTICLE_MULTIPLE", query=args_id,
             ids=format_article_candidates(results))
    _out(None, "ARTICLE_NOT_FOUND", article_id=args_id)
