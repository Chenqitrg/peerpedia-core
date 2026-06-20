# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Layer 0: Git storage backend for article content and reviews.

Every article is an independent git repository stored under
``~/.peerpedia/articles/<article-id>/``.

Git stores content (article body, review files) — the things that need
version history, diff, and fork/merge.  Metadata (status, scores, fork
count) lives in the database so it can be queried and aggregated.

Pure local git — does not depend on bundle or sync modules.

Functions by category
---------------------
Write (mutate state)
    init_article_repo      Create .git/ + reviews/ directory
    commit_article          Stage all changes → commit → return hash
    merge_git_repos         Merge a fork repo into a target repo
    delete_article_repo     Delete the entire repo directory (idempotent)

Read (inspect state)
    get_commit_history      List recent commits with stats
    get_commit_authors      Extract user IDs from commit author emails
    get_diff_between        Diff two arbitrary commits

Review file reading (non-git — reads worktree files directly)
    list_review_dirs        List directory names under reviews/
    read_review_scores      Parse reviews/{dir}/scores.json → dict

Why read review files from the worktree?
----------------------------------------
Reviews arrive through two paths:

1. Local submission (``commands/reviews.py:submit_review``):
   _write_review_to_git() → upsert_review(commit_hash=return_value)
   Both git and DB are updated atomically.

2. Remote sync (``commands/sync.py:apply_sync_bundle``):
   git merge FETCH_HEAD → ... → git_sync_reviews() → upsert_review()
   The bundle merged new review files into git, but nobody told the DB.
   ``git_sync_reviews`` closes this gap by reading every scores.json from
   the worktree and upserting into the Review cache.

This is NOT a full git-log traversal — it only reads the current worktree
state.  Full historical review reconstruction from git history is deferred.
"""

from pathlib import Path

DEFAULT_ARTICLES_DIR = Path.home() / ".peerpedia" / "articles"


def init_article_repo(repo_path: Path) -> Path:
    """Initialize a new git repository for an article.

    Creates the repo directory, initializes .git/, and sets up the
    reviews/ subdirectory.  Returns repo_path.

    **Do not call this function in isolation.**  An empty repo without
    content and an initial commit is invalid.  This function exists
    only as a building block for ``create_article_with_content``
    (and for tests that need a bare git repo).
    """
    import git

    repo_path.mkdir(parents=True, exist_ok=True)
    git.Repo.init(repo_path)
    (repo_path / "reviews").mkdir(exist_ok=True)
    return repo_path


def commit_article(
    repo_path: Path,
    message: str,
    author_name: str,
    author_email: str,
) -> str:
    """Stage all changes and commit. Returns the commit hash.

    If the repo already has a HEAD and nothing changed, returns the
    current HEAD hash without creating a new commit.  Always creates
    an initial commit on an empty repo.
    """
    import git

    repo = git.Repo(repo_path)
    repo.git.add(A=True)

    # Nothing to commit — return current HEAD
    if not repo.is_dirty(untracked_files=True) and repo.head.is_valid():
        return repo.head.commit.hexsha  # type: ignore[union-attr]

    # Create commit (initial commit or normal commit)
    commit = repo.index.commit(
        message,
        author=git.Actor(author_name, author_email),
        committer=git.Actor(author_name, author_email),
    )
    return commit.hexsha


def get_commit_history(
    repo_path: Path,
    max_count: int = 50,
) -> list[dict]:
    """Get commit history for an article.

    Raises ValueError if the repo has no commits — the caller should
    commit before asking for history.
    """
    import git

    repo = git.Repo(repo_path)
    if not repo.head.is_valid():
        raise ValueError(f"Repo has no commits: {repo_path}")

    return [
        {
            "hash": c.hexsha,
            "parents": [p.hexsha for p in c.parents],
            "message": c.message.strip(),
            "author": str(c.author),
            "timestamp": c.committed_datetime.isoformat(),
            "stats": {
                "total": c.stats.total,
                "files": list(c.stats.files.keys()),
                "insertions": c.stats.total.get("insertions", 0) if isinstance(c.stats.total, dict) else 0,
                "deletions": c.stats.total.get("deletions", 0) if isinstance(c.stats.total, dict) else 0,
            },
        }
        for c in repo.iter_commits(max_count=max_count)
    ]


def _patch_text(d) -> str:
    """Decode a git diff patch to str."""
    if d is None:
        return ""
    if isinstance(d, bytes):
        return d.decode("utf-8", errors="replace")
    return str(d)


def get_commit_authors(
    repo_path: Path,
    since_hash: str | None = None,
) -> set[str]:
    """Return the set of user IDs from commit author emails.

    Emails have the form ``{user_id}@peerpedia``, so the user_id is
    extracted directly from the email without needing a DB lookup.
    """
    import git as _git

    repo = _git.Repo(repo_path)
    rev = f"{since_hash}..HEAD" if since_hash else None
    return {
        c.author.email.split("@", 1)[0]
        for c in repo.iter_commits(rev=rev)
    }


def get_diff_between(repo_path: Path, hash1: str, hash2: str) -> dict:
    """Get the diff between two arbitrary commits.

    hash1 is the "old" commit, hash2 is the "new" commit.
    """
    import git

    repo = git.Repo(repo_path)
    c1 = repo.commit(hash1)
    c2 = repo.commit(hash2)

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
        ins = sum(1 for l in patch.split("\n") if l.startswith("+") and not l.startswith("+++"))
        dels = sum(1 for l in patch.split("\n") if l.startswith("-") and not l.startswith("---"))
        diff_files[fname] = {"insertions": ins, "deletions": dels}
        total_insertions += ins
        total_deletions += dels

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


# ── Merge ─────────────────────────────────────────────────────────────────


class MergeConflictError(Exception):
    """Raised when a git merge encounters conflicts that can't auto-resolve."""

    pass


