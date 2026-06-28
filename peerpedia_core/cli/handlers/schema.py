# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Schema command — JSON Schema for AI tool discovery."""

from __future__ import annotations

import json
import sys


def _param_schema(argspec: tuple, kwargs: dict) -> tuple[str, dict]:
    """Convert an argparse arg spec to a JSON Schema property."""
    flags = argspec[0] if isinstance(argspec, tuple) and argspec else ""
    name = flags.lstrip("-").replace("-", "_") if flags else "arg"
    meta = kwargs
    ptype = "string"
    if "type" in meta:
        t = meta["type"]
        if t is int: ptype = "integer"
        elif t is bool or meta.get("action") in ("store_true", "store_false"): ptype = "boolean"
    elif meta.get("action") in ("store_true", "store_false"):
        ptype = "boolean"

    schema: dict = {"type": ptype, "description": meta.get("help", "")}
    is_positional = not flags.startswith("-") if flags else False
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


def _cmd_schema(args):
    """Output the full command schema as JSON (for AI tool discovery)."""
    from peerpedia_core.cli.parser import COMMAND_GROUPS, TOP_LEVEL

    commands: list[dict] = []

    for name, _help, subcommands in COMMAND_GROUPS:
        for entry in subcommands:
            sub_name, cmd_id, arg_specs = entry[0], entry[1], entry[2]
            props = {}
            required: list[str] = []
            for spec in arg_specs:
                pname, pschema = _param_schema(spec[0], spec[1])
                props[pname] = pschema
                if pschema.pop("required", False):
                    required.append(pname)
            parts = ["peerpedia", name]
            if sub_name: parts.append(sub_name)
            cli_str = " ".join(parts) + " " + " ".join(
                f"<{r}>" if r in required else f"[--{r} <value>]"
                for r in props
            ) if props else " ".join(parts)
            schema = {
                "name": f"{name}_{sub_name}" if sub_name else name,
                "cli": cli_str,
                "description": cmd_id,
                "parameters": {"type": "object", "properties": props},
            }
            if required:
                schema["parameters"]["required"] = required
            commands.append(schema)

    for entry in TOP_LEVEL:
        name, cmd_id, arg_specs = entry[0], entry[1], entry[2]
        props = {}
        required: list[str] = []
        for spec in arg_specs:
            pname, pschema = _param_schema(spec[0], spec[1])
            props[pname] = pschema
            if pschema.pop("required", False):
                required.append(pname)
        cli_str = f"peerpedia {name} " + " ".join(
            f"<{r}>" if r in required else f"[--{r} <value>]"
            for r in props
        ) if props else f"peerpedia {name}"
        schema = {
            "name": name,
            "cli": cli_str,
            "description": cmd_id,
            "parameters": {"type": "object", "properties": props},
        }
        if required:
            schema["parameters"]["required"] = required
        commands.append(schema)

    target = getattr(args, "command", None)
    if target:
        commands = [c for c in commands if c["name"] == target or c["name"].endswith(f"_{target}")]
        if not commands:
            print(json.dumps({"error": "NOT_FOUND", "detail": f"No command matching '{target}'"}))
            sys.exit(1)

    print(json.dumps({"version": "1.0", "commands": commands}, indent=2, default=str))
