# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Unit tests for browse.py — school browser rendering and cursor."""

from __future__ import annotations

from dataclasses import dataclass

from peerpedia_core.repl.browse import (
    BrowserCursor,
    _render_user_line,
    _user_status_text,
)


@dataclass
class _UserStub:
    id: str = "u1"
    name: str = "Alice"
    follower_count: int = 42


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


# ═══════════════════════════════════════════════════════════════════════════════
# _render_user_line / _user_status_text
# ═══════════════════════════════════════════════════════════════════════════════


def test_render_user_line_selected():
    u = _UserStub(name="Alice", follower_count=10)
    style, text = _render_user_line(u, rank=1, is_selected=True, is_self=False)
    assert style == "class:selected"
    assert "Alice" in text
    assert "10 followers" in text
    assert "(you)" not in text


def test_render_user_line_self():
    u = _UserStub(name="Alice")
    style, text = _render_user_line(u, rank=3, is_selected=False, is_self=True)
    assert "(you)" in text


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
