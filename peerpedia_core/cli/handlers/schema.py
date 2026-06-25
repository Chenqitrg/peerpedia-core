# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Schema command — programmatic command discovery for AI agents and power users.

Outputs JSON Schema describing every CLI command: parameters, types,
required fields, return schemas, error codes, and workflow relationships.
"""

from __future__ import annotations

import json
import sys


def _param_schema(argspec: tuple, kwargs: dict) -> dict:
    """Convert an argparse arg spec to a JSON Schema property."""
    flags, meta = argspec, kwargs
    name = flags[0].lstrip("-").replace("-", "_")
    # Detect type from kwargs
    ptype = "string"
    if "type" in meta:
        t = meta["type"]
        if t is int:
            ptype = "integer"
        elif t is bool or meta.get("action") in ("store_true", "store_false"):
            ptype = "boolean"
    elif meta.get("action") in ("store_true", "store_false"):
        ptype = "boolean"

    schema: dict = {"type": ptype, "description": meta.get("help", "")}
    # Positional args (no leading -) are required unless nargs="?".
    # Optional flags (--foo) are required only if kwargs["required"] is True.
    is_positional = not flags[0].startswith("-")
    if is_positional:
        if meta.get("nargs") != "?":
            schema["required"] = True
    elif meta.get("required"):
        schema["required"] = True
    if "choices" in meta:
        schema["enum"] = list(meta["choices"])
    if "default" in meta:
        schema["default"] = meta["default"]
    return name, schema


def _build_command_schema(group_name: str, sub_name: str,
                          handler, arg_specs: list) -> dict:
    """Build a single command's JSON Schema entry."""
    # Build the CLI invocation string
    parts = ["peerpedia"]
    if group_name:
        parts.append(group_name)
    if sub_name:
        parts.append(sub_name)

    props = {}
    required: list[str] = []
    for spec in arg_specs:
        name, pschema = _param_schema(spec[0], spec[1])
        props[name] = pschema
        if pschema.pop("required", False):
            required.append(name)

    schema: dict = {
        "name": f"{group_name}_{sub_name}" if group_name and sub_name else (sub_name or group_name),
        "cli": " ".join(parts) + " " + " ".join(
            f"<{r}>" if r in required else f"[--{r} <value>]"
            for r in props
        ) if props else " ".join(parts),
        "description": (handler.__doc__ or "").splitlines()[0].strip(),
        "parameters": {
            "type": "object",
            "properties": props,
        },
    }
    if required:
        schema["parameters"]["required"] = required

    return schema


def _cmd_schema(args):
    """Output the full command schema as JSON (for AI tool discovery).

    Usage: ``peerpedia schema [command]``

    Without arguments, outputs every available command.
    With a command name, outputs just that command's schema.
    """
    # Lazy import to avoid circular dependency (parser → handlers → schema → parser).
    from peerpedia_core.cli.parser import COMMAND_GROUPS, TOP_LEVEL  # noqa: PLC0415

    commands: list[dict] = []

    # Nested command groups (e.g. ``article create``)
    for name, _help, subcommands in COMMAND_GROUPS:
        for sub_name, handler, arg_specs in subcommands:
            if sub_name:
                commands.append(_build_command_schema(name, sub_name, handler, arg_specs))
            else:
                commands.append(_build_command_schema(name, "", handler, arg_specs))

    # Top-level commands (e.g. ``fork``, ``follow``)
    for name, handler, arg_specs in TOP_LEVEL:
        commands.append(_build_command_schema("", name, handler, arg_specs))

    # Filter by command name if provided
    target = getattr(args, "command", None)
    if target:
        commands = [c for c in commands if c["name"] == target or c["name"].endswith(f"_{target}")]
        if not commands:
            print(json.dumps({"error": "NOT_FOUND", "detail": f"No command matching '{target}'"}))
            sys.exit(1)

    output = {
        "version": "1.0",
        "commands": commands,
    }
    print(json.dumps(output, indent=2, default=str))
