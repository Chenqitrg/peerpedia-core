# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Article diff — compare two commits."""

from __future__ import annotations

from pathlib import Path

from peerpedia_core.storage.git.guards import require_article_repo
from peerpedia_core.storage.git import (
    get_commit_history, get_diff_between, get_head_hash,
)
from peerpedia_core.types.entities import DiffResult


def _resolve_head(repo_path: Path) -> str:
    """Return the full hash of HEAD."""
    return get_head_hash(repo_path)


def _resolve_offset(repo_path: Path, ref: str) -> str:
    """Resolve ``~N`` — return hash of the Nth commit back from HEAD."""
    try:
        n = int(ref[1:])
    except ValueError:
        raise ValueError("INVALID_COMMIT_REF")
    history = get_commit_history(repo_path, max_count=n + 1)
    if len(history) <= n:
        raise ValueError("COMMIT_NOT_FOUND")
    return history[n]["hash"]


def _resolve_hash_prefix(repo_path: Path, ref: str) -> str:
    """Resolve a full or partial commit hash — one exact prefix match required."""
    matches = [c for c in get_commit_history(repo_path) if c["hash"].startswith(ref)]
    if len(matches) == 0:
        raise ValueError("COMMIT_NOT_FOUND")
    if len(matches) > 1:
        raise ValueError("INVALID_COMMIT_REF")
    return matches[0]["hash"]


def resolve_commit_ref(repo_path: Path, ref: str) -> str:
    """Resolve a commit reference to a full hash.

    *ref* can be: full 40-char hash, short hash prefix, ``HEAD``,
    or ``~N`` (N commits back, e.g. ``~1`` for parent, ``~3`` for HEAD~3).

    Raises ValueError if the ref cannot be resolved.
    """
    if ref is None or ref.upper() == "HEAD":
        return _resolve_head(repo_path)
    if ref.startswith("~"):
        return _resolve_offset(repo_path, ref)
    return _resolve_hash_prefix(repo_path, ref)


def diff_article(article_id: str, hash1: str, hash2: str) -> DiffResult:
    """Diff two commits of an article. Returns a ``DiffResult``.

    Raises FileNotFoundError if the article repo does not exist.
    """
    rp = require_article_repo(article_id)

    h1 = resolve_commit_ref(rp, hash1)
    h2 = resolve_commit_ref(rp, hash2)
    return get_diff_between(rp, h1, h2)
