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
import warnings

# Suppress SQLAlchemy deprecation warnings from user-facing output.
# SAWarning about Subquery coercion is harmless and confusing to users.
warnings.filterwarnings("ignore", category=Warning, module="sqlalchemy")

from peerpedia_core.cli.parser import build_parser
from peerpedia_core.config.paths import DB_PATH, DB_URL
from peerpedia_core.cli.info import console
from peerpedia_core.core import db_session, count_articles, get_user, list_users, publish_ready_articles
from peerpedia_core.cli.session import _read_session
from peerpedia_core.types import short_id
def _count_users() -> int:
    """Return the number of users in the local DB.  Returns 0 on fresh install."""
    try:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        with db_session(DB_URL) as session:
            return len(list_users(session))
    except OSError:
        return 0


def _show_dashboard() -> None:
    """Show a compact status dashboard for returning users."""
    session = _read_session()
    console.print()
    console.print("  [accent]PeerPedia[/] — peer review from the terminal.")
    console.print()

    if session:
        user_id = session.get("user_id", "")
        user_name = session.get("name", "?")
        console.print(f"  Currently: [accent]{user_name}[/] ({short_id(user_id) if user_id else '?'})")

        try:
            with db_session(DB_URL) as db:
                drafts = count_articles(db, statuses={"draft"}, author_id=user_id)
                in_review = count_articles(db, statuses={"sedimentation"}, author_id=user_id)
                published = count_articles(db, statuses={"published"}, author_id=user_id)
                console.print(f"    Drafts:      {drafts}")
                console.print(f"    In review:   {in_review}")
                console.print(f"    Published:   {published}")
        except Exception:
            import logging
            logging.getLogger(__name__).warning(
                "Failed to load dashboard stats", exc_info=True
            )
    else:
        console.print("  [dim]Not logged in.[/]")

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


def main():
    """CLI entry point — parse args and dispatch to handler.

    The top-level router (``__main__.py``) calls this when subcommand
    arguments are present; otherwise it launches the REPL directly.
    ``cli/`` has zero knowledge of ``repl/`` — no circular dependency.
    """
    # Startup scan — publish any articles whose sink time has elapsed
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with db_session(DB_URL) as session:
        publish_ready_articles(session)

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


__all__ = ["main", "build_parser"]
