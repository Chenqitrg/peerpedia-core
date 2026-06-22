# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Commands layer — the sole module that touches both git and DB.

**This is the ONLY package that can import both ``storage/git_backend``
and ``storage/db/``.**  CLI, REPL, sync — everything external — must go
through this facade: ``from peerpedia_core.commands import ...``.

Hard rules
----------
- External callers MUST import from here, never from submodules directly.
- Submodules MAY import each other directly (``from .articles import ...``)
  to avoid circular imports through ``__init__.py``.
- No function may have an internal ``from peerpedia_core.*`` import — if
  a function needs an import the module doesn't have, the function is in
  the wrong module ("红杏出墙").
- All CRUD calls use ``flush()`` only; ``commit()`` is the caller's job.

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
    the DB.  ``write_review_to_git`` is the low-level git writer shared
    with articles.py's ``publish_article``.

merge.py
    Merge proposal acceptance.  ``accept_merge`` runs git merge, rebuilds
    authors from git history, and triggers re-sedimentation if the target
    article was published.

sync.py
    Sync bundle application.  ``apply_sync_bundle`` merges fetched git
    objects and reconciles DB state.  ``sync_reviews_from_worktree`` reads every
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
from peerpedia_core.commands.maintainers import (
    add_maintainer_to_article,
    list_maintainers,
    remove_maintainer_from_article,
)
from peerpedia_core.commands.merge import accept_merge, create_merge_proposal
from peerpedia_core.commands.reviews import get_reviews_for_article, submit_review
from peerpedia_core.commands.sync import apply_sync_bundle, sync_reviews_from_worktree
from peerpedia_core.commands.users import (
    create_user,
    follow_user,
    get_followers,
    get_following,
    get_user,
    get_user_by_name,
    is_following,
    search_users,
    unfollow_user,
    update_user_public_key,
    update_user_salt,
)
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
    "add_maintainer_to_article",
    "apply_sync_bundle",
    "count_articles",
    "create_article_with_content",
    "create_merge_proposal",
    "create_user",
    "delete_article",
    "follow_user",
    "fork_article",
    "get_article",
    "get_author_ids",
    "get_followers",
    "get_following",
    "get_bookmarks_for_user",
    "get_reviews_for_article",
    "get_user",
    "is_following",
    "get_user_by_name",
    "sync_reviews_from_worktree",
    "list_articles",
    "list_maintainers",
    "parse_frontmatter",
    "publish_article",
    "publish_ready_articles",
    "rebuild_article_authors",
    "recalculate_all_reputations",
    "recompute_article_score",
    "recompute_author_reputation",
    "remove_bookmark",
    "remove_maintainer_from_article",
    "rollback_article",
    "search_users",
    "submit_review",
    "unfollow_user",
    "update_article_content",
    "update_user_public_key",
    "update_user_salt",
]
