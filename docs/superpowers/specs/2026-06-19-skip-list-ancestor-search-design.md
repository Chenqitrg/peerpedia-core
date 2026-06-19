# Interactive k-exponential Common Ancestor Search

**Date**: 2026-06-19
**Status**: draft

## Motivation

`get_ancestor_hashes()` sends up to 1000 commit hashes (~40KB) in a single
request to find a common ancestor with a remote peer. An article with tens of
thousands of review commits would exceed this limit. Git's smart protocol
solves this with multi-round negotiation — send a few hashes, get an ACK,
narrow the range.

## Design

Replace `get_ancestor_hashes` + `find_merge_base` with a single function:

```
find_common_ancestor(repo_path, probe) → str | None
```

that uses **k-exponential probe + binary refinement** to locate the most recent
common ancestor with a remote peer in O(log_k d + log d) rounds.

### Algorithm

**Phase 1 — k-exponential probe (k=5):**

Probe HEAD (distance 0) first.  If HEAD is common, return it immediately
(remote is ahead or identical).

Then probe at distances `d_i = k^i` for i = 0, 1, 2, … (i.e., 1, 5, 25, 125,
625, 3125, 15625) until the remote acknowledges.  Note: `k^0 = 1`, not 0,
so we probe HEAD separately.

```
i:      —   0   1    2     3      4       5        6        7
d_i:    0   1   5   25   125    625    3125    15625    78125
```

Stop when `probe(hash)` returns `True`. Record:
- `last_no`: the largest distance where probe returned `False`
- `first_yes`: the smallest distance where probe returned `True`

If history is exhausted without finding `True`, probe the oldest commit
in the range.  If it is `True`, the fork lies between `last_no` and the
end of history — proceed to Phase 2 with `first_yes = len(commits)-1`.
Otherwise return `None` (no common ancestor within `max_depth`).

**Phase 2 — binary refinement:**

The fork point lies in `(last_no, first_yes]`. Binary-search this range using
`probe()` to find exactly the most recent common ancestor — the commit whose
parent is NOT common, but the commit itself IS common.

```
lo = distance(last_no)   # exclusive — probe returned False
hi = distance(first_yes) # inclusive — probe returned True
while hi - lo > 1:
    mid = (lo + hi) // 2
    if probe(hash_at_distance(mid)):
        hi = mid   # mid is common, fork is at or before mid
    else:
        lo = mid   # mid is not common, fork is after mid
return hash_at_distance(hi)
```

At exit, `hi` is the distance of the most recent common ancestor. Since the
probe function is monotonic (all ancestors of a "yes" are also "yes"), binary
search is sound.

### Correctness

**Monotonicity**: If a commit C is in the remote's history, all ancestors of C
are also in the remote's history. Therefore the probe function is monotonic
walking backwards from HEAD: `False` for commits after the fork (not on
remote), `True` for commits at or before the fork (common ancestors). The
cutoff is the most recent common ancestor.

**Nearest ancestor guarantee**: Binary refinement continues until `hi - lo == 1`,
meaning `hi` is the first common commit walking backwards, and `lo` is its
parent (not common). This yields the exact most recent common ancestor.

### Complexity

| Scenario          | Phase 1 rounds | Phase 2 rounds | Total  |
|-------------------|---------------|----------------|--------|
| Fork at dist 5    | 2             | 3              | 5      |
| Fork at dist 100  | 4             | 8              | 12     |
| Fork at dist 5000 | 6             | 13             | 19     |
| No common ancestor| 7             | 0              | 7      |

Each round = one HTTP request (client sends a hash, server responds yes/no).

## Implementation

### `git_backend.py`

**Remove**: `get_ancestor_hashes()`, `find_merge_base()`

**Add**:

