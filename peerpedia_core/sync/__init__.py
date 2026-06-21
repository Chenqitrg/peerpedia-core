# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

r"""Sync domain — peer-to-peer git bundle exchange.

This package handles everything needed to synchronize articles between
peer nodes.  It is self-contained: ``git_bundle.py`` and
``monotonic_search.py`` have zero dependencies on ``git_backend`` or
``storage/db``.  They operate on raw git repositories via GitPython.

Architecture
------------
::

    CLI (sync push)
      │
      ▼
    bundle_client.py ──HTTP──► bundle_server.py   (remote peer)
      │                            │
      ├► git_bundle.py              ├► git_bundle.py
      ├► monotonic_search.py        ├► monotonic_search.py
      └► transport/http.py          └► (HTTP layer — future: server/main.py)

Client and server run the SAME codebase — the only difference is which
side initiates the HTTP request.  Both call ``git_bundle.create_bundle``
and ``git_bundle.apply_bundle``; both use ``git_backend`` for local git ops.

Modules
-------
git_bundle.py          Pure git bundle protocol — create, apply, find common
                       ancestor.  Depends only on GitPython + monotonic_search.
monotonic_search.py    k-exponential boundary search + binary refinement.
                       Pure algorithm, no git or HTTP dependencies.
bundle_client.py       Client-side sync orchestration.  Wraps bundle protocol
                       with HTTP transport and local git operations.
bundle_server.py       Server-side request handlers.  Pure logic — no HTTP
                       code (that lives in a separate routing layer, TBD).
transport/http.py      HTTP transport implementation.  The ONLY file in the
                       entire project that imports ``httpx``.  Replaceable.
network.py             Network detection — ``is_online(server_url)``.
pending_queue.py       Offline operation queue (file-based JSON).

Discovery model (planned)
-------------------------
No global index.  Discovery follows the social graph: each peer sees articles
bookmarked by users they follow.  With ~50 follows and each follow connecting
to ~50 others, the reachable network covers ~2500 researchers — enough to
surface relevant papers without a central directory.

The server exposes a bookmark index for each user it hosts; peers poll the
bookmarks of followed users to discover new articles.
"""

from peerpedia_core.sync.bundle_client import client_sync
from peerpedia_core.sync.network import is_online
from peerpedia_core.sync.pending_queue import add, clear, count, list_all, remove

__all__ = ["client_sync", "is_online", "add", "clear", "count", "list_all", "remove"]
