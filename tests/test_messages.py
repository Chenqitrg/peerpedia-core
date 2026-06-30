# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Tests for messages.py — centralized message registry."""


from peerpedia_core.messages import Kind, Msg, log_text, lookup


# ═══════════════════════════════════════════════════════════════════════════════
# lookup
# ═══════════════════════════════════════════════════════════════════════════════


class TestLookup:
    def test_registered_code_returns_match(self):
        """Known code returns (code, Msg) pair."""
        code, msg = lookup("OK")
        assert code == "OK"
        assert isinstance(msg, Msg)
        assert msg.kind == Kind.SUCCESS

    def test_empty_code_returns_success(self):
        """Empty code is treated as success — data-only result, no display."""
        code, msg = lookup("")
        assert code == ""
        assert msg.kind == Kind.SUCCESS
        assert msg.text == ""

    def test_unregistered_code_returns_error(self):
        """Unknown code gets an ERROR-kind Msg with the code as message."""
        code, msg = lookup("NONEXISTENT_CODE_XYZ")
        assert code == "NONEXISTENT_CODE_XYZ"
        assert msg.kind == Kind.ERROR
        assert msg.text == "NONEXISTENT_CODE_XYZ"


# ═══════════════════════════════════════════════════════════════════════════════
# log_text
# ═══════════════════════════════════════════════════════════════════════════════


class TestLogText:
    def test_no_format_args(self):
        """Without format kwargs, returns the raw template."""
        result = log_text("OK")
        assert "✓" in result

    def test_with_format_args(self):
        """Format kwargs are interpolated into the template."""
        result = log_text("REGISTERED", name="Alice", id="abc123")
        assert "Alice" in result
        assert "abc123" in result

    def test_log_text_prefers_log_text_field(self):
        """When Msg.log_text is set, it's used instead of Msg.text."""
        result = log_text("L_DISCOVERED_PEERS", count=5, seed="peer.example.com")
        assert "5" in result
        assert "peer.example.com" in result


# ═══════════════════════════════════════════════════════════════════════════════
# Msg and Kind
# ═══════════════════════════════════════════════════════════════════════════════


class TestMsgDataclass:
    def test_defaults(self):
        """Msg defaults: kind=SUCCESS, no suggestion, no see_also, no log_text."""
        msg = Msg("hello")
        assert msg.text == "hello"
        assert msg.kind == Kind.SUCCESS
        assert msg.suggestion == ""
        assert msg.see_also == ()
        assert msg.log_text == ""

    def test_frozen(self):
        """Msg is immutable — prevents accidental mutation of the registry."""
        msg = Msg("hello")
        with __import__("pytest").raises(Exception):
            msg.text = "modified"
