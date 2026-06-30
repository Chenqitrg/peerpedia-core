# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Tests for cli/info.py — output formatting and rendering."""

import json
from argparse import Namespace
from unittest.mock import patch

import pytest


# ═══════════════════════════════════════════════════════════════════════════════
# _format
# ═══════════════════════════════════════════════════════════════════════════════


class TestFormat:
    def test_simple_substitution(self):
        """Replaces known keys, leaves unknown keys as {key}."""
        from peerpedia_core.cli.info import _format
        result = _format("Hello {name}", {"name": "Alice"})
        assert result == "Hello Alice"

    def test_missing_key_preserved(self):
        """Missing keys are preserved as {key} — no KeyError or empty string."""
        from peerpedia_core.cli.info import _format
        result = _format("Hello {name}", {})
        assert result == "Hello {name}"

    def test_multiple_keys(self):
        """Multiple substitutions work correctly."""
        from peerpedia_core.cli.info import _format
        result = _format("{a} {b} {c}", {"a": "1", "b": "2", "c": "3"})
        assert result == "1 2 3"

    def test_rich_markup_preserved(self):
        """Rich markup tags like [accent]...[/] are left untouched."""
        from peerpedia_core.cli.info import _format
        result = _format("[accent]{name}[/]", {"name": "Alice"})
        assert result == "[accent]Alice[/]"


# ═══════════════════════════════════════════════════════════════════════════════
# _json_out
# ═══════════════════════════════════════════════════════════════════════════════


class TestJsonOut:
    def test_outputs_json_dict(self, capsys):
        """Dict data → indented JSON to stdout."""
        from peerpedia_core.cli.info import _json_out
        _json_out({"key": "value", "num": 42})
        captured = capsys.readouterr()
        parsed = json.loads(captured.out)
        assert parsed == {"key": "value", "num": 42}

    def test_outputs_json_list(self, capsys):
        """List data → indented JSON to stdout."""
        from peerpedia_core.cli.info import _json_out
        _json_out([{"id": "a"}, {"id": "b"}])
        captured = capsys.readouterr()
        parsed = json.loads(captured.out)
        assert parsed == [{"id": "a"}, {"id": "b"}]


# ═══════════════════════════════════════════════════════════════════════════════
# _ok
# ═══════════════════════════════════════════════════════════════════════════════


class TestOk:
    def test_prints_checkmark(self):
        """_ok prints a green checkmark + message."""
        from peerpedia_core.cli.info import _ok
        with patch.object(
            __import__("peerpedia_core.cli.info", fromlist=["console"]).console,
            "print",
        ) as mock_print:
            _ok("Done")
            mock_print.assert_called_once()
            args = mock_print.call_args[0]
            # Should contain the checkmark
            assert any("Done" in str(a) for a in args)


# ═══════════════════════════════════════════════════════════════════════════════
# _render_data
# ═══════════════════════════════════════════════════════════════════════════════


class TestRenderData:
    def test_render_dict(self):
        """Dict data → renders via _render_key_value_pairs."""
        from peerpedia_core.cli.info import _render_data
        with patch(
            "peerpedia_core.cli.info._render_key_value_pairs"
        ) as mock_render:
            _render_data({"a": 1, "b": 2})
            mock_render.assert_called_once_with({"a": 1, "b": 2})

    def test_render_list_of_dicts(self):
        """List of dicts → renders via _render_table."""
        from peerpedia_core.cli.info import _render_data
        with patch("peerpedia_core.cli.info._render_table") as mock_render:
            _render_data([{"a": 1}, {"b": 2}])
            mock_render.assert_called_once()

    def test_render_scalar(self):
        """Scalar value → prints directly."""
        from peerpedia_core.cli.info import _render_data
        with patch.object(
            __import__("peerpedia_core.cli.info", fromlist=["console"]).console,
            "print",
        ) as mock_print:
            _render_data("just a string")
            mock_print.assert_called_once()


# ═══════════════════════════════════════════════════════════════════════════════
# _out — error / notify / success paths
# ═══════════════════════════════════════════════════════════════════════════════


class TestOut:
    def test_success_with_json(self, capsys):
        """SUCCESS message with json=True → JSON output, then exit(0)."""
        from peerpedia_core.cli.info import _out

        args = Namespace(json=True)
        with pytest.raises(SystemExit) as exc:
            _out(args, "OK", None, msg="done")
        assert exc.value.code == 0

    def test_error_exits(self):
        """ERROR message → raises SystemExit."""
        from peerpedia_core.cli.info import _out

        args = Namespace(json=False)
        with pytest.raises(SystemExit):
            _out(args, "NOT_FOUND")

    def test_notify_does_not_exit(self):
        """NOTIFY message prints but does not exit."""
        from peerpedia_core.cli.info import _out

        args = Namespace(json=False)
        with patch.object(
            __import__("peerpedia_core.cli.info", fromlist=["console"]).console,
            "print",
        ):
            # Should not raise SystemExit
            _out(args, "W_NO_KNOWN_PEERS")

    def test_log_only_no_exit(self):
        """_log writes to logger, does not exit."""
        from peerpedia_core.cli.info import _log
        # Should not raise — log_text for L_AUTO_SYNC_ARTICLE needs
        # {article}, {server}, {error} format fields
        _log("L_AUTO_SYNC_ARTICLE", article="art-1", server="peer.example.com",
             error="timeout")
