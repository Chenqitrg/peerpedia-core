# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""REPL display helpers — REPL-specific rendering over shared Rich components.

Result rendering (``render_result``, ``render_error``) is REPL-specific.
Shared components (tables, panels, score stars, user display) live in
``presentation/rich/components.py`` — both CLI and REPL import from there.
"""

from __future__ import annotations

from rich.text import Text

from peerpedia_core.app.result import AppResult
from peerpedia_core.exceptions import PeerpediaError
from peerpedia_core.messages import lookup as _lookup
from peerpedia_core.presentation.rich.components import (
    SCORE_DIM_NAMES,
    display_user as _shared_display_user,
    print_panel as _shared_print_panel,
    print_table as _shared_print_table,
    score_lines as _shared_score_lines,
    score_stars as _shared_score_stars,
    status_badge as _shared_status_badge,
)
from peerpedia_core.repl.state import console

# ── Re-exports (thin wrappers with REPL console) ─────────────────────────────


def _print_table(headers: list[str], rows: list[list[str]],
                 title: str | None = None) -> None:
    _shared_print_table(console, headers, rows, title=title)


def display_user(name: str, user_id: str, *,
                 affiliation: str = "",
                 expertise: list[str] | None = None,
                 reputation: dict | None = None,
                 follower_count: int | None = None,
                 public_key: str | None = None,
                 created_at: str | None = None) -> None:
    _shared_display_user(console, name, user_id,
                         affiliation=affiliation, expertise=expertise,
                         reputation=reputation, follower_count=follower_count,
                         public_key=public_key, created_at=created_at)


def _score_lines(score: dict | None, dims: list[str] | None = None) -> list[str]:
    return _shared_score_lines(score, dims)


def _stars(score: dict | None, dims: list[str] | None = None) -> str:
    return _shared_score_stars(score, dims)


def _status_badge(status: str) -> str:
    return _shared_status_badge(status)


def _print_panel(title: str, content: str) -> None:
    _shared_print_panel(console, title, content)


# ── Result rendering (REPL-specific) ─────────────────────────────────────────


def render_result(result: AppResult) -> None:
    """Render an ``AppResult`` — Rich output, no JSON mode in REPL."""
    for notice in result.notices:
        _render_notice(notice)

    code, m = _lookup(result.code)
    if m.kind.name in ("SUCCESS", "INFO") and m.text:
        msg = m.text.format(**result.params) if result.params else m.text
        console.print(Text("✓ " + msg))
        return

    data = result.data
    if not data:
        return

    if isinstance(data, list) and data and isinstance(data[0], dict):
        _print_table(
            list(data[0].keys()),
            [list(d.values()) for d in data],
        )
    elif isinstance(data, dict):
        items = data.get("items")
        unread = data.get("unread_count")
        if isinstance(items, list):
            if items and isinstance(items[0], dict):
                for u in items:
                    uid = u.get("id") or u.get("user_id", "?")
                    display_user(
                        u.get("name", "?"),
                        uid,
                        affiliation=u.get("affiliation", ""),
                        expertise=u.get("expertise"),
                        follower_count=u.get("follower_count"),
                        public_key=u.get("public_key"),
                        created_at=str(u.get("created_at", "")) if u.get("created_at") else "",
                    )
            elif unread is not None and items:
                _print_table(
                    ["Event", "Message", "Read"],
                    [[n.get("event", "?"), n.get("message", "?"), "✓" if n.get("read") else "—"]
                     for n in items],
                    title=f"Notifications ({unread} unread)",
                )
        else:
            uid = data.get("id", "?")
            display_user(
                data.get("name", "?"),
                uid,
                public_key=data.get("public_key"),
                affiliation=data.get("affiliation", ""),
                expertise=data.get("expertise"),
                created_at=str(data.get("created_at", "")) if data.get("created_at") else "",
            )


def _render_notice(notice) -> None:
    """Render a notice to the console."""
    code, m = _lookup(notice.code)
    if m.text:
        text = m.text.format(**notice.params) if notice.params else m.text
        console.print(Text(text))


def render_error(error: PeerpediaError) -> None:
    """Render a ``PeerpediaError`` to the console."""
    code, m = _lookup(error.code)
    detail = m.text.format(**error.context) if hasattr(error, 'context') and error.context else str(error)
    console.print(Text(f"✗ {detail}", style="error"))
    if m.suggestion:
        console.print(Text(f"  → {m.suggestion}", style="dim"))
    if m.see_also:
        console.print(Text(f"  See also: {' · '.join(m.see_also)}", style="dim"))
