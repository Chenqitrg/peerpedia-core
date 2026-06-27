# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Pure BFS graph traversal — zero IO, zero side effects.

Callers provide a ``get_neighbors`` callback to supply edges.
"""

from collections import deque
from collections.abc import Callable, Iterator


def bfs_traverse(
    start,
    get_neighbors: Callable[..., list],
    *,
    max_depth: int,
    max_nodes: int,
) -> Iterator[tuple]:
    """Yield (node, depth) in BFS order from *start*.

    *get_neighbors(node)* must return a list of adjacent nodes.
    """
    visited = {start}
    queue: deque[tuple] = deque([(start, 0)])
    yielded = 0

    while queue and yielded < max_nodes:
        node, depth = queue.popleft()
        if depth > max_depth:
            continue

        yield node, depth
        yielded += 1

        if depth >= max_depth:
            continue

        for neighbor in get_neighbors(node):
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append((neighbor, depth + 1))
