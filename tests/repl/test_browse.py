# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Unit tests for pure rendering functions in repl/browse.py.

These functions have no DB/IO dependencies — they only format data.
Testing them here means the browser views are verified without
launching a full prompt_toolkit Application.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from peerpedia_core.presentation.rich.components import star_string
from peerpedia_core.repl.browse import (
    BrowserCursor,
    _browser_result,
    _format_star_rating,
    _format_status_label,
    _render_compact_card,
    _render_full_card,
    _render_user_line,
    _review_status_text,
    _reviewer_name,
    _user_status_text,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Test doubles — light stubs with just the attributes each renderer needs
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class _ArticleStub:
    id: str = "abc123"
    title: str = "Test Article"
    status: str = "draft"
    score: dict | None = None


@dataclass
class _ReviewStub:
    reviewer_id: str = "rev001"
    scores: dict | None = None


@dataclass
class _UserStub:
    id: str = "u1"
    name: str = "Alice"
    follower_count: int = 42


# ═══════════════════════════════════════════════════════════════════════════════
# _browser_result
# ═══════════════════════════════════════════════════════════════════════════════


def test_browser_result():
    assert _browser_result("publish", "abc") == "publish:abc"
    assert _browser_result("follow", "u1") == "follow:u1"


# ═══════════════════════════════════════════════════════════════════════════════
# _format_status_label
# ═══════════════════════════════════════════════════════════════════════════════


def test_format_status_label_normal():
    assert _format_status_label("sedimentation") == "SEDI"


def test_format_status_label_short():
    assert _format_status_label("dr") == "DR"


def test_format_status_label_none():
    assert _format_status_label(None) == "?"
    assert _format_status_label("") == "?"


# ═══════════════════════════════════════════════════════════════════════════════
# star_string (from presentation)
# ═══════════════════════════════════════════════════════════════════════════════


def test_star_string():
    assert star_string(3) == "★★★☆☆"
    assert star_string(0) == "☆☆☆☆☆"
    assert star_string(5) == "★★★★★"
    assert star_string(3, max_val=3) == "★★★"


# ═══════════════════════════════════════════════════════════════════════════════
# _format_star_rating
# ═══════════════════════════════════════════════════════════════════════════════


def test_format_star_rating_with_scores():
    stars, avg = _format_star_rating({"orig": 4, "rigor": 3, "comp": 5})
    assert avg == 4.0
    assert stars == "★★★★☆"


def test_format_star_rating_empty():
    stars, avg = _format_star_rating({})
    assert avg == 0.0
    assert stars == "  —  "


def test_format_star_rating_none():
    stars, avg = _format_star_rating(None)
    assert avg == 0.0
    assert stars == "  —  "


# ═══════════════════════════════════════════════════════════════════════════════
# _reviewer_name
# ═══════════════════════════════════════════════════════════════════════════════


def test_reviewer_name_found():
    r = _ReviewStub(reviewer_id="rev1")
    users = {"rev1": _UserStub(id="rev1", name="Bob")}
    assert _reviewer_name(r, users) == "Bob"


def test_reviewer_name_not_found():
    r = _ReviewStub(reviewer_id="rev99")
    assert _reviewer_name(r, {}) == "rev99"


def test_reviewer_name_no_id():
    r = _ReviewStub(reviewer_id="")
    assert _reviewer_name(r, {}) == ""


# ═══════════════════════════════════════════════════════════════════════════════
# _render_compact_card / _render_full_card
# ═══════════════════════════════════════════════════════════════════════════════


def test_render_compact_card():
    a = _ArticleStub(id="abc", title="My Article", status="draft",
                     score={"originality": 4})
    result = _render_compact_card(a, "▸", "class:selected")
    assert len(result) == 1
    style, text = result[0]
    assert style == "class:selected"
    assert "abc" in text
    assert "DRAF" in text
    assert "★" in text


def test_render_compact_card_unselected():
    a = _ArticleStub(status="published")
    result = _render_compact_card(a, " ", "")
    assert len(result) == 1
    style, text = result[0]
    assert style == ""
    assert "PUBL" in text


def test_render_compact_card_no_score():
    a = _ArticleStub()
    result = _render_compact_card(a, "▸", "cls")
    _, text = result[0]
    assert "—" in text


def test_render_full_card():
    a = _ArticleStub(id="abc", title="Full", status="sedimentation",
                     score={"orig": 3, "rigor": 4})
    result = _render_full_card(a, "▸", "class:selected")
    # header + 2 score lines + blank separator = 4 lines
    assert len(result) >= 3
    # last fragment should be a blank separator
    assert result[-1] == ("", "\n")


def test_render_full_card_no_status():
    a = _ArticleStub(status=None)
    result = _render_full_card(a, " ", "")
    _, text = result[0]
    assert "?" in text


# ═══════════════════════════════════════════════════════════════════════════════
# _render_user_line / _user_status_text
# ═══════════════════════════════════════════════════════════════════════════════


def test_render_user_line_selected():
    u = _UserStub(name="Alice", follower_count=10)
    style, text = _render_user_line(u, rank=1, is_selected=True, is_self=False)
    assert style == "class:selected"
    assert "▸" in text
    assert "Alice" in text
    assert "10 followers" in text
    assert "(you)" not in text


def test_render_user_line_self():
    u = _UserStub(name="Alice")
    style, text = _render_user_line(u, rank=3, is_selected=False, is_self=True)
    assert "(you)" in text
    assert "▸" not in text


def test_user_status_text_self():
    u = _UserStub(name="Alice")
    text = _user_status_text(u, index=0, total=5, is_self=True)
    assert "(you)" in text
    assert "Enter: follow" not in text


def test_user_status_text_other():
    u = _UserStub(name="Bob")
    text = _user_status_text(u, index=2, total=5, is_self=False)
    assert "Enter: follow" in text
    assert "(you)" not in text


# ═══════════════════════════════════════════════════════════════════════════════
# _review_status_text
# ═══════════════════════════════════════════════════════════════════════════════


def test_review_status_text():
    r = _ReviewStub(reviewer_id="rev1")
    users = {"rev1": _UserStub(id="rev1", name="Charlie")}
    text = _review_status_text(r, index=0, total=3, users_by_id=users)
    assert "1/3" in text
    assert "Charlie" in text
    assert "Enter: view" in text


# ═══════════════════════════════════════════════════════════════════════════════
# BrowserCursor
# ═══════════════════════════════════════════════════════════════════════════════


def test_cursor_move_wraps():
    c = BrowserCursor(index=0)
    c.move(1, 3)
    assert c.index == 1
    c.move(1, 3)
    assert c.index == 2
    c.move(1, 3)
    assert c.index == 0


def test_cursor_move_backward():
    c = BrowserCursor(index=0)
    c.move(-1, 5)
    assert c.index == 4
