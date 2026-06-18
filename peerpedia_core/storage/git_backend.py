# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Layer 0: Git storage backend.

Every article is an independent git repository stored under
~/.peerpedia/articles/<article-id>/.

This is the immutable storage format — the git object format IS the protocol.
"""

import tempfile
import threading
from pathlib import Path
from typing import Optional

DEFAULT_ARTICLES_DIR = Path.home() / ".peerpedia" / "articles"

# Per-article git operation locks. Plain dict (not WeakValueDictionary — locks
# must survive GC). Guarded by a module-level lock for thread-safe get/create.
_locks_dict: dict[str, threading.Lock] = {}
_locks_guard = threading.Lock()


def init_article_repo(
    article_id: str,
    base_dir: Optional[Path] = None,
) -> Path:
    """Initialize a new git repository for an article.

    Returns the path to the repo.
    """
    import git

    base = base_dir or DEFAULT_ARTICLES_DIR
    repo_path = base / article_id
    repo_path.mkdir(parents=True, exist_ok=True)

    git.Repo.init(repo_path)
    return repo_path


def commit_article(
    repo_path: Path,
    message: str,
    author_name: str,
    author_email: str,
    *,
    allow_empty: bool = False,
) -> str:
    """Stage all changes and commit. Returns the commit hash.

    Set allow_empty=True to create a commit even if nothing changed
    (used for merge records, fork tracking, etc.).

    Raises ValueError if the repo has no commits and allow_empty is False.
    """
    import git

    repo = git.Repo(repo_path)
    repo.git.add(A=True)

    has_head = repo.head.is_valid()

    # Skip commit only if nothing changed AND we already have commits
    if not repo.is_dirty(untracked_files=True) and not allow_empty and has_head:
        return repo.head.commit.hexsha  # type: ignore[union-attr]

    # Otherwise: create commit (handles initial commit + all normal commits)
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
    """Get commit history for an article. Returns empty list for empty repos."""
    import git

    repo = git.Repo(repo_path)
    if not repo.head.is_valid():
        return []
    commits = []
    for c in repo.iter_commits(max_count=max_count):
        commits.append(
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
                }
                if c.stats.total
                else {},
            }
        )
    return commits


def get_blame(repo_path: Path, file_path: str) -> list[dict]:
    """Get git blame for a file — maps lines to authors."""
    import git  # type: ignore[import-untyped]

    repo = git.Repo(repo_path)
    blames: list[dict] = []
    for entry in repo.blame_incremental("HEAD", file_path):  # type: ignore[attr-defined]
        blames.append(
            {
                "commit": entry.commit.hexsha[:8],  # type: ignore[attr-defined]
                "author": str(entry.commit.author),  # type: ignore[attr-defined]
                "lines": list(range(entry.linenos_start, entry.linenos_start + entry.linenos_count)),  # type: ignore[attr-defined]
            }
        )
    return blames


def get_diff(repo_path: Path, commit_hash: str) -> dict:
    """Get the diff for a specific commit.

    Returns a dict with:
        - commit_hash: the commit's full hash
        - message: commit message
        - author: author name
        - timestamp: ISO datetime
        - files: list of file paths changed
        - diff_text: unified diff text (for diff2html rendering)
        - parent_hash: parent commit hash (or None for initial commit)
    """
    import git

    repo = git.Repo(repo_path)
    commit = repo.commit(commit_hash)

    parent_hash = commit.parents[0].hexsha if commit.parents else None

    # Get diff between parent and this commit
    if commit.parents:
        diff_index = commit.parents[0].diff(commit, create_patch=True)
    else:
        # Initial commit: diff against empty tree
        diff_index = commit.diff(git.NULL_TREE, create_patch=True)

    files_changed = []
    diff_parts = []

    for d in diff_index:
        if d.a_path:
            files_changed.append(d.a_path)
        if d.diff:
            diff_text = d.diff.decode("utf-8", errors="replace") if isinstance(d.diff, bytes) else str(d.diff)
            diff_parts.append(diff_text)

    unified_diff = "\n".join(diff_parts)

    return {
        "commit_hash": commit.hexsha,
        "message": commit.message.strip(),
        "author": str(commit.author),
        "timestamp": commit.committed_datetime.isoformat(),
        "files": files_changed,
        "diff_text": unified_diff,
        "parent_hash": parent_hash,
        "stats": {
            "total": commit.stats.total.get("lines", 0) if commit.stats.total else 0,
            "files": list(commit.stats.files.keys()) if commit.stats.total else [],
        }
        if commit.stats.total
        else {},
    }


def get_diff_between(repo_path: Path, hash1: str, hash2: str) -> dict:
    """Get the diff between two arbitrary commits.

    hash1 is the "old" commit, hash2 is the "new" commit.
    Returns the same shape as get_diff().
    """
    import git

    repo = git.Repo(repo_path)
    c1 = repo.commit(hash1)
    c2 = repo.commit(hash2)

    diff_index = c1.diff(c2, create_patch=True)

    files_changed = []
    diff_parts = []

    for d in diff_index:
        if d.a_path:
            files_changed.append(d.a_path)
        if d.diff:
            diff_text = d.diff.decode("utf-8", errors="replace") if isinstance(d.diff, bytes) else str(d.diff)
            diff_parts.append(diff_text)

    unified_diff = "\n".join(diff_parts)

    # Compute stats from the diff text (unified diff format).
    total_insertions = 0
    total_deletions = 0
    diff_files = {}
    for d in diff_index:
        fname = d.a_path or d.b_path or ""
        if fname:
            diff_text = d.diff.decode("utf-8", errors="replace") if d.diff else ""
            ins = sum(1 for line in diff_text.split("\n") if line.startswith("+") and not line.startswith("+++"))
            dels = sum(1 for line in diff_text.split("\n") if line.startswith("-") and not line.startswith("---"))
            diff_files[fname] = {"insertions": ins, "deletions": dels}
            total_insertions += ins
            total_deletions += dels

    return {
        "commit_hash": c2.hexsha,
        "message": c2.message.strip(),
        "author": str(c2.author),
        "timestamp": c2.committed_datetime.isoformat(),
        "files": files_changed,
        "diff_text": unified_diff,
        "parent_hash": c1.hexsha,
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

    Adds fork as a remote, fetches, merges into target.
    Returns the resulting HEAD commit hash.
    Raises MergeConflictError if the merge has conflicts.
    """
    import git

    target_repo = git.Repo(target)

    remote_name = f"fork-{fork.name}"
    try:
        target_repo.create_remote(remote_name, str(fork))
        target_repo.git.fetch(remote_name)

        # Find the fork's HEAD ref
        fork_ref = None
        for branch_name in ["master", "main"]:
            try:
                fork_ref = target_repo.refs[f"{remote_name}/{branch_name}"]
                break
            except (IndexError, AttributeError):
                continue

        if fork_ref is None:
            raise MergeConflictError("Could not find main/master branch in fork")

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


