# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

r"""Git bundle protocol — create, ingest, and find common ancestors.

This is the lowest layer of the sync stack.  It operates on raw git
repositories via GitPython and the k-exponential search algorithm.  It
does NOT import from ``git_backend`` or ``storage/db`` — it is a pure
protocol implementation.

Function relationships::

    create_bundle(repo, since_hash) → bytes
        Bundle all commits from *since_hash* to HEAD.  If *since_hash* is
        not an ancestor, returns a full bundle (all objects).

    ingest_bundle(repo, bundle_bytes) → str
        Verify + fetch objects from a bundle file into the repo.
        Returns the tip commit hash from the bundle.  Does NOT merge —
        objects are fetched into .git/objects but the working tree is
        unchanged.

    apply_bundle(repo, bundle_bytes, ff_only=True) → str
        Convenience: ingest + merge in one step.

    is_ancestor(repo, maybe_ancestor) → bool
        Check whether *maybe_ancestor* is reachable from HEAD.

    find_common_ancestor(repo, probe, server_head, k=5) → str | None
        Use k-exponential search to find the most recent commit that both
        local and remote share.  Each "probe" is a callable that asks the
        remote "is hash X your ancestor?" → bool.  First jumps by powers of
        k to find a boundary, then binary search to pinpoint.

Protocol property — self-contained
----------------------------------
This module depends only on:
    - GitPython (``git.Repo``, ``git.GitCommandError``)
    - ``monotonic_search`` (pure algorithm)
    - ``tempfile`` (stdlib)

It does NOT know about HTTP, JSON, the database, or the article model.
This makes it testable without a server and reusable for other git-based
sync protocols.

Reviewer's checklist
--------------------
- Is ``create_bundle`` used for pushes and ``ingest_bundle`` used for pulls?
  (Client creates, server ingests, and vice versa.)
- Does ``find_common_ancestor`` handle the case where no common ancestor
  exists?  (Returns None → full bundle needed.)
- Are bundle temp files cleaned up after use?
"""

import tempfile
from collections.abc import Callable
from pathlib import Path

import git

from peerpedia_core.sync.monotonic_search import search_monotonic_boundary


class MergeConflictError(Exception):
    """Raised when a git merge encounters conflicts that can't auto-resolve."""

    pass


# ── Bundle operations ────────────────────────────────────────────────────────


def get_head(repo_path: Path) -> str:
    """Return the HEAD commit hash.

    Raises FileNotFoundError if no .git directory, ValueError if no commits.
    """

    if not (repo_path / ".git").is_dir():
        raise FileNotFoundError(f"Git repo not found: {repo_path}")
    repo = git.Repo(repo_path)
    if not repo.head.is_valid():
        raise ValueError(f"Repo has no commits: {repo_path}")
    return repo.head.commit.hexsha


def ingest_bundle(repo_path: Path, bundle_bytes: bytes) -> None:
    """Verify and fetch git bundle objects into the local repo.

    Pure git — adds objects to ``.git/objects`` but does NOT merge or
    touch the working tree.  The caller is responsible for merging
    ``FETCH_HEAD`` and reconciling DB state.

    Raises:
        FileNotFoundError: repo_path/.git doesn't exist.
        ValueError: bundle is invalid or fetch failed.
    """

    if not (repo_path / ".git").is_dir():
        raise FileNotFoundError(f"Git repo not found: {repo_path}")

    repo = git.Repo(repo_path)

    # TODO(perf): ingest_bundle leaks temp files — delete=False but no cleanup
    # in finally.  Every pull/push-receive leaves a .bundle file in the system
    # temp directory.  Fix: add a finally block with Path(f.name).unlink().
    with tempfile.NamedTemporaryFile(suffix=".bundle", delete=False) as f:
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


def create_bundle(repo_path: Path, since_hash: str | None = None) -> bytes:
    """Create a git bundle from *since_hash* to HEAD.

    *since_hash=None* → full bundle (all commits from the beginning).
    Otherwise creates an incremental bundle (``since_hash..HEAD``).

    Raises:
        FileNotFoundError: if repo_path/.git doesn't exist.
        ValueError: if since_hash is not an ancestor of HEAD.
    """

    if not (repo_path / ".git").is_dir():
        raise FileNotFoundError(f"Git repo not found: {repo_path}")

    if since_hash is not None and not is_ancestor(repo_path, since_hash):
        raise ValueError(f"since_hash {since_hash[:8]} is not an ancestor of HEAD")

    repo = git.Repo(repo_path)
    rev_range = f"{since_hash}..HEAD" if since_hash else "HEAD"

    # TODO(perf): create_bundle writes bundle to disk then reads it back
    # (double I/O + double memory).  Use repo.git.bundle("create", ...) with
    # as_process=True to pipe stdout directly, eliminating the temp file.
    with tempfile.NamedTemporaryFile(suffix=".bundle", delete=False) as f:
        bundle_path = f.name
    try:
        repo.git.bundle("create", bundle_path, rev_range)
        return Path(bundle_path).read_bytes()
    finally:
        Path(bundle_path).unlink(missing_ok=True)


# ── Ancestor helpers ─────────────────────────────────────────────────────────


def is_ancestor(repo_path: Path, maybe_ancestor: str) -> bool:
    """Check if *maybe_ancestor* exists in the repo and is an ancestor of HEAD."""

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

    repo = git.Repo(repo_path)
    if not repo.head.is_valid():
        raise ValueError(f"Repo has no commits: {repo_path}")

    # ── Fast path: local-ahead ───────────────────────────────────────────
    # TODO(perf): is_ancestor also creates a git.Repo(repo_path) internally.
    # Pass repo directly to avoid opening .git/ twice for the fast-path check.
    if server_head is not None and is_ancestor(repo_path, server_head):
        return server_head

    # TODO(perf): list() materializes up to 20k Commit objects (4-8 MB) but
    # the k-exponential search only probes ~10 of them.  Replace with lazy
    # indexable sequence or rev-list --skip to avoid 1000x allocation waste.
    commits = list(repo.iter_commits(max_count=max_depth + 1))

    def probe_at(dist: int) -> bool | None:
        """Map index to commit hash, wrap with retries."""
        h = commits[dist].hexsha
        # TODO(perf): retries with no backoff — transient network blips get
        # no recovery time.  Add exponential backoff (0.5s, 1s, 2s).
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
