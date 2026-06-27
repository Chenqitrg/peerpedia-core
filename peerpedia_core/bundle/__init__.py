# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Git bundle protocol — article sync via git bundle exchange.

Client and server share the same protocol stack; the only difference is
which side initiates the HTTP request.
"""

from peerpedia_core.bundle.client import pull_new_article, sync_article
from peerpedia_core.exceptions import MergeConflictError
from peerpedia_core.bundle.pending import add, clear, count, list_all, remove

__all__ = [
    "sync_article",
    "pull_new_article",
    "MergeConflictError",
    "add",
    "clear",
    "count",
    "list_all",
    "remove",
]
