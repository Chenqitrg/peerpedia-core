# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""REPL execution engine — parse, dispatch, commit, render.

Thin orchestration layer.  Command specs come from ``app/commandspec/``;
rendering from ``repl/display.py``.  No argparse, no ``@with_context``.
"""

from __future__ import annotations

import logging
import os
import shlex
from typing import Any

from peerpedia_core.app.commandspec import (
    COMMAND_GROUPS, TOP_LEVEL_COMMANDS,
    ArgSpec, CommandSpec, _UNSET, find_spec,
)
from peerpedia_core.app.context import build_context
from peerpedia_core.exceptions import PeerpediaError
from peerpedia_core.repl.display import render_error, render_result
from peerpedia_core.repl.state import console, session_scope

_log = logging.getLogger(__name__)

# Commands that need interactive password prompting when password is missing
_PASSWORD_COMMANDS = {"account.register", "account.login", "account.recover"}


# ═══════════════════════════════════════════════════════════════════════════════
# Parser
# ═══════════════════════════════════════════════════════════════════════════════

def _parse_args(raw_args: list[str], spec: CommandSpec) -> dict[str, Any]:
    """Parse shlex-split args into a dict based on *spec.args*.

    Supports ``--key=value``, ``--key value``, ``--flag`` (bool), and
    positional args.  Applies type coercion and defaults from ArgSpec.
    """
    result: dict[str, Any] = {}
    positional_queue = [a for a in spec.args if a.positional]
    pos_idx = 0
    i = 0

    while i < len(raw_args):
        a = raw_args[i]
        if a.startswith("--"):
            key, val, consumed = _parse_flag(a, raw_args, i, spec)
            if key is not None:
                result[key] = val
                i += consumed
            else:
                i += 1
        else:
            if pos_idx < len(positional_queue):
                arg_spec = positional_queue[pos_idx]
                result[arg_spec.name] = _coerce(a, arg_spec)
                pos_idx += 1
            i += 1

    # Apply defaults for args not in result
    for arg in spec.args:
        if arg.name not in result:
            if arg.default is not _UNSET:
                result[arg.name] = arg.default
            elif arg.takes_value is False:
                result[arg.name] = False

    # Resolve PEERPEDIA_SERVER env var for server args
    if "server" in result and not result["server"]:
        env_server = os.environ.get("PEERPEDIA_SERVER", "")
        if env_server:
            result["server"] = env_server

    return result


def _parse_flag(a: str, raw_args: list[str], i: int, spec: CommandSpec
                ) -> tuple[str | None, Any, int]:
    """Parse a ``--flag`` token.  Returns (key, value, tokens_consumed)."""
    if "=" in a:
        key_part, val = a[2:].split("=", 1)
        key = key_part.replace("-", "_")
    else:
        key = a[2:].replace("-", "_")
        val = None

    for arg in spec.args:
        if arg.name == key:
            if arg.takes_value:
                if val is not None:
                    return key, _coerce(val, arg), 1
                if i + 1 < len(raw_args) and not raw_args[i + 1].startswith("--"):
                    return key, _coerce(raw_args[i + 1], arg), 2
            else:
                return key, True, 1

    return None, None, 1


def _coerce(val: str, arg: ArgSpec) -> Any:
    """Coerce a string value to *arg.type*, with optional choices validation."""
    if arg.type is None:
        coerced = val
    else:
        try:
            coerced = arg.type(val)
        except (ValueError, TypeError):
            raise PeerpediaError("BAD_ARG_TYPE", context={
                "arg": arg.name, "expected": arg.type.__name__, "got": val,
            })
    if arg.choices and coerced not in arg.choices:
        raise PeerpediaError("BAD_ARG_CHOICE", context={
            "arg": arg.name, "got": str(coerced),
            "choices": ", ".join(str(c) for c in arg.choices),
        })
    return coerced


# ═══════════════════════════════════════════════════════════════════════════════
# Engine
# ═══════════════════════════════════════════════════════════════════════════════

def execute(cmd_str: str) -> bool:
    """Parse and execute a single REPL command.

    Creates a fresh DB session per command (unit-of-work pattern).
    Returns False to exit the REPL, True to continue.
    """
    cmd_str = cmd_str.strip()
    if not cmd_str:
        return True

    # ── Parse ─────────────────────────────────────────────────────────────
    try:
        parts = shlex.split(cmd_str)
    except ValueError as e:
        console.print(f"[error]✗ Parse error: {e}[/]")
        return True

    # ── Lookup ────────────────────────────────────────────────────────────
    group = parts[0]
    action: str | None = None
    rest = parts[1:]

    if len(parts) >= 2 and find_spec(group, parts[1]):
        action = parts[1]
        rest = parts[2:]
    elif find_spec(group, None):
        pass  # top-level command
    else:
        found = False
        if len(parts) >= 2:
            for grp_spec in _iter_all_specs():
                if grp_spec.group == group and grp_spec.action == parts[1]:
                    action = parts[1]
                    rest = parts[2:]
                    found = True
                    break
        if not found and find_spec(group, None) is None:
            console.print(f"[error]✗ Unknown command: {cmd_str}[/]. Try :help")
            return True

    spec = find_spec(group, action)
    if spec is None:
        console.print(f"[error]✗ Unknown command: {cmd_str}[/]. Try :help")
        return True

    if spec.frontend == "cli" or spec.handler is None:
        console.print(f"[muted]{spec.cmd_id} is not available in REPL.[/]")
        return True

    # ── Parse args ────────────────────────────────────────────────────────
    try:
        args = _parse_args(rest, spec)
    except PeerpediaError as e:
        render_error(e)
        return True

    # ── Interactive password prompt ───────────────────────────────────────
    if spec.cmd_id in _PASSWORD_COMMANDS and "password" not in args:
        try:
            from peerpedia_core.editor import get_password as _get_password
            from argparse import Namespace
            ns = Namespace(name=args.get("name", ""), password=None, json=False, rich=True)
            confirm = (spec.cmd_id == "account.register")
            args["password"] = _get_password(ns, confirm=confirm)
        except (EOFError, KeyboardInterrupt):
            console.print("\n[muted]Cancelled.[/]")
            return True

    # ── Execute (per-command session) ────────────────────────────────────
    try:
        with session_scope() as db:
            ctx = build_context(db)
            result = spec.handler(ctx, args)
    except PeerpediaError as e:
        render_error(e)
        return True
    except Exception as e:
        _log.exception("REPL command failed: %s", cmd_str)
        console.print(f"[error]✗ Internal error: {e}[/]")
        return True

    # ── Render ────────────────────────────────────────────────────────────
    render_result(result)
    return True


def _iter_all_specs():
    """Iterate all command specs (for auto-resolve fallback)."""
    for grp in COMMAND_GROUPS:
        yield from grp.commands
    yield from TOP_LEVEL_COMMANDS
