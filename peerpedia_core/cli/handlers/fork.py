# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Fork and merge commands."""

from __future__ import annotations

from peerpedia_core.cli.bundle_utils import _try_sync
from peerpedia_core.cli.display import console
from peerpedia_core.cli.helpers import (
    _with_db, _get_session_user, _out, search_articles,
)
from peerpedia_core.core import (
    fork_article, create_merge_proposal, accept_merge, withdraw_merge_proposal,
)
from peerpedia_core.types import short_id


@_with_db
def _cmd_fork(db, args):
    """Fork a published article into a new draft copy."""
    results = search_articles(db, args.article_id)
    if len(results) != 1:
        _out(args, "ARTICLE_NOT_FOUND", article_id=args.article_id)
    article = results[0]
    result = fork_article(db, article.id, _get_session_user())
    db.commit()
    _try_sync(db)
    _out(args, "FORKED", result,
         id_short=short_id(result["id"]), title=result["title"])


@_with_db
def _cmd_merge_propose(db, args):
    """Propose merging a fork back into the original article."""
    results = search_articles(db, args.target)
    if len(results) != 1:
        _out(args, "ARTICLE_NOT_FOUND", article_id=args.target)
    target = results[0]
    mp = create_merge_proposal(db, args.fork_id, target.id, _get_session_user())
    db.commit()
    _out(args, "MERGE_PROPOSED", {"id": mp.id, "status": mp.status},
         id_short=short_id(mp.id), target_id=short_id(target.id))


@_with_db
def _cmd_merge_accept(db, args):
    """Accept a merge proposal. May report conflicts."""
    result = accept_merge(db, args.target, args.proposal_id, _get_session_user())
    db.commit()
    _try_sync(db)
    if args.json:
        _out(args, "", result)
    elif result.get("status") == "conflict":
        console.print(f"[warning]⚠ {result['message']}[/]")
    else:
        _out(args, "MERGE_ACCEPTED", result,
             id_short=short_id(result["id"]))


@_with_db
def _cmd_merge_withdraw(db, args):
    """Withdraw a merge proposal."""
    result = withdraw_merge_proposal(db, args.proposal_id, _get_session_user())
    db.commit()
    _out(args, "MERGE_WITHDRAWN", result,
         id_short=short_id(args.proposal_id))
