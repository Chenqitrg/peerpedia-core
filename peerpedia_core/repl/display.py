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

from peerpedia_core.messages import lookup as _lookup
from peerpedia_core.presentation.rich.components import (
    data_table,
    notification_table as _notification_table,
    score_lines as _shared_score_lines,
    user_line_text,
)

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


# format_result, format_error, print_result, render_result, render_error
# removed in Phase 0 — replaced by page-based rendering in repl/pages/.
