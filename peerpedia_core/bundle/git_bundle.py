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

from peerpedia_core.bundle.monotonic import search_monotonic_boundary


from peerpedia_core.exceptions import ConflictError

class MergeConflictError(ConflictError):
    """Raised when a git merge encounters conflicts that can't auto-resolve."""


# ── Bundle operations ────────────────────────────────────────────────────────


def init_repo(path: Path) -> Path:
    """Create a bare git repo at *path*. Returns *path*.

    Pure git init — no dependency on ``git_backend``.
    """
    path.mkdir(parents=True, exist_ok=True)
    git.Repo.init(path)
    return path


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

    with tempfile.NamedTemporaryFile(suffix=".bundle", delete=False) as f:
        f.write(bundle_bytes)
        f.flush()
        try:
            try:
                repo.git.bundle("verify", f.name)
            except git.GitCommandError as e:
                raise ValueError(f"Invalid bundle: {e}") from e

            try:
                repo.git.fetch(f.name, "HEAD")
            except git.GitCommandError as e:
                raise ValueError(f"Bundle fetch failed: {e}") from e
        finally:
            Path(f.name).unlink(missing_ok=True)


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
    proc = repo.git.bundle("create", "-", rev_range, as_process=True)
    stdout, _stderr = proc.communicate()
    return stdout


# ── Ancestor helpers ─────────────────────────────────────────────────────────


def is_ancestor(repo_path: Path, maybe_ancestor: str, *, repo: git.Repo | None = None) -> bool:
    """Check if *maybe_ancestor* exists in the repo and is an ancestor of HEAD.

    Pass *repo* to avoid opening ``.git/`` twice when called from a function
    that already has a ``Repo`` object.
    """
    if repo is None:
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
    if server_head is not None and is_ancestor(repo_path, server_head, repo=repo):
        return server_head

    import time as _time

    def _hash_at(dist: int) -> str:
        """Return the commit hash at position *dist* (lazy, single rev-list call)."""
        result = repo.git.rev_list("HEAD", max_count=1, skip=dist)
        return result.strip()

    def probe_at(dist: int) -> bool | None:
        """Map index to commit hash, wrap with retries + exponential backoff."""
        h = _hash_at(dist)
        for attempt in range(retries + 1):
            result = probe(h)
            if result is not None:
                return result
            if attempt < retries:
                _time.sleep(0.5 * (2 ** attempt))  # 0.5s, 1s, 2s, ...
        return None

    # ── Full search: server-ahead or diverged ────────────────────────────
    total = int(repo.git.rev_list("HEAD", count=True))
    max_idx = min(total, max_depth) - 1
    boundary = search_monotonic_boundary(probe_at, max_idx, k=k)
    if boundary is None:
        return None
    return _hash_at(boundary)


# ── Full-repo pack / unpack (tar.gz) ──────────────────────────────────────


def ingest_article_repo(repo_path: Path, payload: dict) -> str:
    """Unpack a full article repo from a base64-encoded tar.gz payload.

    *payload* must contain ``"repo_bundle"``: a base64-encoded gzipped
    tar archive of the full git repo.

    Returns the HEAD hash of the newly ingested article.

    Raises ``FileExistsError`` if *repo_path* already contains a ``.git``
    directory.
    """
    import base64 as _b64
    import io as _io
    import tarfile as _tarfile

    if (repo_path / ".git").is_dir():
        raise FileExistsError(f"Article already exists locally: {repo_path.name}")

    bundle_bytes = _b64.b64decode(payload["repo_bundle"])
    with _tarfile.open(fileobj=_io.BytesIO(bundle_bytes), mode="r:gz") as tar:
        tar.extractall(path=repo_path.parent)
    return get_head(repo_path)


def pack_article_repo(repo_path: Path) -> str:
    """Pack an article's full git repo into a base64-encoded tar.gz string.

    The reverse of ``ingest_article_repo``.
    """
    import base64 as _b64
    import io as _io
    import tarfile as _tarfile

    buf = _io.BytesIO()
    with _tarfile.open(fileobj=buf, mode="w:gz") as tar:
        tar.add(str(repo_path), arcname=repo_path.name)
    return _b64.b64encode(buf.getvalue()).decode("ascii")
