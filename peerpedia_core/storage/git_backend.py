# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Layer 0: Git storage backend for article content and reviews.

Every article is an independent git repository stored under
~/.peerpedia/articles/<article-id>/.

Git stores content (article body, review files) — the things that need
version history, diff, and fork/merge.  Metadata (status, scores, fork
count) lives in the database so it can be queried and aggregated.
"""

import tempfile
from collections.abc import Callable
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


# ── Bundle Sync ─────────────────────────────────────────────────────────────


def apply_bundle(repo_path: Path, bundle_bytes: bytes, *, ff_only: bool = True) -> str:
    """Fetch objects from a git bundle and merge.

    When *ff_only* is True (default), does a fast-forward merge — fails with
    MergeConflictError if histories have diverged.  Set to False for the
    diverged case (e.g., both sides edited different files).

    Returns the new HEAD commit hash.
    """
    import git

    if not (repo_path / ".git").is_dir():
        raise FileNotFoundError(f"Git repo not found: {repo_path}")

    repo = git.Repo(repo_path)

    with tempfile.NamedTemporaryFile(suffix=".bundle", delete=True) as f:
        f.write(bundle_bytes)
        f.flush()

        try:
            repo.git.bundle("verify", f.name)
        except git.GitCommandError as e:
            raise ValueError(f"Invalid bundle: {e}") from e

        try:
            repo.git.fetch(f.name, "HEAD")
        except git.GitCommandError as e:
            raise ValueError(f"Bundle fetch failed: {e}") from e

    merge_args = ["FETCH_HEAD", "--ff-only"] if ff_only else ["FETCH_HEAD"]
    try:
        repo.git.merge(*merge_args)
    except git.GitCommandError as e:
        try:
            repo.git.merge("--abort")
        except git.GitCommandError:
            pass
        raise MergeConflictError(f"Merge failed: {e}") from e

    return repo.head.commit.hexsha


def is_ancestor(repo_path: Path, maybe_ancestor: str) -> bool:
    """Check if *maybe_ancestor* exists in the repo and is an ancestor of HEAD."""
    import git

    if not (repo_path / ".git").is_dir():
        return False
    repo = git.Repo(repo_path)
    try:
        repo.git.merge_base("--is-ancestor", maybe_ancestor, "HEAD")
        return True
    except git.GitCommandError:
        return False


def find_common_ancestor(
    repo_path: Path,
    probe: Callable[[str], str | None],
    k: int = 5,
    max_depth: int = 20000,
    retries: int = 3,
) -> str | None:
    """Find the most recent common ancestor with a remote peer.

    Uses k-exponential probe + binary refinement.
    *probe(hash)* must return:

      - ``True``  if the remote has *hash* in its history,
      - ``False`` if the remote does NOT have *hash*,
      - ``None``  if the probe failed (network error).

    On ``None``, retries *retries* times per hash.  If all retries
    return ``None``, returns ``None`` (no common ancestor found).

    Returns the common ancestor hash, or ``None`` if no common ancestor
    is found within *max_depth*.

    Pure git logic — no HTTP dependency.  The caller injects *probe*.
    """
    import git

    repo = git.Repo(repo_path)
    if not repo.head.is_valid():
        raise ValueError(f"Repo has no commits: {repo_path}")
    commits = list(repo.iter_commits(max_count=max_depth + 1))

    def hash_at(dist: int) -> str:
        return commits[dist].hexsha

    def probe_with_retry(h: str) -> bool | None:
        """Call probe; retry on None up to *retries* times."""
        for _ in range(retries + 1):
            result = probe(h)
            if result is not None:
                return result
        return None

    # ── Phase 1: k-exponential probe ──────────────────────────────────────
    # Probe HEAD (distance 0) explicitly — k^0 = 1, not 0.
    result = probe_with_retry(hash_at(0))
    if result is None:
        return None
    if result:
        return hash_at(0)  # HEAD is common — remote >= local

    last_no = 0       # distance where probe returned False
    first_yes = -1    # distance where probe returned True

    i = 0
    while True:
        dist = k ** i   # k^0 = 1, k^1 = 5, k^2 = 25, ...
        if dist >= len(commits):
            break  # exhausted history

        result = probe_with_retry(hash_at(dist))
        if result is None:
            return None

        if result:
            first_yes = dist
            break
        last_no = dist
        i += 1

    # No True found within history — check the oldest commit.
    # The fork may lie between the last probe and the end of history.
    if first_yes == -1:
        deepest = len(commits) - 1
        if deepest == last_no:
            return None  # already probed the deepest, still False
        result = probe_with_retry(hash_at(deepest))
        if result is None:
            return None
        if not result:
            return None  # no common ancestor at all
        first_yes = deepest

    # ── Phase 2: binary refinement in (last_no, first_yes] ─────────────────
    lo = last_no    # exclusive — probe returned False
    hi = first_yes  # inclusive — probe returned True

    while hi - lo > 1:
        mid = (lo + hi) // 2
        result = probe_with_retry(hash_at(mid))
        if result is None:
            return None
        if result:
            hi = mid
        else:
            lo = mid

    return hash_at(hi)


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


def delete_article_repo(repo_path: Path) -> None:
    """Delete the git repository for an article (idempotent).

    Called by orchestration layer AFTER the database record has been deleted.
    """
    import shutil

    if repo_path.exists():
        shutil.rmtree(str(repo_path))
