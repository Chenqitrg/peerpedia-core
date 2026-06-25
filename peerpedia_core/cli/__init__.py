# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

r"""PeerPedia CLI — terminal-based frontend for the PeerPedia backend.

**Hard constraint**: CLI never imports from ``storage/`` directly.  All
data access goes through ``commands/`` facade.  Handlers import from
``cli.handlers`` (facade), not from individual handler modules.

Sub-packages:
  ``display``     — Rich terminal formatting (Layer 0)
  ``helpers``     — DB, editor, user resolution, messaging (Layer 1)
  ``bundle_utils``  — auto-push helpers (Layer 1)
  ``handlers/``   — command implementations (Layer 2)
  ``parser``      — argparse registration (Layer 3)
"""

from __future__ import annotations

import sys

from peerpedia_core.cli.parser import build_parser
from peerpedia_core.config.paths import DB_PATH, DB_URL
from peerpedia_core.cli.display import console
from peerpedia_core.commands import db_session, list_users, publish_ready_articles
from peerpedia_core.repl import run


def _count_users() -> int:
    """Return the number of users in the local DB.  Returns 0 on fresh install."""
    try:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        with db_session(DB_URL) as session:
            return len(list_users(session))
    except OSError:
        return 0


def _show_welcome() -> None:
    """First-run wizard — guide the user through registration."""
    console.print()
    console.print("  ╔══════════════════════════════════════════╗")
    console.print("  ║       Welcome to [accent]PeerPedia[/]!          ║")
    console.print("  ║   peer review from the terminal         ║")
    console.print("  ╚══════════════════════════════════════════╝")
    console.print()
    console.print("  Get started in two commands:")
    console.print()
    console.print("    [accent]peerpedia account register --name <your-name>[/]")
    console.print("    [accent]peerpedia article create --title \"My First Paper\"[/]")
    console.print()
    console.print("  Or run [accent]peerpedia --help[/] to see all commands.")
    console.print()


def main():
    # Startup scan — publish any articles whose sink time has elapsed
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with db_session(DB_URL) as session:
        publish_ready_articles(session)

    # If no arguments, enter REPL or show welcome on fresh install
    if len(sys.argv) == 1:
        if _count_users() == 0:
            _show_welcome()
        else:
            run()
        return

    parser = build_parser()
    try:
        import argcomplete
        argcomplete.autocomplete(parser)
    except ImportError:
        pass
    args = parser.parse_args()
    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()


__all__ = ["main", "build_parser"]
