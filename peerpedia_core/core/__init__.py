# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

r"""Core domain layer — the ONLY package that coordinates both git and DB.

Architecture::

    cli / repl / transport  ──→  core  ←──  storage/git + storage/db
                                  │
                    ┌─────────────┼─────────────┐
                    ▼             ▼             ▼
                 articles      reviews       reconcile
                (lifecycle)   (lifecycle)   (git↔DB mirror)

    compute/  纯算法（零 IO）       rules/   纯授权规则（零 IO）

External callers import from here — never from submodules or storage/ directly.
"""

from peerpedia_core.config.paths import ARTICLES_DIR
from peerpedia_core.frontmatter import parse_frontmatter
from peerpedia_core.storage.db import db_repl_setup
from peerpedia_core.storage.db.session_utils import db_session_scope as db_session


def health_check(database_url: str) -> list[str]:
    """Check that runtime dependencies (DB, articles directory) are reachable."""
    problems: list[str] = []
    if not ARTICLES_DIR.is_dir():
        problems.append("articles_dir_missing")
    try:
        with db_session(database_url):
            pass
    except Exception as e:
        problems.append(f"db_unreachable: {e}")
    return problems

# ── Articles ─────────────────────────────────────────────────────────────────

from peerpedia_core.core.articles import (
    count_articles,
    create_article_with_content,
    delete_article,
    diff_article,
    fork_article,
    list_all_article_ids,
    get_article,
    list_author_ids,
    list_articles,
    publish_article,
    publish_ready_articles,
    rollback_article,
    update_article_content,
)


def search_articles(db: Session, query: str) -> list:
    """Fuzzy-search articles by partial title, author, or ID prefix."""
    return list_articles(db, search_query=query)


def merge_article_meta(db: Session, entries: list[dict]) -> int:
    """Merge article metadata from a peer into the local DB."""
    from peerpedia_core.storage.db.ingest import ingest_articles
    from peerpedia_core.types.entities import ArticleMetaExchange
    return ingest_articles(db, [ArticleMetaExchange.from_json(e) for e in entries])


# ── Reviews ──────────────────────────────────────────────────────────────────

from peerpedia_core.core.reviews import (
    accept_invitation, decline_invitation, get_reviews_for_article,
    invite_reviewer, rate_review_helpfulness, submit_reply, submit_review,
)

# ── Users ────────────────────────────────────────────────────────────────────

from peerpedia_core.core.users import (
    create_user, create_user_stub, find_users, follow_user,
    get_followers, get_following, get_top_users_by_followers,
    get_user, list_users_by_name, increment_failed_login, is_following,
    list_users, require_authenticable_user, reset_failed_login,
    search_users, soft_delete_user, unfollow_user, update_user_public_key,
    update_user_salt, verify_user_password,
)

# ── Maintainers ──────────────────────────────────────────────────────────────

from peerpedia_core.core.maintainers import (
    add_maintainer_to_article, consent_to_publish, list_maintainers,
    remove_maintainer_from_article, revoke_publish_consent,
)

# ── Merge ────────────────────────────────────────────────────────────────────

from peerpedia_core.core.merge import accept_merge, create_merge_proposal, withdraw_merge_proposal

# ── Reconcile ────────────────────────────────────────────────────────────────

from peerpedia_core.core.reconcile import (
    reconcile_after_sync, reconcile_all_reputations,
    reconcile_reputation, reconcile_reviews, reconcile_score,
)

# ── Guards & Integrity ───────────────────────────────────────────────────────

from peerpedia_core.core.reconcile import reconcile_integrity

# ── Social — bookmarks, shares, notifications ────────────────────────────────

from peerpedia_core.core.bookmarks import add_bookmark, get_bookmarks_for_user, remove_bookmark
from peerpedia_core.core.shares import (
    add_share, get_feed_shares, get_shares_for_user, remove_share,
)
from peerpedia_core.core.notifications import (
    count_unread_notifications, create_notification,
    get_notifications, get_notifications_for_user, mark_read,
)

# ── Views ────────────────────────────────────────────────────────────────────

from peerpedia_core.core.views import (
    get_article_view, get_follower_views, get_following_views,
    get_user_view, list_article_views, list_user_article_views,
)

# ── Discovery (P2P) ──────────────────────────────────────────────────────────

from peerpedia_core.core.sync_social import (
    discover_articles, discover_followers, discover_following,
    discover_network, discover_notifications, discover_shares,
)

# ── Ingest (P2P) ─────────────────────────────────────────────────────────────

from peerpedia_core.storage.db.ingest import (
    ingest_articles, ingest_bookmarks, ingest_followers, ingest_following,
    ingest_maintainers, ingest_notifications, ingest_shares, ingest_users,
    sync_followers, sync_following,
)

# ── Pass-through (thin wrappers over storage/) ───────────────────────────────

from peerpedia_core.storage.db.crud_article import create_article_from_orm, list_author_ids_batch
from peerpedia_core.storage.db.crud_alias import (
    list_aliases, remove_alias, resolve_username_or_alias, set_alias,
)
from peerpedia_core.storage.db.crud_user import list_users_by_ids
from peerpedia_core.storage.git import (
    get_commit_history, get_head_hash, read_article_source,
)
from peerpedia_core.storage.git.read import article_source_path
from peerpedia_core.storage.peers import (
    add_peer, get_known_peers, merge_peers, record_peer_result,
)
