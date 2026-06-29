# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Build JSON Schema from parser command definitions (for AI tool discovery).

Reads ``COMMANDS`` from ``parser.py`` — the same table that builds argparse —
and produces a machine-readable JSON description of every CLI command,
its arguments, types, defaults, and required/optional status.

Used by ``peerpedia schema`` so AI tools (Claude, etc.) can discover
the command surface without reading source code.
"""

from __future__ import annotations

import json


# ── Public entry point ────────────────────────────────────────────────────

def build(target: str | None = None) -> str:
    """Return a JSON Schema string for every registered CLI command.

    If *target* is given, filter to commands whose name matches.
    """
    from peerpedia_core.cli.parser import COMMANDS

    commands = _collect_commands(COMMANDS)
    if target:
        commands = _filter_by_target(commands, target)
    return _format_result(commands)


# ── Collect ───────────────────────────────────────────────────────────────

def _collect_commands(items) -> list[dict]:
    """Dispatch each parser item (group or top-level) into a command dict."""
    from peerpedia_core.cli.parser import CommandGroup

    commands: list[dict] = []
    for item in items:
        if isinstance(item, CommandGroup):
            commands.extend(_commands_from_group(item))
        else:
            commands.append(_command_from_top_level(item))
    return commands


def _commands_from_group(group) -> list[dict]:
    """Yield one dict per sub-command in a group (e.g. ``article create``)."""
    return [
        _make_command(
            name=f"{group.name}_{cmd.name}" if cmd.name else group.name,
            cmd_id=cmd.cmd_id,
            cli_parts=[group.name, cmd.name],
            arg_specs=cmd.args,
        )
        for cmd in group.commands
    ]


def _command_from_top_level(cmd) -> dict:
    """Build a dict for a top-level command (e.g. ``follow``, ``compile``)."""
    return _make_command(
        name=cmd.name,
        cmd_id=cmd.cmd_id,
        cli_parts=[cmd.name],
        arg_specs=cmd.args,
    )


# ── Single command ────────────────────────────────────────────────────────

def _make_command(*, name: str, cmd_id: str,
                  cli_parts: list[str], arg_specs) -> dict:
    """Assemble one command's JSON Schema entry from its parts."""
    props, required = _build_props(arg_specs)
    return {
        "name": name,
        "cli": _format_cli(cli_parts, props, required),
        "description": cmd_id,
        "parameters": _wrap_parameters(props, required),
    }


# ── Properties ────────────────────────────────────────────────────────────

def _build_props(arg_specs) -> tuple[dict, list[str]]:
    """Convert a list of ``ArgSpec`` to ``(props_dict, required_names)``."""
    props: dict = {}
    required: list[str] = []
    for spec in arg_specs:
        name, prop = _arg_to_property(spec.args, spec.kwargs)
        props[name] = prop
        if _is_required(spec):
            required.append(name)
    return props, required


def _arg_to_property(argspec: tuple, kwargs: dict) -> tuple[str, dict]:
    """Map one argparse argument to a JSON Schema property ``(name, prop)``."""
    name = _arg_name(argspec)
    prop: dict = {
        "type": _json_type(kwargs),
        "description": kwargs.get("help", ""),
    }
    if "choices" in kwargs:
        prop["enum"] = list(kwargs["choices"])
    if "default" in kwargs:
        prop["default"] = kwargs["default"]
    return name, prop


# ── Property helpers ──────────────────────────────────────────────────────

def _arg_name(argspec: tuple) -> str:
    """Derive a variable name from an argparse flag (``--max-users`` → ``max_users``)."""
    flags = argspec[0] if isinstance(argspec, tuple) and argspec else ""
    return flags.lstrip("-").replace("-", "_") if flags else "arg"


def _json_type(kwargs: dict) -> str:
    """Map an argparse type/action to a JSON Schema type string."""
    if "type" in kwargs:
        t = kwargs["type"]
        if t is int:
            return "integer"
        if t is bool:
            return "boolean"
    if kwargs.get("action") in ("store_true", "store_false"):
        return "boolean"
    return "string"


def _is_required(spec) -> bool:
    """True when this arg spec is required (positional non-optional, or required=True)."""
    flags = spec.args[0] if isinstance(spec.args, tuple) and spec.args else ""
    is_positional = bool(flags and not flags.startswith("-"))
    if is_positional:
        return spec.kwargs.get("nargs") != "?"
    return bool(spec.kwargs.get("required"))


# ── Output ────────────────────────────────────────────────────────────────

def _wrap_parameters(props: dict, required: list[str]) -> dict:
    """Wrap prop dicts into a JSON Schema ``parameters`` object."""
    schema: dict = {"type": "object", "properties": props}
    if required:
        schema["required"] = required
    return schema


def _format_cli(parts: list[str], props: dict, required: list[str]) -> str:
    """Build a human-readable CLI usage string from command parts + args.

    Example: ``peerpedia article create <id> [--title <value>]``
    """
    names = ["peerpedia"] + [p for p in parts if p]
    args = [_cli_arg(r, r in required) for r in props]
    return " ".join(names + args)


def _cli_arg(name: str, required: bool) -> str:
    """Format one argument as ``<name>`` (required) or ``[--name <value>]`` (optional)."""
    if required:
        return f"<{name}>"
    return f"[--{name} <value>]"


# ── Filter / format ───────────────────────────────────────────────────────

def _filter_by_target(commands: list[dict], target: str) -> list[dict]:
    """Keep only commands whose name matches *target* (exact or suffix)."""
    result = [c for c in commands
              if c["name"] == target or c["name"].endswith(f"_{target}")]
    if not result:
        _die_not_found(target)
    return result


def _die_not_found(target: str):
    """Print a NOT_FOUND error as JSON and exit."""
    print(json.dumps(
        {"error": "NOT_FOUND", "detail": f"No command matching '{target}'"},
        indent=2))
    import sys
    sys.exit(1)


def _format_result(commands: list[dict]) -> str:
    """Serialize the final command list to indented JSON."""
    return json.dumps({"version": "1.0", "commands": commands},
                      indent=2, default=str)
