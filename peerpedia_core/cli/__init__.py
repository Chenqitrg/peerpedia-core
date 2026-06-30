# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

r"""PeerPedia CLI — terminal-based frontend for the PeerPedia backend.

**Hard constraint**: CLI never imports from ``storage/`` or ``core/``
directly.  Data access goes through ``app/commands/``.  ``db_session``
is the sole exception — it is infrastructure plumbing, not domain logic.

Sub-packages:
  ``display``       — Rich terminal formatting (Layer 0)
  ``helpers``       — DB, editor, user resolution, messaging (Layer 1)
  ``bundle_utils``  — auto-push helpers (Layer 1)
  ``cmds/``         — command implementations (Layer 2)
  ``parser``        — argparse registration (Layer 3)
"""

from __future__ import annotations

import sys
import warnings

# Suppress SQLAlchemy deprecation warnings from user-facing output.
warnings.filterwarnings("ignore", category=Warning, module="sqlalchemy")

from peerpedia_core.app.readmodels.dashboard import (
    count_user_articles,
    count_users,
    publish_ready,
)
from peerpedia_core.presentation.rich.components import guest_hint
from peerpedia_core.cli.parser import build_parser
from peerpedia_core.config.paths import DB_PATH, DB_URL
from peerpedia_core.cli.info import console
from peerpedia_core.core import db_session
from peerpedia_core.cli.session import _read_session


def _show_dashboard() -> None:
    """Show a compact status dashboard for returning users."""
    session = _read_session()
    console.print()
    console.print("  [accent]PeerPedia[/] — peer review from the terminal.")
    console.print()

    if session:
        user_id = session.get("user_id", "")
        user_name = session.get("name", "?")
        console.print(f"  Currently: [accent]{user_name}[/] ({user_id or '?'})")

        try:
            with db_session(DB_URL) as db:
                stats = count_user_articles(db, user_id)
                console.print(f"    Drafts:      {stats['draft']}")
                console.print(f"    In review:   {stats['sedimentation']}")
                console.print(f"    Published:   {stats['published']}")
        except Exception:
            import logging
            logging.getLogger(__name__).warning(
                "Failed to load dashboard stats", exc_info=True
            )
    else:
        console.print(f"  {guest_hint(cli=True)}")

    console.print()
    console.print("  Get started:")
    console.print("    [accent]peerpedia article create --title \"My Paper\"[/]")
    console.print("    [accent]peerpedia article list[/]")
    console.print("    [accent]peerpedia mother[/]                   ← full guide")
    console.print()


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


def _count_users() -> int:
    """Return the number of users in the local DB.  Returns 0 on fresh install."""
    try:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        with db_session(DB_URL) as session:
            return count_users(session)
    except OSError:
        return 0


def main():
    """CLI entry point — parse args and dispatch to handler."""
    # Startup scan — publish any articles whose sink time has elapsed.
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with db_session(DB_URL) as session:
        publish_ready(session)

    parser = build_parser()
    try:
        import argcomplete
        argcomplete.autocomplete(parser)
    except ImportError:
        pass
    args = parser.parse_args()
    # Default to JSON output for AI consumption; --rich enables human-readable.
    if getattr(args, "rich", False):
        args.json = False
    else:
        args.json = True   # default: JSON for AI
    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()


__all__ = ["main", "build_parser", "_count_users", "_show_dashboard", "_show_welcome"]
