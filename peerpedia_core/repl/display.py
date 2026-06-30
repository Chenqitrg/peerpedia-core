# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""REPL display helpers — pure rendering, no print side effects.

All rendering functions return data (``Renderable``, ``Text``, ``list``).
The caller (``engine.execute``) is responsible for printing via
``console.print()`` — this is the parse→execute→format→print pipeline.
"""

from __future__ import annotations

from rich.table import Table
from rich.text import Text

from peerpedia_core.app.result import AppResult
from peerpedia_core.exceptions import PeerpediaError
from peerpedia_core.messages import lookup as _lookup
from peerpedia_core.presentation.rich.components import (
    data_table,
    error_lines,
    notification_table as _notification_table,
    score_lines as _shared_score_lines,
    user_line_text,
)
from peerpedia_core.repl.state import console

# ── Thin wrappers ─────────────────────────────────────────────────────────────


def _score_lines(score: dict | None, dims: list[str] | None = None) -> list[str]:
    return _shared_score_lines(score, dims)


# ── Format: data → renderables (no print) ────────────────────────────────────


def _format_result_data(data: dict | list) -> list[Table | Text]:
    """Format AppResult data payload into Rich renderables."""
    result: list[Table | Text] = []

    if isinstance(data, list) and data and isinstance(data[0], dict):
        result.append(data_table(
            list(data[0].keys()),
            [list(d.values()) for d in data],
        ))
    elif isinstance(data, dict):
        items = data.get("items")
        unread = data.get("unread_count")
        if isinstance(items, list):
            if items and isinstance(items[0], dict):
                for u in items:
                    result.append(user_line_text(u))
            elif unread is not None and items:
                result.append(_notification_table(
                    items, title=f"Notifications ({unread} unread)",
                ))
        else:
            result.append(user_line_text(data))
    return result


def format_result(result: AppResult) -> list[Text | Table]:
    """Format an AppResult into renderables.  Does NOT print."""
    renderables: list[Text | Table] = []

    for notice in result.notices:
        code, m = _lookup(notice.code)
        if m.text:
            text = m.text.format(**notice.params) if notice.params else m.text
            renderables.append(Text(text))

    code, m = _lookup(result.code)
    if m.kind.name in ("SUCCESS", "INFO") and m.text:
        msg = m.text.format(**result.params) if result.params else m.text
        renderables.append(Text("✓ " + msg))
    elif result.data:
        renderables.extend(_format_result_data(result.data))

    return renderables


def format_error(error: PeerpediaError) -> list[Text]:
    """Format a PeerpediaError into renderables.  Does NOT print."""
    code, m = _lookup(error.code)
    detail = (m.text.format(**error.context)
              if hasattr(error, 'context') and error.context
              else str(error))
    return [Text(line) for line in error_lines(
        detail, suggestion=m.suggestion or "",
        see_also=m.see_also or (),
    )]


# ── Print: renderables → console (the I/O step) ──────────────────────────────


def print_result(renderables: list[Text | Table]) -> None:
    """Print formatted renderables to the REPL console."""
    for r in renderables:
        console.print(r)


# ── Legacy compatibility (thin wrappers that print) ──────────────────────────


def render_result(result: AppResult) -> None:
    """Render and print an AppResult.  Legacy wrapper around format+print."""
    print_result(format_result(result))


def render_error(error: PeerpediaError) -> None:
    """Render and print a PeerpediaError.  Legacy wrapper around format+print."""
    print_result(format_error(error))
