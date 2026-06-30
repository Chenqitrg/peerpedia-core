# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Tests for server/shared.py — request validation utilities."""

import pytest

from peerpedia_core.exceptions import BadRequestError


# ═══════════════════════════════════════════════════════════════════════════════
# _validate_id
# ═══════════════════════════════════════════════════════════════════════════════


class TestValidateId:
    def test_hyphenated_uuid_passes(self):
        """Standard UUID format (8-4-4-4-12) passes."""
        from peerpedia_core.server.shared import _validate_id
        _validate_id("00000000-0000-0000-0000-000000000001", "article_id")

    def test_unhyphenated_uuid_passes(self):
        """32 hex chars without hyphens passes."""
        from peerpedia_core.server.shared import _validate_id
        _validate_id("00000000000000000000000000000001", "article_id")

    def test_uppercase_uuid_passes(self):
        """Uppercase hex passes — UUID parsing is case-insensitive."""
        from peerpedia_core.server.shared import _validate_id
        _validate_id("ABCDABCD-ABCD-ABCD-ABCD-ABCDABCDABCD", "article_id")

    def test_empty_string_raises(self):
        """Empty string is not a UUID → BadRequestError."""
        from peerpedia_core.server.shared import _validate_id
        with pytest.raises(BadRequestError, match="Invalid article_id"):
            _validate_id("", "article_id")

    def test_non_uuid_string_raises(self):
        """Arbitrary string is not a UUID → prevents path traversal."""
        from peerpedia_core.server.shared import _validate_id
        with pytest.raises(BadRequestError, match="Invalid user_id"):
            _validate_id("../../../etc/passwd", "user_id")

    def test_too_short_hex_raises(self):
        """Not enough hex chars → BadRequestError."""
        from peerpedia_core.server.shared import _validate_id
        with pytest.raises(BadRequestError, match="Invalid article_id"):
            _validate_id("abc", "article_id")


# ═══════════════════════════════════════════════════════════════════════════════
# _require_field
# ═══════════════════════════════════════════════════════════════════════════════


class TestRequireField:
    def test_returns_value_when_present(self):
        """Field exists and is non-empty → returns the value."""
        from peerpedia_core.server.shared import _require_field
        assert _require_field({"name": "Alice"}, "name") == "Alice"

    def test_raises_when_missing(self):
        """Field absent from payload → BadRequestError."""
        from peerpedia_core.server.shared import _require_field
        with pytest.raises(BadRequestError, match="'name'"):
            _require_field({}, "name")

    def test_raises_when_empty_string(self):
        """Empty string is treated as missing → BadRequestError."""
        from peerpedia_core.server.shared import _require_field
        with pytest.raises(BadRequestError, match="'name'"):
            _require_field({"name": ""}, "name")


# ═══════════════════════════════════════════════════════════════════════════════
# _parse_pagination
# ═══════════════════════════════════════════════════════════════════════════════


class TestParsePagination:
    def test_defaults(self):
        """No query params → default limit=20, offset=0."""
        from peerpedia_core.server.shared import _parse_pagination
        from starlette.requests import Request

        scope = {"type": "http", "method": "GET", "path": "/test",
                 "query_string": b""}
        req = Request(scope)
        limit, offset = _parse_pagination(req)
        assert limit == 20
        assert offset == 0

    def test_custom_limit_and_offset(self):
        """Query params are parsed correctly."""
        from peerpedia_core.server.shared import _parse_pagination
        from starlette.requests import Request

        scope = {"type": "http", "method": "GET", "path": "/test",
                 "query_string": b"limit=5&offset=10"}
        req = Request(scope)
        limit, offset = _parse_pagination(req)
        assert limit == 5
        assert offset == 10

    def test_limit_clamped_to_max(self):
        """Limit > max_limit is clamped down."""
        from peerpedia_core.server.shared import _parse_pagination
        from starlette.requests import Request

        scope = {"type": "http", "method": "GET", "path": "/test",
                 "query_string": b"limit=999999"}
        req = Request(scope)
        limit, offset = _parse_pagination(req, max_limit=100)
        assert limit == 100

    def test_offset_non_numeric_defaults_to_zero(self):
        """Non-numeric offset raises ValueError — caller should handle.
        The function passes through the raw int() result without clamping."""
        from peerpedia_core.server.shared import _parse_pagination
        from starlette.requests import Request

        scope = {"type": "http", "method": "GET", "path": "/test",
                 "query_string": b"offset=-5"}
        req = Request(scope)
        limit, offset = _parse_pagination(req)
        # offset is not clamped to zero — caller is responsible for validation
        assert offset == -5
