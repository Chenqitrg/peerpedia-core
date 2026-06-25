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
    diff_article,
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
    consent_to_publish,
    list_maintainers,
    remove_maintainer_from_article,
    revoke_publish_consent,
)
from peerpedia_core.commands.merge import accept_merge, create_merge_proposal, withdraw_merge_proposal
from peerpedia_core.commands.reviews import get_reviews_for_article, invite_reviewer, rate_review_helpfulness, submit_reply, submit_review
from peerpedia_core.commands.shares import (
    add_share, get_feed_shares, get_shares_for_user, remove_share,
)
from peerpedia_core.commands.bundle import apply_sync_bundle, assert_article_integrity, sync_reviews_from_worktree
from peerpedia_core.commands.users import (
    create_user,
    create_user_stub,
    follow_user,
    list_users,
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
    merge_shares,
    merge_users,
)
from peerpedia_core.commands.notifications import (
    count_unread,
    create_notification,
    get_notifications,
    mark_read,
    merge_notifications,
)

# TODO(citation-system): three independent subsystems, ordered by dependency:
#
#   1. BIB PARSING (SOT — git) — parse .bib files in article git repos.
#      BibTeX parser that reads author/title/venue/year/key from a .bib
#      file inside the article repo.  ADR-007: git is SOT for citation
#      metadata.  The BibTeX key is the canonical @key reference.
#      Needs: a bib parser module (storage/bib_parser.py or similar).
#
#   2. INLINE @key PARSING (compiler) — resolve @key citation markers in
#      Markdown/Typst source.  @ prefix is the delimiter (no brackets).
#      Distinguish from email addresses (name@domain.com has a dot after @).
#      Parse @key → look up BibTeX entry → format rendered reference.
#      Needs: compiler.py changes, regex/parser for @key detection.
#
#   3. PROBABILITY ACCUMULATION (DB cache) — forward_prob / backward_prob
#      are graph-topology scores computed from click/view events.  Need a
#      click-tracking mechanism: user reads article A → clicks citation to
#      article B → P(A→B) increases.  Could use a read-event table
#      (article_id, viewer_id, timestamp, referrer_article_id).  Only
#      forward_prob / backward_prob live in DB — everything else is SOT
#      in git.  Needs: event table, click endpoint, scoring function.
#
#   CRUD (crud_citation.py) is fully implemented and tested.  The missing
#   pieces are all above it: bib parsing, @key resolution, probability
#   accumulation.  Without those three, the Citation table is inert.
# Notification system: model + CRUD + CLI + P2P sync (completed).

from peerpedia_core.config.paths import ARTICLES_DIR
from peerpedia_core.storage.db import db_repl_setup as _db_repl_setup
from peerpedia_core.storage.db.session_utils import db_session_scope as _db_session_scope
from peerpedia_core.storage.db.crud_article import get_author_ids_batch, insert_article
from peerpedia_core.storage.db.crud_alias import (
    list_aliases, remove_alias, resolve_username_or_alias, set_alias,
)
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
    "add_share",
    "db_session",
    "withdraw_merge_proposal",
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
    "get_feed_shares",
    "get_follower_views",
    "get_following_views",
    "get_shares_for_user",
    "get_user_view",
    "get_users_by_ids",
    "list_aliases",
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
    "merge_shares",
    "merge_users",
    "parse_frontmatter",
    "publish_article",
    "publish_ready_articles",
    "rebuild_article_authors",
    "resolve_username_or_alias",
    "recalculate_all_reputations",
    "recompute_article_score",
    "recompute_author_reputation",
    "remove_alias",
    "remove_bookmark",
    "remove_share",
    "remove_maintainer_from_article",
    "rollback_article",
    "search_users",
    "set_alias",
    "submit_review",
    "unfollow_user",
    "update_article_content",
    "update_user_public_key",
    "update_user_salt",
]