# ── Bundle Sync ─────────────────────────────────────────────────────────────


def apply_bundle(repo_path: Path, bundle_bytes: bytes) -> str:
    """Fetch objects from a git bundle and fast-forward merge.

    Writes bundle to a temp file, fetches into the target repo, and merges
    with --ff-only. Returns the new HEAD commit hash.

    Raises:
        FileNotFoundError: if repo_path/.git doesn't exist.
        ValueError: if the bundle is empty or malformed.
        MergeConflictError: if --ff-only fails (history diverged).
    """
    import git

    if not (repo_path / ".git").is_dir():
        raise FileNotFoundError(f"Git repo not found: {repo_path}")

    repo = git.Repo(repo_path)

    with tempfile.NamedTemporaryFile(suffix=".bundle", delete=True) as f:
        f.write(bundle_bytes)
        f.flush()

        # Verify bundle validity
        try:
            repo.git.bundle("verify", f.name)
        except git.GitCommandError as e:
            raise ValueError(f"Invalid bundle: {e}") from e

        # Fetch objects from bundle
        try:
            repo.git.fetch(f.name, "HEAD")
        except git.GitCommandError as e:
            raise ValueError(f"Bundle fetch failed: {e}") from e

    # Fast-forward merge to FETCH_HEAD
    try:
        repo.git.merge("FETCH_HEAD", "--ff-only")
    except git.GitCommandError as e:
        # Abort merge if in progress
        try:
            repo.git.merge("--abort")
        except git.GitCommandError:
            pass
        raise MergeConflictError(f"Fast-forward merge failed: {e}") from e

    return repo.head.commit.hexsha


def create_bundle(repo_path: Path, since_hash: str) -> bytes:
    """Create an incremental git bundle from since_hash to HEAD.

    Returns the bundle file bytes. The caller can stream this directly
    as an HTTP response.

    Raises:
        FileNotFoundError: if repo_path/.git doesn't exist.
        ValueError: if since_hash is not an ancestor of HEAD.
    """
    import git

    if not (repo_path / ".git").is_dir():
        raise FileNotFoundError(f"Git repo not found: {repo_path}")

    repo = git.Repo(repo_path)

    # Verify since_hash is an ancestor
    try:
        repo.git.merge_base("--is-ancestor", since_hash, "HEAD")
    except git.GitCommandError:
        raise ValueError(f"since_hash {since_hash[:8]} is not an ancestor of HEAD")

    with tempfile.NamedTemporaryFile(suffix=".bundle", delete=False) as f:
        bundle_path = f.name

    try:
        repo.git.bundle("create", bundle_path, f"{since_hash}..HEAD")
        return Path(bundle_path).read_bytes()
    finally:
        Path(bundle_path).unlink(missing_ok=True)


def get_article_lock(article_id: str) -> threading.Lock:
    """Get or create a per-article threading.Lock for git operation serialization.

    Guards the dict with _locks_guard to prevent races during lock creation.
    The lock persists indefinitely (no GC risk like WeakValueDictionary).
    """
    with _locks_guard:
        lock = _locks_dict.get(article_id)
        if lock is None:
            lock = threading.Lock()
            _locks_dict[article_id] = lock
    return lock
