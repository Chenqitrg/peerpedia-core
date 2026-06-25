# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

r"""Merge orchestration — accept merge proposals and reconcile state.


Call graph::

    accept_merge
      ├► crud_merge.get_merge_proposal        (validate proposal exists)
      ├► crud_article.get_author_ids          (verify caller is author)
      ├► git_backend.merge_git_repos          (git merge fork into target)
      ├► commands.articles.rebuild_article_authors
      ├► crud_article.set_sink_start          (G2b: only if target was published)
      └► crud_merge.accept_merge_proposal     (update DB proposal status)

State transition
----------------
If the target article was ``published`` before the merge, it enters a 3-day
sedimentation period.  This enforces the rule that any post-publish commit
triggers re-review.  If the target was already in sedimentation, it stays
in sedimentation (``set_sink_start`` only resets the timer, which is the
correct behavior — the merge adds new content that needs review).

Fork-then-merge workflow
------------------------
After publication, a direct edit to the article triggers a 7-day
sedimentation period — the article re-enters peer review before it can be
published again.  For non-trivial changes, authors should work on a **fork**
instead: create a fork via ``peerpedia fork``, make all changes on the fork,
then propose merging back with ``peerpedia merge propose``.  The maintainer
accepts the merge with ``peerpedia merge accept``.  This way, all changes
arrive in a single merge commit, and the article goes through re-review
only once — not once per edit.

Reviewer's checklist
--------------------
- Is the ``was_published`` check done *before* the merge?  The merge itself
  doesn't change the article status, but we need the pre-merge value.
- Are merge conflicts returned as ``{"status": "conflict"}`` rather than
  raising an exception?
"""

from __future__ import annotations

from peerpedia_core.storage.db import Session

from peerpedia_core.config.params import params
from peerpedia_core.exceptions import BadRequestError, NotAuthorizedError, NotFoundError
from peerpedia_core.policies.articles import assert_can_accept_merge, assert_not_folded
from peerpedia_core.storage.db.crud_article import get_article, get_author_ids, set_sink_start
from peerpedia_core.storage.db.crud_maintainer import get_maintainer_ids
from peerpedia_core.storage.db.crud_merge import (
    accept_merge_proposal, get_merge_proposal, withdraw_merge_proposal as _withdraw,
)
from peerpedia_core.storage.db.crud_user import get_user
from peerpedia_core.storage.db.crud_merge import create_merge_proposal as _create
from peerpedia_core.commands.notifications import create_notification
from peerpedia_core.storage.git_backend import (
    DEFAULT_ARTICLES_DIR, MergeConflictError, commit_status_marker,
    get_head_hash, merge_git_repos,
)

from peerpedia_core.commands.articles import rebuild_article_authors


def accept_merge(db: Session, article_id: str, proposal_id: str, user_id: str) -> dict:
    """Accept a merge proposal: git merge fork into target, rebuild authors."""
    user = get_user(db, user_id)
    if user is None:
        raise NotFoundError("User not found")

    mp = get_merge_proposal(db, proposal_id)
    if mp is None:
        raise NotFoundError("Merge proposal not found")
    if mp.target_article_id != article_id:
        raise BadRequestError("Proposal does not belong to this article")
    article = get_article(db, article_id)
    if article is None:
        raise NotFoundError("Article not found")
    mids = get_maintainer_ids(db, article_id)
    assert_can_accept_merge(article, mids, user)
    assert_not_folded(article, threshold=params.reputation.fold_score_threshold)

    was_published = article.status == "published"

    target_repo = DEFAULT_ARTICLES_DIR / article_id
    fork_repo = DEFAULT_ARTICLES_DIR / mp.fork_article_id

    if not (target_repo / ".git").is_dir():
        raise NotFoundError(f"Target article repo not found: {article_id}")
    if not (fork_repo / ".git").is_dir():
        raise NotFoundError(f"Fork article repo not found: {mp.fork_article_id}")

    # G2b: merge_git_repos succeeds → if process dies here before the
    # [status] commit, the DB stays "published" with merged content in git
    # and no marker for integrity repair.  The gap between L97 and L110 is
    # a crash window.
    try:
        merge_git_repos(target_repo, fork_repo, user.name)
    except MergeConflictError:
        return {
            "status": "conflict",
            "message": "Merge conflicts detected.",
        }

    rebuild_article_authors(db, article_id)

    if was_published:
        # Record status transition in git so it survives P2P sync.
        # The merge itself is already committed — this is an empty commit
        # that marks the re-sedimentation triggered by the merge.
        commit_status_marker(target_repo, "sedimentation")
        set_sink_start(db, article_id, params.sink.edit_article_default_days)

    mp = accept_merge_proposal(db, proposal_id)
    head_hash = get_head_hash(target_repo)

    # Notify the proposer that their merge was accepted.
    create_notification(
        db, user_id=mp.proposer_id, event="merge_accepted",
        message=f"{user.name} accepted your merge proposal",
        article_id=article_id, actor_id=user_id,
    )

    return {"id": article.id, "title": article.title, "status": article.status,
            "commit_hash": head_hash}


# ── Write wrapper ────────────────────────────────────────────────────────


def create_merge_proposal(db: Session, fork_id: str, target_id: str, proposer_id: str):
    """Create a merge proposal and notify target article maintainers."""
    proposer = get_user(db, proposer_id)
    proposer_name = proposer.name if proposer else "A user"

    mp = _create(db, fork_id, target_id, proposer_id)

    mids = get_maintainer_ids(db, target_id)
    for mid in mids:
        if mid != proposer_id:
            create_notification(
                db, user_id=mid, event="merge_proposed",
                message=f"{proposer_name} proposed merging a fork into your article",
                article_id=target_id, actor_id=proposer_id,
            )
    return mp


def withdraw_merge_proposal(db: Session, proposal_id: str, user_id: str) -> dict:
    """Withdraw a merge proposal — proposer only.

    Raises ``NotAuthorizedError`` if *user_id* is not the proposer.
    """
    mp = get_merge_proposal(db, proposal_id)
    if mp is None:
        raise NotFoundError("Merge proposal not found")
    if mp.proposer_id != user_id:
        raise NotAuthorizedError(
            f"Only the proposal creator can withdraw this proposal"
        )

    try:
        _withdraw(db, proposal_id)
    except ValueError as e:
        raise BadRequestError(str(e)) from e
    return {
        "id": mp.id,
        "status": "withdrawn",
        "fork_article_id": mp.fork_article_id,
        "target_article_id": mp.target_article_id,
    }
