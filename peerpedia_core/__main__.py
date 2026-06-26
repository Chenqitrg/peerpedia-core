# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Top-level entry point — routes to CLI or REPL.

This is the ONLY module that knows about both ``cli`` and ``repl``.
``cli/`` never imports from ``repl/``; ``repl/`` only imports from ``cli/``.
No circular dependency.
"""

from __future__ import annotations

import sys

from peerpedia_core.cli import main as cli_main


def main():
    """Entry point for the ``peerpedia`` command."""
    if len(sys.argv) == 1:
        # No subcommand → interactive REPL.
        # Lazy import: prompt_toolkit is heavy, only load for REPL mode.
        from peerpedia_core.repl import run
        run()
        return

    cli_main()
