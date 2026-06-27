# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Centralised filesystem paths — change one file to relocate all PeerPedia data.

Override the data root by setting the ``PEERPEDIA_HOME`` environment variable.
All paths below are relative to ``DATA_ROOT``.
"""

from __future__ import annotations

import os
from pathlib import Path

# ═══════════════════════════════════════════════════════════════════════════════
# Root
# ═══════════════════════════════════════════════════════════════════════════════

DATA_ROOT = Path(os.environ.get("PEERPEDIA_HOME", Path.home() / ".peerpedia"))

# ═══════════════════════════════════════════════════════════════════════════════
# Database
# ═══════════════════════════════════════════════════════════════════════════════

DB_PATH = DATA_ROOT / "peerpedia.db"
DB_URL = f"sqlite:///{DB_PATH}"

# ═══════════════════════════════════════════════════════════════════════════════
# Articles (git repos)
# ═══════════════════════════════════════════════════════════════════════════════

ARTICLES_DIR = DATA_ROOT / "articles"


def article_repo_path(article_id: str) -> Path:
    """Return the filesystem path for *article_id*'s git repository.

    Does NOT check whether the repo exists — use ``require_article_repo``
    for callers that need a guard.
    """
    return ARTICLES_DIR / article_id

# ═══════════════════════════════════════════════════════════════════════════════
# Session
# ═══════════════════════════════════════════════════════════════════════════════

SESSION_FILE = DATA_ROOT / "session.json"

# ═══════════════════════════════════════════════════════════════════════════════
# REPL
# ═══════════════════════════════════════════════════════════════════════════════

REPL_HISTORY_FILE = DATA_ROOT / ".repl_history"

# ═══════════════════════════════════════════════════════════════════════════════
# Sync
# ═══════════════════════════════════════════════════════════════════════════════

PENDING_OPS_FILE = DATA_ROOT / "pending_ops.json"

# ═══════════════════════════════════════════════════════════════════════════════
# Blob Store (content-addressed binary storage)
# ═══════════════════════════════════════════════════════════════════════════════
#
# TODO(blob-store): content-addressed blob layer for images and other binary
# assets that don't belong in git repos.
#
# Design:
#   ~/.peerpedia/blobs/{sha256[:2]}/{sha256}
#   — same structure as git objects, zero new concepts.
#
# ArticleMetaStorage repos store a blobs.json manifest:
#   {"fig1.png": "sha256:abc123...", "data.csv": "sha256:def456..."}
#
# Peer exchange:
#   GET /api/v1/blobs/{hash}         — fetch a blob from a peer
#   POST /api/v1/blobs                — upload a blob to a peer
#   Pull is on-demand (lazy), not eager like bundle sync.  When rendering an
#   article, the compiler encounters a blob reference, checks local cache,
#   and fetches from known peers if missing.
#
# Why not IPFS:  IPFS is a full distributed filesystem — overkill for "I need
# to store 5 figures per article."  The blob store uses the same content-
# addressed model (hash → content) with zero external dependencies.  Same
# P2P transport layer, same hash semantics, ~200 lines.
#
# Storage budget:  a 10 MB image × 100 articles = 1 GB.  Trivial for any
# modern disk.  No central server, no LFS, no IPFS daemon.

BLOBS_DIR = DATA_ROOT / "blobs"
