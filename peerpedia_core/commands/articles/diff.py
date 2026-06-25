# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Article diff — compare two commits."""

from pathlib import Path

from peerpedia_core.storage.git_backend import (
    DEFAULT_ARTICLES_DIR, get_commit_history, get_diff_between, get_head_hash,
)


def resolve_commit_ref(repo_path: Path, ref: str) -> str:
    """Resolve a commit reference to a full hash.

    *ref* can be: full 40-char hash, short hash prefix, ``HEAD``,
    or ``~N`` (N commits back, e.g. ``~1`` for parent, ``~3`` for HEAD~3).

    Raises ValueError if the ref cannot be resolved.
    """

    if ref.upper() == "HEAD":
        return get_head_hash(repo_path)

    if ref.startswith("~"):
        try:
            n = int(ref[1:])
        except ValueError:
            raise ValueError(f"Invalid commit ref: {ref!r} — use ~N (e.g. ~1)")
        history = get_commit_history(repo_path, max_count=n + 1)
        if len(history) <= n:
            raise ValueError(
                f"Cannot resolve {ref}: repo only has {len(history)} commit(s)"
            )
        return history[n]["hash"]

    # Try as hash prefix
    history = get_commit_history(repo_path)
    matches = [c for c in history if c["hash"].startswith(ref)]
    if len(matches) == 0:
        raise ValueError(f"No commit found matching {ref!r}")
    if len(matches) > 1:
        raise ValueError(
            f"Ambiguous ref {ref!r} — matches {len(matches)} commits. "
            "Use more characters or a full hash."
        )
    return matches[0]["hash"]


def diff_article(article_id: str, hash1: str, hash2: str) -> dict:
    """Diff two commits of an article. Returns the same dict as ``get_diff_between``.

    Raises FileNotFoundError if the article repo does not exist.
    """
    rp = DEFAULT_ARTICLES_DIR / article_id
    if not (rp / ".git").is_dir():
        raise FileNotFoundError(f"Article repo not found: {article_id}")

    h1 = resolve_commit_ref(rp, hash1)
    h2 = resolve_commit_ref(rp, hash2)
    return get_diff_between(rp, h1, h2)
