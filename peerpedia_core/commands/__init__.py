# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Commands layer — the sole module that touches both git and DB.

This package is the gatekeeper for all data access.  Every read and write that
involves both storage backends must go through a function in this package.
CLI, REPL, and sync code call into here; they never import git_backend or
crud_* directly.

Submodules
----------
articles.py
    Article lifecycle: create, update, publish, fork, rollback.
    These are the most complex functions because they must coordinate git
    commits with DB metadata sync.  Every function follows git-first: commit
    content to the git repo, then update the DB cache.

reviews.py
    Review submission.  ``submit_review`` writes review files to the git
    worktree (scores.json + threads/*.md), commits, then caches scores in
    the DB.  ``_write_review_to_git`` is the low-level git writer shared
    with articles.py's ``publish_article``.

merge.py
    Merge proposal acceptance.  ``accept_merge`` runs git merge, rebuilds
    authors from git history, and triggers re-sedimentation if the target
    article was published.

sync.py
    Sync bundle application.  ``apply_sync_bundle`` merges fetched git
    objects and reconciles DB state.  ``git_sync_reviews`` reads every
    reviews/*/scores.json from the git worktree and upserts into the DB
    Review cache — closing the gap where sync'd reviews were invisible to
    scoring.

workflow.py
    Scheduled and reactive workflow orchestration.
    ``publish_ready_articles`` scans for sedimentation articles whose sink
    time has elapsed and publishes them.  ``recompute_article_score`` and
    ``recompute_author_reputation`` are the DB-aware wrappers that gather
    data, call pure workflow/ functions, and write results back.

Design invariants
-----------------
- All crud functions in this package call ``session.flush()`` only.
  ``session.commit()`` is the caller's responsibility (CLI/REPL entry).
- Internal cross-module imports (e.g. articles.py importing from reviews.py)
  use deferred imports inside function bodies to avoid circular dependencies
  at import time.
- Public API is re-exported here; callers should import from
  ``peerpedia_core.commands``, not from submodules directly.
"""

from peerpedia_core.commands.articles import (
    count_articles,
    create_article_with_content,
    delete_article,
    fork_article,
    get_article,
    get_author_ids,
    list_articles,
    publish_article,
    rebuild_article_authors,
    rollback_article,
    update_article_content,
)
from peerpedia_core.commands.bookmarks import add_bookmark, get_bookmarks_for_user, remove_bookmark
from peerpedia_core.frontmatter import parse_frontmatter
from peerpedia_core.commands.merge import accept_merge, create_merge_proposal
from peerpedia_core.commands.reviews import get_reviews_for_article, submit_review
from peerpedia_core.commands.sync import apply_sync_bundle, git_sync_reviews
from peerpedia_core.commands.users import create_user, get_user, get_user_by_name
from peerpedia_core.commands.workflow import (
    publish_ready_articles,
    recalculate_all_reputations,
    recompute_article_score,
    recompute_author_reputation,
)
from peerpedia_core.storage.db.session_utils import db_session_scope as _db_session_scope


def db_session(database_url: str):
    """Context manager for a database session with auto commit/rollback/close.

    CLI and REPL use this to get a session; they never import ``storage/`` directly.
    """
    return _db_session_scope(database_url)

__all__ = [
    "accept_merge",
    "add_bookmark",
    "apply_sync_bundle",
    "count_articles",
    "create_article_with_content",
    "create_merge_proposal",
    "create_user",
    "delete_article",
    "fork_article",
    "get_article",
    "get_author_ids",
    "get_bookmarks_for_user",
    "get_reviews_for_article",
    "get_user",
    "get_user_by_name",
    "git_sync_reviews",
    "list_articles",
    "parse_frontmatter",
    "publish_article",
    "publish_ready_articles",
    "rebuild_article_authors",
    "recalculate_all_reputations",
    "recompute_article_score",
    "recompute_author_reputation",
    "remove_bookmark",
    "rollback_article",
    "submit_review",
    "update_article_content",
]
