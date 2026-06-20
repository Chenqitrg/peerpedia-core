# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

r"""Sync orchestration — apply incoming git bundles and reconcile DB state.

This module bridges the gap between git (SOT for review content) and the DB
(score cache).  ``git_sync_reviews`` is the key function — it reads review
scores from the git worktree and writes them into the DB Review cache, so
that ``recompute_article_score`` can see reviews that arrived via sync.

Call graph::

    apply_sync_bundle
      ├► git (merge FETCH_HEAD)
      ├► commands.articles.rebuild_article_authors
      ├► git_sync_reviews                    ← G5 fix: sync before scoring
      ├► commands.workflow.recompute_article_score
      └▻ commands.workflow.publish_ready_articles  ← G4 trigger

    git_sync_reviews
      ├► git_backend.list_review_dirs        (list reviews/*/ directories)
      ├► for each dir:
      │     ├► git_backend.read_review_scores (parse scores.json)
      │     └► crud_review.upsert_review      (write to DB cache)
      └► Fail fast: missing or malformed scores.json raises immediately

Key design decision — reviewer identity
----------------------------------------
``git_sync_reviews`` uses the git directory name directly as ``reviewer_id``
in the DB.  During sedimentation, reviews are stored under anonymous hashes
(``sha256(article_id:reviewer_id)[:12]``).  These 12-char hex strings are
valid DB ``reviewer_id`` values — ``derive_anonymous_name`` handles display.
When the article publishes, the real identity can be revealed separately.

Reviewer's checklist
--------------------
- Is ``git_sync_reviews`` called before every ``recompute_article_score``
  that follows a git state change?
- Does ``apply_sync_bundle`` trigger ``publish_ready_articles`` after
  reconciliation?  (A sync might bring reviews that make an article
  publishable.)
- Fail fast: are malformed scores.json files raised, not skipped?
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from peerpedia_core.storage.db.crud_article import get_article
from peerpedia_core.storage.db.crud_review import upsert_review
from peerpedia_core.storage.git_backend import (
    DEFAULT_ARTICLES_DIR,
    MergeConflictError,
    list_review_dirs,
    read_review_scores,
)

from peerpedia_core.commands.articles import rebuild_article_authors
from peerpedia_core.commands.workflow import recompute_article_score


def git_sync_reviews(db: Session, article_id: str) -> None:
    """Sync review scores from git worktree into the DB Review cache.

    Reads every ``reviews/{dir}/scores.json`` in the article's git worktree
    and upserts into the DB.  Uses the current git HEAD as commit_hash.

    Directory names are used directly as reviewer_id — anonymous hashes and
    real UUIDs both work (derive_anonymous_name handles display).

    Fail fast: malformed or missing scores.json raises immediately.
    """
    import git

    rp = DEFAULT_ARTICLES_DIR / article_id
    head_hash = git.Repo(rp).head.commit.hexsha

    for dir_name in list_review_dirs(rp):
        scores = read_review_scores(rp, dir_name)
        if scores is None:
            raise FileNotFoundError(
                f"scores.json not found in reviews/{dir_name}/ for article {article_id}"
            )
        upsert_review(
            db,
            article_id=article_id,
            commit_hash=head_hash,
            reviewer_id=dir_name,
            scores=scores,
        )


def apply_sync_bundle(
    db: Session,
    article_id: str,
    *,
    ff_only: bool = False,
) -> str:
    """Merge fetched bundle objects (``FETCH_HEAD``) and reconcile DB state.

    The caller must have already called ``ingest_bundle`` to verify + fetch
    objects into the repo.  This function only does the merge and DB
    reconciliation.  It does NOT import from ``sync/``.

    After merge: syncs reviews from git, recomputes article score, and
    triggers publish_ready_articles to catch any newly-publishable articles.

    Returns the new HEAD commit hash.

    Raises:
        MergeConflictError: merge conflict (ff-only rejected).
    """
    import git

    rp = DEFAULT_ARTICLES_DIR / article_id
    repo = git.Repo(rp)

    merge_args = ["FETCH_HEAD", "--ff-only"] if ff_only else ["FETCH_HEAD"]
    try:
        repo.git.merge(*merge_args)
    except git.GitCommandError as e:
        try:
            repo.git.merge("--abort")
        except git.GitCommandError:
            pass
        raise MergeConflictError(f"Merge failed: {e}") from e

    new_head = repo.head.commit.hexsha

    # DB reconciliation — git state changed, DB must follow
    rebuild_article_authors(db, article_id)

    # Sync reviews from git before scoring — git is the SOT (G5)
    git_sync_reviews(db, article_id)

    recompute_article_score(db, article_id)

    # Trigger auto-publish for any articles that may now be ready (G4)
    from peerpedia_core.commands.workflow import publish_ready_articles
    publish_ready_articles(db)

    return new_head
