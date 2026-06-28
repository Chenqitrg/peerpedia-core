# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

r"""Application layer — use-case orchestration between entry points and domain.

Each command in ``app/commands/`` takes an ``AppContext`` and typed
keyword arguments, calls ``core/`` functions, and returns an ``AppResult``
or raises a ``PeerpediaError``.  The layer NEVER imports from ``cli/``,
``repl/``, or ``server/``.
"""

from peerpedia_core.app.context import AppContext, build_context
from peerpedia_core.app.result import AppNotice, AppResult

__all__ = ["AppContext", "build_context", "AppNotice", "AppResult"]
