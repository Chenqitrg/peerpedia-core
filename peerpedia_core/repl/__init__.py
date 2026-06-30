# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

r"""Interactive REPL for PeerPedia — persistent session, same commands as CLI.

Usage::

    peerpedia repl          enter the REPL explicitly
    peerpedia               enter the REPL (when no subcommand given)

Architecture
------------
``repl/`` only imports from ``app/`` (commands + context + result) and its own
modules.  ``cli/`` never imports from ``repl/``, so there is zero circular
dependency.  ``repl/`` and ``cli/`` are sibling frontends over ``app/``.
"""

from peerpedia_core.repl.main import run

# Re-export for external callers (__main__.py)
__all__ = ["run"]
