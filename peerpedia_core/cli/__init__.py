# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

r"""PeerPedia CLI — terminal-based frontend for the PeerPedia backend.

**Hard constraint**: CLI never imports from ``storage/`` directly.  All
data access goes through ``commands/`` facade.  Handlers import from
``cli.handlers`` (facade), not from individual handler modules.

Sub-packages:
  ``display``     — Rich terminal formatting (Layer 0)
  ``helpers``     — DB, editor, user resolution, messaging (Layer 1)
  ``sync_utils``  — auto-sync helpers (Layer 1)
  ``handlers/``   — command implementations (Layer 2)
  ``parser``      — argparse registration (Layer 3)
"""

from __future__ import annotations

import sys

from peerpedia_core.cli.parser import build_parser
from peerpedia_core.config.paths import DB_PATH, DB_URL
from peerpedia_core.commands import db_session, publish_ready_articles
from peerpedia_core.repl import run


def main():
    # Startup scan — publish any articles whose sink time has elapsed

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with db_session(DB_URL) as session:
        publish_ready_articles(session)

    # If no arguments, enter REPL
    if len(sys.argv) == 1:
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