```python
def find_common_ancestor(
    repo_path: Path,
    probe: Callable[[str], bool],
    k: int = 5,
    max_depth: int = 20000,
) -> str | None:
    """Find the most recent common ancestor with a remote peer.

    Uses k-exponential probe + binary refinement.  *probe(hash)* must
    return ``True`` if the remote peer has *hash* in its history.

    Returns the common ancestor hash, or ``None`` if no common ancestor
    is found within *max_depth*.

    Pure git logic — no HTTP dependency.  The caller injects *probe*
    (which typically makes an HTTP request to the remote server).
    """
    import git

    repo = git.Repo(repo_path)
    commits = list(repo.iter_commits(max_count=max_depth + 1))
    if not commits:
        raise ValueError(f"Repo has no commits: {repo_path}")

    def hash_at(dist: int) -> str:
        return commits[dist].hexsha

    # Phase 1: k-exponential probe
    last_no = 0      # distance where probe returned False
    first_yes = -1   # distance where probe returned True

    i = 0
    while True:
        dist = k ** i
        if dist >= len(commits):
            break  # exhausted history

        h = hash_at(dist)
        if probe(h):
            first_yes = dist
            break
        last_no = dist
        i += 1

    # HEAD itself is common — remote >= local, just return HEAD
    if first_yes == 0:
        return hash_at(0)

    # No common ancestor found
    if first_yes == -1:
        return None

    # Phase 2: binary refinement in (last_no, first_yes]
    lo = last_no   # exclusive
    hi = first_yes # inclusive

    while hi - lo > 1:
        mid = (lo + hi) // 2
        if probe(hash_at(mid)):
            hi = mid
        else:
            lo = mid

    return hash_at(hi)
```

### `bundle_client.py`

The diverged case (currently `_pull_full` fallback) uses `find_common_ancestor`:

```python
def _find_merge_base_via_probe(
    server: str, article_id: str, repo_path: Path
) -> str | None:
    """Find merge base by probing the server with candidate hashes."""
    from peerpedia_core.storage.git_backend import find_common_ancestor

    def probe(hash: str) -> bool:
        """Ask server: do you have this hash in your history?"""
        try:
            resp = httpx.get(
                f"{_api_url(server, article_id)}/ancestor/{hash}",
                timeout=30,
            )
            return resp.status_code == 200
        except Exception:
            return False

    return find_common_ancestor(repo_path, probe)


def push(server: str, article_id: str) -> dict:
    # ... existing code ...

    # ── Case 3: Diverged ───────────────────────────────────────────
    merge_base = _find_merge_base_via_probe(server, article_id, rp)
    if merge_base:
        # Pull server's changes from merge_base → server HEAD
        bundle = _fetch_bundle(server, article_id, merge_base)
        if bundle:
            apply_bundle(rp, bundle, ff_only=False)
    else:
        # Fallback: full pull
        new_head = _pull_full(server, article_id)
        if not new_head:
            return {"pushed": False, "head": None}

    # Now push local changes
    history = get_commit_history(rp)
    return _do_push(server, article_id, server_head, history[0]["hash"])
```

### Server endpoint

Server needs a lightweight endpoint for the probe:

```
GET /api/v1/articles/{id}/ancestor/{hash}
→ 200 { "ancestor": true }   if hash is an ancestor of server HEAD
→ 404                        if hash is not found / not an ancestor
```

Single-responsibility: calls `is_ancestor(repo, hash)` and returns the
appropriate status code. No bundle generation, no complex logic.

### Files changed

| File | Change |
|------|--------|
| `peerpedia_core/storage/git_backend.py` | Remove `get_ancestor_hashes`, `find_merge_base`; add `find_common_ancestor` |
| `peerpedia_core/sync/bundle_client.py` | Diverged case uses `find_common_ancestor` + probe; add `_find_merge_base_via_probe` |
| `tests/test_git_backend.py` | Tests for `find_common_ancestor` with mock probe |
| `tests/test_sync.py` | Integration tests for diverged sync with probe endpoint |

### Unchanged

- `is_ancestor()` — still wraps `git merge-base --is-ancestor`
- `create_bundle()` / `apply_bundle()` — same bundle mechanism
- Case 1 (server ahead) and Case 2 (local ahead) in `push()` — unchanged
- `pull()` flow — unchanged (already uses `_pull_incremental`)
