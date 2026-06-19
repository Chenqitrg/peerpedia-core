# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Git bundle protocol — create, apply, and find common ancestors.

Pure git — depends only on GitPython and ``monotonic_search``.  Does NOT
import from ``git_backend``.  Used only by ``sync/``; dead code when offline.
"""

import tempfile
from collections.abc import Callable
from pathlib import Path

from peerpedia_core.sync.monotonic_search import search_monotonic_boundary


class MergeConflictError(Exception):
    """Raised when a git merge encounters conflicts that can't auto-resolve."""

    pass


# ── Bundle operations ────────────────────────────────────────────────────────


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

    if not is_ancestor(repo_path, since_hash):
        raise ValueError(f"since_hash {since_hash[:8]} is not an ancestor of HEAD")

    repo = git.Repo(repo_path)

    with tempfile.NamedTemporaryFile(suffix=".bundle", delete=False) as f:
        bundle_path = f.name

    try:
        repo.git.bundle("create", bundle_path, f"{since_hash}..HEAD")
        return Path(bundle_path).read_bytes()
    finally:
        Path(bundle_path).unlink(missing_ok=True)


# ── Ancestor helpers ─────────────────────────────────────────────────────────


def is_ancestor(repo_path: Path, maybe_ancestor: str) -> bool:
    """Check if *maybe_ancestor* exists in the repo and is an ancestor of HEAD."""
    import git

    if not (repo_path / ".git").is_dir():
        raise FileNotFoundError(f"Git repo not found: {repo_path}")
    repo = git.Repo(repo_path)
    try:
        repo.git.merge_base("--is-ancestor", maybe_ancestor, "HEAD")
        return True
    except git.GitCommandError:
        return False


def find_common_ancestor(
    repo_path: Path,
    probe: Callable[[str], bool | None],
    server_head: str | None = None,
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

    If *server_head* is provided, a local ``is_ancestor`` check is done
    first — returning *server_head* immediately when local is ahead
    (0 HTTP calls).  Otherwise falls through to the full probe.

    On ``None``, retries *retries* times per hash.  If all retries
    return ``None``, returns ``None`` (no common ancestor found).

    Returns the common ancestor hash, or ``None`` if no common ancestor
    is found within *max_depth*.
    """
    import git

    repo = git.Repo(repo_path)
    if not repo.head.is_valid():
        raise ValueError(f"Repo has no commits: {repo_path}")

    # ── Fast path: local-ahead ───────────────────────────────────────────
    if server_head is not None and is_ancestor(repo_path, server_head):
        return server_head

    commits = list(repo.iter_commits(max_count=max_depth + 1))

    def probe_at(dist: int) -> bool | None:
        """Map index to commit hash, wrap with retries."""
        h = commits[dist].hexsha
        for _ in range(retries + 1):
            result = probe(h)
            if result is not None:
                return result
        return None

    # ── Full search: server-ahead or diverged ────────────────────────────
    boundary = search_monotonic_boundary(probe_at, len(commits) - 1, k=k)
    if boundary is None:
        return None
    return commits[boundary].hexsha
