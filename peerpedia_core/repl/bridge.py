# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""CLI bridge — resolve a command string against the CLI command map and
execute it via argparse.  Pure translation layer; does not import from
``dispatch.py`` (no cycle).
"""

from __future__ import annotations

import io
import sys

from rich.panel import Panel

from peerpedia_core.cli.parser import get_cmd_map
from peerpedia_core.repl.help import _show_topic_help
from peerpedia_core.repl.state import console


def execute(args_list: list[str], parser) -> bool:
    """Look up *args_list* in the CLI command map and run via argparse.

    Returns True to continue the REPL, False to exit (should not happen
    for CLI commands — they always return True).
    """
    cmd_map = get_cmd_map()

    # Try compound name first (e.g. "review submit"), then short name
    mapping = None
    rest_args: list[str] = []
    cmd: str = args_list[0]

    if len(args_list) >= 2:
        compound = f"{args_list[0]} {args_list[1]}"
        if compound in cmd_map:
            mapping = cmd_map[compound]
            rest_args = args_list[2:]
            cmd = compound

    if mapping is None:
        cmd = args_list[0]
        if cmd in cmd_map:
            mapping = cmd_map[cmd]
            rest_args = args_list[1:]

    if mapping is None:
        console.print(f"[error]✗ Unknown command: {cmd}[/]. Try :help")
        return True

    argv = ["peerpedia"] + mapping + rest_args

    # ── Intercept --help / -h → show Rich help (same as :help) ────────
    if "--help" in rest_args or "-h" in rest_args:
        if len(mapping) == 2:
            topic = mapping[1]
        elif len(mapping) == 1:
            topic = mapping[0]
        else:
            topic = cmd
        _show_topic_help(topic)
        return True

    # ── Execute via argparse ──────────────────────────────────────────
    try:
        old_stderr = sys.stderr
        sys.stderr = io.StringIO()
        try:
            args = parser.parse_known_args(argv[1:])[0]
        except SystemExit:
            console.print("[muted](type :help for available commands)[/]")
            return True
        finally:
            sys.stderr = old_stderr

        if hasattr(args, "func"):
            if not getattr(args, "json", False):
                args.json = False
            args.rich = True
            args.func(args)
        else:
            parser.print_help()
    except SystemExit:
        # _die() in handler — error already displayed, don't crash REPL.
        pass
    except Exception as e:
        console.print(Panel(str(e), title="Error", border_style="error",
                            title_align="left"))

    return True
