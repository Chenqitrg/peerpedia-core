# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""REPL page stack — interactive page-based navigation.

Each ``Page`` is a full-screen prompt_toolkit layout.  Pages are pushed
onto a stack; ``Esc`` pops back to the previous page.
"""

from __future__ import annotations

from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import Layout

from peerpedia_core.repl.state import console


class Page:
    """One page in the navigation stack.

    Subclasses override ``render_layout`` to build their prompt_toolkit
    ``Layout``, and ``handle_key`` for Enter/Esc/↑↓/Tab logic.
    """

    title: str = ""

    def __init__(self):
        self.focus_index: int = 0
        self.filter_query: str = ""
        self._items: list[dict] = []

    # ── Items (data from AppResult) ────────────────────────────────────────

    @property
    def items(self) -> list[dict]:
        return self._items

    @items.setter
    def items(self, value: list[dict]) -> None:
        self._items = value

    def filtered(self) -> list[dict]:
        """Items matching ``filter_query`` (case-insensitive substring)."""
        if not self.filter_query:
            return self._items
        q = self.filter_query.lower()
        return [it for it in self._items if _item_matches(it, q)]

    # ── Override points ────────────────────────────────────────────────────

    def render_layout(self) -> Layout:
        """Build the prompt_toolkit ``Layout`` for this page."""
        raise NotImplementedError

    def handle_key(self, key: str) -> Page | None:
        """Handle a key press.  Return a new Page to push, or None."""
        return None

    # ── Helpers ────────────────────────────────────────────────────────────

    def move_focus(self, delta: int) -> None:
        items = self.filtered()
        if items:
            self.focus_index = (self.focus_index + delta) % len(items)

    def focused_item(self) -> dict | None:
        items = self.filtered()
        if not items:
            return None
        if self.focus_index >= len(items):
            self.focus_index = 0
        return items[self.focus_index]


# ── Filter helper ────────────────────────────────────────────────────────────


def _item_matches(item: dict, query: str) -> bool:
    """Return True if *query* appears in any string value of *item*."""
    for v in item.values():
        if isinstance(v, str) and query in v.lower():
            return True
        if isinstance(v, list):
            for sv in v:
                if isinstance(sv, str) and query in sv.lower():
                    return True
    return False
