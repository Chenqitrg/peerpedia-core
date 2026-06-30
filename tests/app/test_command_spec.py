# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Tests for app/commandspec/ — registry/handler/schema consistency invariants.

Validates that the registry, handlers, and schema stay in lockstep:
every handler's dict-key usage matches the declared ArgSpec, every spec
is findable, no duplicate IDs or collisions, and the schema covers everything.
"""

import ast
import inspect
import json

import pytest

from peerpedia_core.app.commandspec import (
    COMMAND_GROUPS,
    TOP_LEVEL_COMMANDS,
    find_spec,
    spec_for_cmd_id,
)
from peerpedia_core.app.commandspec.schema import build as build_schema


# ── Helpers ──────────────────────────────────────────────────────────────────


def _all_specs():
    """Yield every CommandSpec across all groups and top-level."""
    for g in COMMAND_GROUPS:
        yield from g.commands
    yield from TOP_LEVEL_COMMANDS


def _handler_source(handler_fn) -> str:
    """Return the source code of a handler function."""
    return inspect.getsource(handler_fn)


def _args_accesses(source: str) -> tuple[set[str], set[str]]:
    """Parse handler source, return (direct_access_keys, get_access_keys).

    direct_access:  args["key"] or args['key']
    get_access:     args.get("key") or args.get('key')
    """
    direct: set[str] = set()
    getter: set[str] = set()
    tree = ast.parse(source)
    for node in ast.walk(tree):
        # args["key"]  →  Subscript( Name('args'), Constant('key') )
        if isinstance(node, ast.Subscript):
            if (isinstance(node.value, ast.Name) and node.value.id == "args"
                    and isinstance(node.slice, ast.Constant)):
                direct.add(node.slice.value)
        # args.get("key") or args.get("key", default)
        if isinstance(node, ast.Call):
            if (isinstance(node.func, ast.Attribute)
                    and node.func.attr == "get"
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "args"
                    and node.args
                    and isinstance(node.args[0], ast.Constant)):
                getter.add(node.args[0].value)
    return direct, getter


# ═══════════════════════════════════════════════════════════════════════════════
# Command ID uniqueness and lookup
# ═══════════════════════════════════════════════════════════════════════════════


class TestCommandIds:
    def test_cmd_ids_unique(self):
        """No duplicate cmd_id across COMMAND_GROUPS and TOP_LEVEL_COMMANDS."""
        ids = [s.cmd_id for s in _all_specs()]
        dupes = [x for x in ids if ids.count(x) > 1]
        assert not dupes, f"Duplicate cmd_ids: {set(dupes)}"

    def test_every_spec_findable_by_id(self):
        """Every CommandSpec is findable via spec_for_cmd_id."""
        for spec in _all_specs():
            result = spec_for_cmd_id(spec.cmd_id)
            assert result is not None, f"spec_for_cmd_id({spec.cmd_id!r}) returned None"
            assert result.cmd_id == spec.cmd_id

    def test_grouped_specs_findable_by_key(self):
        """Every grouped CommandSpec is findable via find_spec(group, action)."""
        for g in COMMAND_GROUPS:
            for spec in g.commands:
                result = find_spec(spec.group, spec.action)
                assert result is not None, (
                    f"find_spec({spec.group!r}, {spec.action!r}) returned None"
                )
                assert result.cmd_id == spec.cmd_id

    def test_no_lookup_collisions(self):
        """No two grouped specs share the same (group, action) key.
        Top-level commands with group="" may collide on ("", None) — they
        are looked up by cmd_id, not by (group, action)."""
        seen: dict[tuple, str] = {}
        for spec in _all_specs():
            # Skip top-level commands — they share group="" action=None
            if spec.group == "":
                continue
            key = (spec.group, spec.action)
            if key in seen:
                raise AssertionError(
                    f"Lookup collision: {spec.cmd_id} and {seen[key]} "
                    f"both keyed as {key}"
                )
            seen[key] = spec.cmd_id


# ═══════════════════════════════════════════════════════════════════════════════
# Handler ↔ registry consistency
# ═══════════════════════════════════════════════════════════════════════════════


class TestHandlerRegistryConsistency:
    def test_every_handler_referenced_in_registry(self):
        """Every function in handlers.py is referenced by at least one CommandSpec."""
        from peerpedia_core.app.commandspec import handlers as h

        handler_names = {
            name for name, obj in inspect.getmembers(h, inspect.isfunction)
            if not name.startswith("_")
        }
        referenced = {
            spec.handler.__name__
            for spec in _all_specs()
            if spec.handler is not None
        }
        unreferenced = handler_names - referenced
        assert not unreferenced, (
            f"Handler functions not referenced by any CommandSpec: {unreferenced}"
        )

    def test_every_spec_handler_exists(self):
        """Every CommandSpec.handler that is not None references a real function."""
        for spec in _all_specs():
            if spec.handler is None:
                continue
            assert callable(spec.handler), (
                f"{spec.cmd_id}: handler {spec.handler} is not callable"
            )

    def test_handler_args_match_spec(self):
        """Every args["key"] or args.get("key") in a handler must have a
        corresponding ArgSpec in the CommandSpec, and every required ArgSpec
        must be accessed directly (not via .get())."""
        from peerpedia_core.app.commandspec import handlers as h

        # Build lookup: cmd_id → set of arg names
        spec_args: dict[str, set[str]] = {}
        spec_required: dict[str, set[str]] = {}
        for spec in _all_specs():
            names = {a.name for a in spec.args}
            spec_args[spec.cmd_id] = names
            spec_required[spec.cmd_id] = {a.name for a in spec.args if a.required}

        # Collect all handler-by-cmd_id
        for spec in _all_specs():
            if spec.handler is None:
                continue
            fn = spec.handler
            try:
                source = _handler_source(fn)
            except OSError:
                continue  # can't get source (e.g. built-in), skip
            direct, getter = _args_accesses(source)
            all_accessed = direct | getter
            declared = spec_args.get(spec.cmd_id, set())
            required = spec_required.get(spec.cmd_id, set())

            # Every accessed key must be declared
            undeclared = all_accessed - declared
            assert not undeclared, (
                f"{spec.cmd_id}: handler accesses undeclared arg keys {undeclared}"
            )

            # Every required key must be accessed directly (args["key"]),
            # not via .get() — because if it's required, it should never
            # be missing and .get() would silently return None.
            required_via_get = required & getter
            assert not required_via_get, (
                f"{spec.cmd_id}: required args accessed via .get() "
                f"instead of direct access: {required_via_get}"
            )


# ═══════════════════════════════════════════════════════════════════════════════
# Schema consistency
# ═══════════════════════════════════════════════════════════════════════════════


class TestSchemaConsistency:
    def test_schema_contains_all_commands(self):
        """schema.build() includes every command with a handler."""
        schema_str = build_schema()
        schema = json.loads(schema_str)
        schema_cmds = {c["name"] for c in schema["commands"]}

        for spec in _all_specs():
            if spec.handler is None:
                continue
            # Schema name: group_action for grouped, cmd_id for top-level
            # When action is None (e.g. "following"), name is just the group
            if spec.group and spec.action:
                name = f"{spec.group}_{spec.action}"
            elif spec.group:
                name = spec.group
            else:
                name = spec.cmd_id
            assert name in schema_cmds, (
                f"{spec.cmd_id}: not found in schema output (expected name={name!r})"
            )

    def test_schema_version(self):
        """Schema output includes version field."""
        schema_str = build_schema()
        schema = json.loads(schema_str)
        assert "version" in schema
        assert schema["version"] == "1.0"
