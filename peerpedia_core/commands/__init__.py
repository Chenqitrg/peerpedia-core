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
articles/ (package)
    Article lifecycle — split into create, update, publish, fork, rollback,
    delete (each ~50-80 lines).  ``__init__.py`` provides read wrappers and
    re-exports the full public API for backward compatibility.

reviews.py
    Review submission.  ``submit_review`` writes review files to the git
    worktree (scores.json + threads/*.md), commits, then caches scores in
    the DB.

merge.py
    Merge proposal acceptance.  ``accept_merge`` runs git merge, rebuilds
    authors from git history, and triggers re-sedimentation if the target
    article was published.

bundle.py
    Bundle application.  ``apply_sync_bundle`` merges fetched git objects and
    reconciles DB state.  ``sync_reviews_from_worktree`` reads reviews from
    git worktree into the DB cache.

workflow.py
    Scoring and reputation orchestration.  ``recompute_article_score`` and
    ``recompute_author_reputation`` gather data, call pure workflow/ functions,
    and write results back.

integrity.py
    Article integrity verification — commit signatures and DB/git consistency
    checks.  Three levels: light (access), full (sync/publish).

views.py
    View layer — returns response-ready dicts.  The ONLY place that calls
    ``.to_dict()`` and composes author enrichment.

Design invariants
-----------------
- All crud functions in this package call ``session.flush()`` only.
  ``session.commit()`` is the caller's responsibility (CLI/REPL entry).
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
from peerpedia_core.commands.bundle import apply_sync_bundle, assert_article_integrity, sync_reviews_from_worktree
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
from peerpedia_core.commands.views import (
    get_article_view,
    get_follower_views,
    get_following_views,
    get_user_view,
    list_article_views,
    list_user_article_views,
)
from peerpedia_core.commands.discover import (
    merge_article_meta,
    merge_bookmarks,
    merge_follows,
    merge_script_maintainers,
    merge_users,
)

# TODO(citation-wiring): citation CRUD (crud_citation.py) is fully
# implemented and tested (100% coverage), but never imported here or exposed
# to CLI/HTTP.  Users cannot add citations, view an article's citation graph,
# or see "cited by" chains.  The compiler does not resolve [@key] markers.
# Wiring plan:
#   1. Import get_cites / get_cited_by / create_or_update_citation here
#   2. Add CLI commands: peerpedia citation add <from> <to>
#   3. Add citation list to article show output
#   4. Wire compiler to resolve [@key] → rendered references
# TODO(notification-system): there is no notification mechanism — no event
# table, no polling endpoint, no push.  Users are unaware of: reviews on
# their articles, merge proposals targeting their articles, new followers,
# articles they follow being published, or sedimentation expiry.  A P2P
# notification system is complex, but a local event table with a
# ``peerpedia notifications`` CLI command is a feasible first step.

from peerpedia_core.config.paths import ARTICLES_DIR
from peerpedia_core.storage.db import db_repl_setup as _db_repl_setup
from peerpedia_core.storage.db.session_utils import db_session_scope as _db_session_scope
from peerpedia_core.storage.db.crud_article import get_author_ids_batch, insert_article
from peerpedia_core.storage.db.crud_user import get_users_by_ids


def db_session(database_url: str):
    """Context manager for a database session with auto commit/rollback/close.

    CLI uses this to get a session; it never imports ``storage/`` directly.
    """
    return _db_session_scope(database_url)


def db_repl_setup(database_url: str):
    """Initialize the database engine and apply migrations.

    Server startup calls this once per process lifetime.
    """
    return _db_repl_setup(database_url)


def health_check(database_url: str) -> list[str]:
    """Check that runtime dependencies (DB, articles directory) are reachable.

    Returns a list of problem strings.  Empty list means healthy.
    """
    problems: list[str] = []
    if not ARTICLES_DIR.is_dir():
        problems.append("articles_dir_missing")
    try:
        with db_session(database_url):
            pass
    except Exception as e:
        problems.append(f"db_unreachable: {e}")
    return problems




__all__ = [
    "accept_merge",
    "add_bookmark",
    "db_session",
    "add_maintainer_to_article",
    "apply_sync_bundle",
    "assert_article_integrity",
    "count_articles",
    "create_article_with_content",
    "create_merge_proposal",
    "create_user",
    "delete_article",
    "follow_user",
    "fork_article",
    "insert_article",
    "get_article",
    "get_article_view",
    "get_author_ids",
    "get_author_ids_batch",
    "get_follower_views",
    "get_following_views",
    "get_user_view",
    "get_users_by_ids",
    "get_followers",
    "get_following",
    "get_bookmarks_for_user",
    "get_reviews_for_article",
    "get_user",
    "is_following",
    "get_user_by_name",
    "sync_reviews_from_worktree",
    "list_articles",
    "list_article_views",
    "list_user_article_views",
    "list_maintainers",
    "merge_article_meta",
    "merge_bookmarks",
    "merge_follows",
    "merge_script_maintainers",
    "merge_users",
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
