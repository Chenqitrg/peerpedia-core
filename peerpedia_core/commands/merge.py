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

Reviewer's checklist
--------------------
- Is the ``was_published`` check done *before* the merge?  The merge itself
  doesn't change the article status, but we need the pre-merge value.
- Are merge conflicts returned as ``{"status": "conflict"}`` rather than
  raising an exception?
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from peerpedia_core.config.params import params
from peerpedia_core.exceptions import BadRequestError, NotFoundError
from peerpedia_core.policies.articles import assert_can_accept_merge
from peerpedia_core.storage.db.crud_article import get_article, get_author_ids, set_sink_start
from peerpedia_core.storage.db.crud_merge import accept_merge_proposal, get_merge_proposal
from peerpedia_core.storage.db.crud_user import get_user
from peerpedia_core.storage.git_backend import DEFAULT_ARTICLES_DIR, MergeConflictError, merge_git_repos

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
    assert_can_accept_merge(db, article_id, user)

    target_repo = DEFAULT_ARTICLES_DIR / article_id
    fork_repo = DEFAULT_ARTICLES_DIR / mp.fork_article_id

    if not (target_repo / ".git").is_dir():
        raise NotFoundError(f"Target article repo not found: {article_id}")
    if not (fork_repo / ".git").is_dir():
        raise NotFoundError(f"Fork article repo not found: {mp.fork_article_id}")

    # G2b: check status before merge — if published, trigger re-sedimentation
    article = get_article(db, article_id)
    was_published = article is not None and article.status == "published"

    try:
        merge_git_repos(target_repo, fork_repo, user.name)
    except MergeConflictError:
        return {
            "status": "conflict",
            "message": "Merge conflicts detected.",
        }

    rebuild_article_authors(db, article_id)

    if was_published:
        set_sink_start(db, article_id, params.sink.edit_article_default_days)

    mp = accept_merge_proposal(db, proposal_id)
    import git
    head_hash = git.Repo(target_repo).head.commit.hexsha
    return {"id": article.id, "title": article.title, "status": article.status,
            "commit_hash": head_hash}


# ── Write wrapper ────────────────────────────────────────────────────────


def create_merge_proposal(db: Session, fork_id: str, target_id: str, proposer_id: str):
    """Create a merge proposal from a fork to its original article."""
    from peerpedia_core.storage.db.crud_merge import create_merge_proposal as _create
    return _create(db, fork_id, target_id, proposer_id)
