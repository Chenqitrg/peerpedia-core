# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Git read operations — history, authors, diff, review files."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TypedDict

import git

from peerpedia_core.config.params import (
    ARTICLE_EXTENSIONS, article_ext_to_format, article_filename,
    extract_user_id_from_email,
)
from peerpedia_core.types.status import parse_status_tag


class CommitInfo(TypedDict):
    hash: str
    parents: list[str]
    message: str
    author: str
    author_email: str
    timestamp: str
    stats: dict[str, object]

_EXPECTED_BRANCH = "refs/heads/main"


def assert_on_main(repo: git.Repo) -> None:
    """Raise RuntimeError if HEAD is not on refs/heads/main.

    ArticleMetaStorage repos use a single-mainline model — all git operations
    expect HEAD to point to ``refs/heads/main``.
    """
    if not repo.head.is_valid():
        return
    if repo.head.is_detached:
        raise RuntimeError(
            "HEAD is detached — expected refs/heads/main; "
            "article repos use a single-mainline model"
        )
    if repo.head.reference.path != _EXPECTED_BRANCH:
        raise RuntimeError(
            f"HEAD is on {repo.head.reference.path}, expected {_EXPECTED_BRANCH} — "
            "article repos use a single-mainline model"
        )


# Commit message prefixes for non-content commits — these commits are
# platform operations (review, status transition, merge) and their
# authors should NOT be counted as article authors.
_NON_CONTENT_PREFIXES = ("[review]", "[status]", "[merge]")


# ── Commit history ─────────────────────────────────────────────────────────


def get_commit_history(
    repo_path: Path,
    max_count: int = 50,
    since_hash: str | None = None,
) -> list[CommitInfo]:
    """Get commit history for an article.

    If *since_hash* is given, only commits reachable from HEAD but not
    from *since_hash* are included (``since_hash..HEAD``).

    Raises ValueError if the repo has no commits.
    """
    repo = git.Repo(repo_path)
    assert_on_main(repo)
    if not repo.head.is_valid():
        raise ValueError(f"Repo has no commits: {repo_path}")

    rev = f"{since_hash}..HEAD" if since_hash else None
    return [
        {
            "hash": c.hexsha,
            "parents": [p.hexsha for p in c.parents],
            "message": c.message.strip(),
            "author": str(c.author),
            "author_email": (c.author.email or "").strip() if c.author else "",
            "timestamp": c.committed_datetime.isoformat(),
            "stats": {
                "total": c.stats.total,
                "files": list(c.stats.files.keys()),
                "insertions": c.stats.total.get("insertions", 0) if isinstance(c.stats.total, dict) else 0,
                "deletions": c.stats.total.get("deletions", 0) if isinstance(c.stats.total, dict) else 0,
            },
        }
        for c in repo.iter_commits(rev=rev, max_count=max_count)
    ]


def read_status_from_git(repo_path: Path) -> str | None:
    """Read the latest [status] tag from platform commit messages."""
    for commit in get_commit_history(repo_path):
        status = parse_status_tag(commit["message"], commit["author_email"])
        if status is not None:
            return status
    return None


def get_commit_authors(
    repo_path: Path,
    since_hash: str | None = None,
) -> set[str]:
    """Return the set of user IDs from content-commit author emails.

    Excludes platform commits (review, status, merge) and non-@peerpedia authors.
    """
    repo = git.Repo(repo_path)
    assert_on_main(repo)
    rev = f"{since_hash}..HEAD" if since_hash else None
    return {
        extract_user_id_from_email(c.author.email)
        for c in repo.iter_commits(rev=rev)
        if c.author.email.endswith("@peerpedia")
        and not c.message.lstrip().startswith(_NON_CONTENT_PREFIXES)
    }


# ── Diff ───────────────────────────────────────────────────────────────────


def _patch_text(d) -> str:
    """Decode a git diff patch to str."""
    if d is None:
        return ""
    if isinstance(d, bytes):
        return d.decode("utf-8", errors="replace")
    return str(d)


