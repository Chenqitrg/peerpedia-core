# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""BFS graph crawler for social network discovery.

The pure graph traversal lives in ``compute/bfs.py`` — this module wraps it
with DB ingest and HTTP-style callbacks for social-graph crawling.
"""

from __future__ import annotations

import logging
from typing import Callable, TypedDict

from peerpedia_core.compute.bfs import bfs_traverse
from peerpedia_core.exceptions import ProtocolError
from peerpedia_core.storage.db import Session
from peerpedia_core.storage.db.ingest import ingest_following, ingest_users
from peerpedia_core.types.entities import FollowExchange, UserExchange

logger = logging.getLogger(__name__)


class CrawlResult(TypedDict):
    users_discovered: int
    articles_discovered: int
    follows_added: int
    depth_reached: int
    errors: list[dict[str, str]]


class _NodeIngestResult(TypedDict):
    neighbors: list[str]
    follows: int
    articles: int


def _bfs_walk(
    db: Session,
    server: str,
    start_user_id: str,
    *,
    depth: int = 1,
    max_users: int = 100,
    fetch_following_fn: Callable[..., list[dict] | None],
    discover_articles_fn: Callable[..., int],
) -> CrawlResult:
    """BFS walk of the follow graph from *start_user_id* on *server*."""
    follows_added = 0
    articles_discovered = 0
    errors: list[dict] = []

    def get_neighbors(user_id: str) -> list[str]:
        nonlocal follows_added, articles_discovered
        data = _fetch_ingest_node(db, server, user_id, fetch_following_fn, discover_articles_fn, errors)
        if data is None:
            return []
        follows_added += data["follows"]
        articles_discovered += data["articles"]
        return data["neighbors"]

    users_discovered = 0
    depth_reached = 0
    for node, d in bfs_traverse(start_user_id, get_neighbors, max_depth=depth, max_nodes=max_users):
        users_discovered += 1
        depth_reached = max(depth_reached, d)

    return {
        "users_discovered": users_discovered,
        "articles_discovered": articles_discovered,
        "follows_added": follows_added,
        "depth_reached": depth_reached,
        "errors": errors,
    }


def _fetch_ingest_node(
    db: Session, server: str, user_id: str,
    fetch_fn, discover_fn, errors: list[dict[str, str]],
) -> _NodeIngestResult | None:
    """Fetch + ingest one user's following data. Returns {"neighbors": [...], "follows": int, "articles": int} or None."""
    # ── Fetch ─────────────────────────────────────────────────────────────
    try:
        data = fetch_fn(server, user_id)
    except Exception:
        logger.debug("_bfs_walk: fetch failed for %s, skipping", user_id)
        errors.append({"user": user_id, "stage": "following", "error": "fetch_failed"})
        return None
    if not data:
        return None

    # ── Ingest users + follows ────────────────────────────────────────────
    users = [UserExchange(id=e["id"], name=e.get("name", e["id"]), address=e.get("address", "")) for e in data]
    try:
        ingest_users(db, users)
    except ValueError as e:
        logger.debug("_bfs_walk: ingest_users failed for %s: %s", user_id, e)
        errors.append({"user": user_id, "stage": "ingest_users", "error": str(e)})
        return None

    n_follows = 0
    follows = [FollowExchange(id=e["id"]) for e in data]
    try:
        n_follows = ingest_following(db, user_id, follows)
    except ValueError as e:
        logger.debug("_bfs_walk: ingest_following failed for %s: %s", user_id, e)
        errors.append({"user": user_id, "stage": "ingest_following", "error": str(e)})

    # ── Discover articles + collect neighbors ─────────────────────────────
    neighbors: list[str] = []
    n_articles = 0
    for entry in data:
        followed_id = entry["id"]
        neighbors.append(followed_id)
        try:
            n_articles += discover_fn(db, server, followed_id)
        except (Exception, ProtocolError) as e:
            logger.debug("_bfs_walk: discover_articles failed for %s, skipping", followed_id)
            errors.append({"user": followed_id, "stage": "articles", "error": str(e)})

    return {"neighbors": neighbors, "follows": n_follows, "articles": n_articles}
