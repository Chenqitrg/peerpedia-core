# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""JSON Schema generation — from shared ``CommandSpec``, not CLI argparse.

Used by ``peerpedia schema`` so AI tools can discover the command surface.
Reads ``COMMAND_GROUPS`` and ``TOP_LEVEL_COMMANDS`` directly — no CLI import.
"""

from __future__ import annotations

import json

from peerpedia_core.app.commandspec.registry import COMMAND_GROUPS, TOP_LEVEL_COMMANDS
from peerpedia_core.app.commandspec.types import ArgSpec, CommandGroupSpec, _UNSET


# ── Public entry point ────────────────────────────────────────────────────

def build(target: str | None = None) -> str:
    """Return a JSON Schema string for every registered command.

    If *target* is given, filter to commands whose name matches.
    """
    commands = _collect_commands()
    if target:
        commands = _filter_by_target(commands, target)
    return _format_result(commands)


# ── Collect ───────────────────────────────────────────────────────────────

def _collect_commands() -> list[dict]:
    commands: list[dict] = []
    for grp in COMMAND_GROUPS:
        for cmd in grp.commands:
            commands.append(_make_command(
                name=f"{grp.name}_{cmd.action}" if cmd.action else grp.name,
                cmd_id=cmd.cmd_id,
                cli_parts=[grp.name, cmd.action] if cmd.action else [grp.name],
                args=cmd.args,
            ))
    for cmd in TOP_LEVEL_COMMANDS:
        name = cmd.cmd_id
        commands.append(_make_command(
            name=name,
            cmd_id=cmd.cmd_id,
            cli_parts=[name],
            args=cmd.args,
        ))
    return commands


# ── Single command ────────────────────────────────────────────────────────

def _make_command(*, name: str, cmd_id: str,
                  cli_parts: list[str], args: list[ArgSpec]) -> dict:
    props, required = _build_props(args)
    return {
        "name": name,
        "cli": _format_cli(cli_parts, props, required),
        "description": cmd_id,
        "parameters": _wrap_parameters(props, required),
    }


# ── Properties ────────────────────────────────────────────────────────────

def _build_props(arg_specs: list[ArgSpec]) -> tuple[dict, list[str]]:
    props: dict = {}
    required: list[str] = []
    for arg in arg_specs:
        props[arg.name] = _arg_to_property(arg)
        if arg.required:
            required.append(arg.name)
    return props, required


def _arg_to_property(arg: ArgSpec) -> dict:
    prop: dict = {
        "type": _json_type(arg),
        "description": arg.help,
    }
    if arg.choices:
        prop["enum"] = list(arg.choices)
    if arg.default is not _UNSET:
        prop["default"] = arg.default
    return prop


def _json_type(arg: ArgSpec) -> str:
    if arg.type is int:
        return "integer"
    if arg.type is bool:
        return "boolean"
    if not arg.takes_value and not arg.positional:
        return "boolean"
    return "string"


# ── Output ────────────────────────────────────────────────────────────────

def _wrap_parameters(props: dict, required: list[str]) -> dict:
    schema: dict = {"type": "object", "properties": props}
    if required:
        schema["required"] = required
    return schema


def _format_cli(parts: list[str], props: dict, required: list[str]) -> str:
    names = ["peerpedia"] + [p for p in parts if p]
    args = [_cli_arg(r, r in required) for r in props]
    return " ".join(names + args)


def _cli_arg(name: str, required: bool) -> str:
    if required:
        return f"<{name}>"
    return f"[--{name.replace('_', '-')} <value>]"


def _filter_by_target(commands: list[dict], target: str) -> list[dict]:
    result = [c for c in commands
              if c["name"] == target or c["name"].endswith(f"_{target}")]
    if not result:
        _die_not_found(target)
    return result


def _die_not_found(target: str):
    print(json.dumps(
        {"error": "NOT_FOUND", "detail": f"No command matching '{target}'"},
        indent=2))
    import sys
    sys.exit(1)


def _format_result(commands: list[dict]) -> str:
    return json.dumps({"version": "1.0", "commands": commands},
                      indent=2, default=str)