def _count_diff_lines(patch: str) -> tuple[int, int]:
    """Return (insertions, deletions) for a unified diff patch."""
    ins = dels = 0
    for line in patch.split("\n"):
        if line.startswith("+") and not line.startswith("+++"):
            ins += 1
        elif line.startswith("-") and not line.startswith("---"):
            dels += 1
    return ins, dels


def get_diff_between(repo_path: Path, hash1: str, hash2: str) -> dict[str, object]:
    """Get the diff between two arbitrary commits.

    hash1 is the "old" commit, hash2 is the "new" commit.
    """
    # ── Resolve commits ──
    repo = git.Repo(repo_path)
    c1 = repo.commit(hash1)
    c2 = repo.commit(hash2)

    # ── Walk diff ──
    files_changed: list[str] = []
    diff_parts: list[str] = []
    total_insertions = 0
    total_deletions = 0
    diff_files: dict[str, dict[str, int]] = {}

    for d in c1.diff(c2, create_patch=True):
        fname = d.a_path or d.b_path or ""
        if d.a_path:
            files_changed.append(d.a_path)

        patch = _patch_text(d.diff)
        if not patch:
            continue

        diff_parts.append(patch)
        ins, dels = _count_diff_lines(patch)
        diff_files[fname] = {"insertions": ins, "deletions": dels}
        total_insertions += ins
        total_deletions += dels

    # ── Build result ──
    return {
        "diff_text": "\n".join(diff_parts),
        "files": files_changed,
        "stats": {
            "total": {
                "insertions": total_insertions,
                "deletions": total_deletions,
                "lines": total_insertions + total_deletions,
            },
            "files": list(diff_files.keys()),
        },
    }


# ── HEAD ───────────────────────────────────────────────────────────────────


def get_head_hash(repo_path: Path) -> str:
    """Return the commit hash of HEAD.

    Raises ValueError if the repo has no commits.
    """
    repo = git.Repo(repo_path)
    assert_on_main(repo)
    if not repo.head.is_valid():
        raise ValueError(f"Repo has no commits: {repo_path}")
    return repo.head.commit.hexsha


def get_head_or_none(repo_path: Path) -> str | None:
    """Return HEAD hash, or None if the repo has no commits."""
    try:
        return get_head_hash(repo_path)
    except ValueError:
        return None


# ── ArticleMetaStorage source ─────────────────────────────────────────────────────────


def resolve_article_format(repo_path: Path) -> str:
    """Return the article format (``"markdown"`` or ``"typst"``).

    Returns ``"markdown"`` if no article file exists yet.
    """
    for ext in ARTICLE_EXTENSIONS:
        if (repo_path / article_filename(ext)).is_file():
            return article_ext_to_format(ext)
    return "markdown"


def is_ancestor(repo_path: Path, maybe_ancestor: str, *, repo: git.Repo | None = None) -> bool:
    """Check if *maybe_ancestor* is an ancestor of HEAD."""
    if repo is None:
        repo = git.Repo(repo_path)
    try:
        repo.git.merge_base("--is-ancestor", maybe_ancestor, "HEAD")
        return True
    except git.GitCommandError:
        return False


def read_article_source(repo_path: Path) -> tuple[str, str] | None:
    """Read the article source file from the git worktree.

    Returns ``(content, format)`` or None if no article file is found.
    """
    fmt = resolve_article_format(repo_path)
    f = repo_path / article_filename(article_ext_to_format(fmt))
    if f.is_file():
        return f.read_text(), fmt
    return None


# ── ReviewMetaStorage files ───────────────────────────────────────────────────────────


def list_review_dirs(repo_path: Path) -> list[str]:
    """Return directory names under reviews/ (reviewer IDs or anonymous hashes)."""
    reviews_dir = repo_path / "reviews"
    if not reviews_dir.is_dir():
        return []
    return [d.name for d in reviews_dir.iterdir() if d.is_dir()]


def read_review_scores(repo_path: Path, reviewer_dir: str) -> dict[str, Any] | None:
    """Read reviews/{reviewer_dir}/scores.json and return the parsed dict.

    Returns None if the scores file does not exist.
    """
    scores_file = repo_path / "reviews" / reviewer_dir / "scores.json"
    if not scores_file.is_file():
        return None
    return json.loads(scores_file.read_text())
