# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Tests for cli/dispatch.py — command dispatch and handler mapping."""


# ═══════════════════════════════════════════════════════════════════════════════
# get_cmd_map_for_parser
# ═══════════════════════════════════════════════════════════════════════════════


class TestGetCmdMapForParser:
    def test_returns_dict(self):
        """Returns a dict mapping flat command names to [group, subcmd]."""
        from peerpedia_core.cli.dispatch import get_cmd_map_for_parser

        result = get_cmd_map_for_parser()
        assert isinstance(result, dict)
        # Should include well-known commands
        assert "article create" in result
        assert result["article create"] == ["article", "create"]

    def test_single_action_commands_have_alias(self):
        """Commands that are unique across groups also get a short alias.
        e.g. 'school' → ['school', None] since it's a top-level command."""
        from peerpedia_core.cli.dispatch import get_cmd_map_for_parser

        result = get_cmd_map_for_parser()
        # Top-level commands appear as their own name
        assert "school" in result

    def test_follow_is_top_level(self):
        """Top-level commands like 'follow' get their own entry."""
        from peerpedia_core.cli.dispatch import get_cmd_map_for_parser

        result = get_cmd_map_for_parser()
        assert "follow" in result

    def test_full_group_command_names_exist(self):
        """Every 'group action' full name has an entry."""
        from peerpedia_core.cli.dispatch import get_cmd_map_for_parser

        result = get_cmd_map_for_parser()
        assert "bookmark add" in result
        assert "share add" in result
        assert "maintainer add" in result


# ═══════════════════════════════════════════════════════════════════════════════
# _HANDLER_MAP
# ═══════════════════════════════════════════════════════════════════════════════


class TestHandlerMap:
    def test_every_handler_is_tuple_of_two(self):
        """Every handler entry is (module_path, function_name)."""
        from peerpedia_core.cli.dispatch import _HANDLER_MAP

        for cmd_id, (mod, func) in _HANDLER_MAP.items():
            assert isinstance(mod, str), f"{cmd_id}: module {mod!r}"
            assert isinstance(func, str), f"{cmd_id}: func {func!r}"
            assert "." in mod, f"{cmd_id}: module {mod!r} is not a dotted path"

    def test_all_handler_func_names_are_valid(self):
        """Every handler function name in the map starts with _cmd_."""
        from peerpedia_core.cli.dispatch import _HANDLER_MAP

        for cmd_id, (mod, func) in _HANDLER_MAP.items():
            assert func.startswith("_cmd_"), (
                f"{cmd_id}: handler func {func!r} does not start with '_cmd_'"
            )