def merge_git_repos(target: Path, fork: Path, author_name: str) -> str:
    """Merge fork repo into target repo.

    ``fork`` is a filesystem path to the fork's git repository (e.g.
    ``~/.peerpedia/articles/def456``).  We add it as a git remote,
    fetch its refs, and merge.  The remote-tracking refs in
    ``.git/refs/remotes/fork-<name>/`` are a git implementation
    detail — they are NOT the source of truth for fork relationships.
    The DB (``Article.forked_from``) owns that.

    Raises MergeConflictError if the merge has conflicts.
    """
    import git

    target_repo = git.Repo(target)

    remote_name = f"fork-{fork.name}"
    try:
        target_repo.create_remote(remote_name, str(fork))
        target_repo.git.fetch(remote_name)

        # Fork repos have exactly one branch — take the first remote ref
        fork_ref = target_repo.remotes[remote_name].refs[0]

        target_repo.git.merge(
            fork_ref.commit.hexsha,
            message=f"Merge fork: {fork.name}",
        )

        merge_hash = target_repo.head.commit.hexsha
    except git.GitCommandError as e:
        # Abort merge if in progress
        try:
            target_repo.git.merge("--abort")
        except git.GitCommandError:
            pass
        raise MergeConflictError(f"Merge conflict: {e}") from e
    finally:
        try:
            target_repo.delete_remote(target_repo.remotes[remote_name])
        except (IndexError, AttributeError, git.GitCommandError):
            pass

    return merge_hash


# ── Review file reading ────────────────────────────────────────────────────


def list_review_dirs(repo_path: Path) -> list[str]:
    """Return directory names under reviews/ (reviewer IDs or anonymous hashes).

    Returns an empty list if reviews/ does not exist or is empty.
    """
    reviews_dir = repo_path / "reviews"
    if not reviews_dir.is_dir():
        return []
    return [d.name for d in reviews_dir.iterdir() if d.is_dir()]


def read_review_scores(repo_path: Path, reviewer_dir: str) -> dict | None:
    """Read reviews/{reviewer_dir}/scores.json and return the parsed dict.

    Returns None if the scores file does not exist.
    Raises json.JSONDecodeError if the file contains malformed JSON.
    """
    import json

    scores_file = repo_path / "reviews" / reviewer_dir / "scores.json"
    if not scores_file.is_file():
        return None
    return json.loads(scores_file.read_text())


def delete_article_repo(repo_path: Path) -> None:
    """Delete the git repository for an article (idempotent).

    Called by orchestration layer AFTER the database record has been deleted.
    """
    import shutil

    if repo_path.exists():
        shutil.rmtree(str(repo_path))
