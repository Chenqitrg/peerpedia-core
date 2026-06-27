# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Common ancestor search — k-exponential probe with network retries."""

import time as _time
from collections.abc import Callable
from pathlib import Path

import git

from peerpedia_core.bundle.monotonic import search_monotonic_boundary
from peerpedia_core.storage.git.read import is_ancestor


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

    Returns the common ancestor hash, or ``None`` if none found.
    """
    repo = git.Repo(repo_path)
    if not repo.head.is_valid():
        raise ValueError(f"Repo has no commits: {repo_path}")

    # ── Fast path: local-ahead ──
    if server_head is not None and is_ancestor(repo_path, server_head, repo=repo):
        return server_head

    # ── Full search ──
    def _hash_at(dist: int) -> str:
        result = repo.git.rev_list("HEAD", max_count=1, skip=dist)
        return result.strip()

    def probe_at(dist: int) -> bool | None:
        h = _hash_at(dist)
        for attempt in range(retries + 1):
            result = probe(h)
            if result is not None:
                return result
            if attempt < retries:
                _time.sleep(0.5 * (2 ** attempt))
        return None

    total = int(repo.git.rev_list("HEAD", count=True))
    max_idx = min(total, max_depth) - 1
    boundary = search_monotonic_boundary(probe_at, max_idx, k=k)
    if boundary is None:
        return None
    return _hash_at(boundary)
