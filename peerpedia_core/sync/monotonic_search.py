# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

r"""Exponential + binary search over a monotonic predicate.

When you have a monotonically False→True sequence where probing an
element is expensive (network call, disk I/O, computation), this does
:math:`O(\log n)` probes instead of probing every element.

Algorithm
---------

**Phase 1 — k-exponential bounding.**  Jump exponentially (1, k, k², …)
until a ``True`` is found, establishing an upper bound.

**Phase 2 — binary refinement.**  Narrow the interval ``(last_no, first_yes]``
with binary search to pinpoint the exact boundary where ``False`` flips to ``True``.

This is the classic galloping / exponential search pattern, generalized from
array lookup to an abstract ``probe_at`` callback.

Use case in this project
------------------------

``find_common_ancestor()`` in ``peerpedia_core.storage.git_backend``
uses it to locate the merge base between two git histories: each probe
is an HTTP call asking the remote peer "do you have commit X in your
history?".

"""
from collections.abc import Callable


def search_monotonic_boundary(
    probe_at: Callable[[int], bool | None],
    max_index: int,
    *,
    k: int = 5,
) -> int | None:
    """Find the first ``True`` index in a monotonic False→True sequence.

    The sequence ``arr[0], arr[1], …, arr[max_index]`` is assumed to be
    monotonically False then True (i.e. all False up to some point, then
    all True from there onward).

    *probe_at(index)* must return:

      - ``True``  — the element at *index* is True
      - ``False`` — the element at *index* is False
      - ``None``  — probe failed; search aborts and returns ``None``

    Uses k-exponential probe (phase 1) + binary refinement (phase 2).
    Returns the index of the first True, or ``None``.

    Pure abstract algorithm — no git or network dependency.
    """
    if k < 2:
        raise ValueError(f"k must be >= 2 for exponential growth, got {k}")
    # Phase 0 — probe index 0 (the most recent element) explicitly.
    result = probe_at(0)
    if result is None:
        return None
    if result:
        return 0

    last_no = 0       # distance where probe returned False
    first_yes = -1    # distance where probe returned True

    # Phase 1 — k-exponential probe: k^0, k^1, k^2, …
    i = 0
    while True:
        dist = k ** i   # 1, k, k², …
        if dist > max_index:
            break

        result = probe_at(dist)
        if result is None:
            return None
        if result:
            first_yes = dist
            break
        last_no = dist
        i += 1

    # No True found within range — check the last element.
    # The boundary may lie between the last probe and max_index.
    if first_yes == -1:
        if max_index == last_no:
            return None  # already probed the deepest, still False
        result = probe_at(max_index)
        if result is None:
            return None
        if not result:
            return None  # no True in the entire sequence
        first_yes = max_index

    # Phase 2 — binary refinement in (last_no, first_yes]
    lo = last_no    # exclusive — probe returned False
    hi = first_yes  # inclusive — probe returned True

    while hi - lo > 1:
        mid = (lo + hi) // 2
        result = probe_at(mid)
        if result is None:
            return None
        if result:
            hi = mid
        else:
            lo = mid

    return hi
