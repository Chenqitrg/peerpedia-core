# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""REPL dispatch — removed :prefix meta-command dispatch (Phase 0 cleanup).

All commands are now unified without ``:`` prefix.  Page-mode ``:word``
commands are handled by the page stack in ``repl/pages/``.
"""