# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""History page — commit list, Enter → diff with parent."""

from __future__ import annotations

from prompt_toolkit.layout import HSplit, Layout, Window
from prompt_toolkit.layout.controls import FormattedTextControl

from peerpedia_core.repl.pages import Page


class HistoryPage(Page):
    """Commit history as panel list."""

    title = "History"

    def __init__(self, commits: list[dict]):
        super().__init__()
        self.items = commits

    def render_layout(self) -> Layout:
        return Layout(HSplit([Window(FormattedTextControl(self._render))]))

    def handle_key(self, key: str) -> Page | None:
        if key == "enter":
            item = self.focused_item()
            if item:
                return DiffPage(commit=item)
        return None

    def _render(self):
        fragments: list[tuple[str, str]] = [
            ("class:prompt", "  Commit History\n\n"),
        ]

        for i, c in enumerate(self.filtered()):
            is_focused = (i == self.focus_index)
            prefix = "▌" if is_focused else " "
            style = "class:prompt" if is_focused else ""

            msg = c.get("message", "")[:60]
            h = c.get("hash", "")[:8]
            author = c.get("author", "?")
            ts = c.get("timestamp", "")

            fragments.append((style, f"{prefix} {h}  {msg}\n"))
            fragments.append(("class:muted", f"   {author}  {ts}\n\n"))

        hint = "Enter: diff with parent  Esc: back"
        fragments.append(("class:status-bar", f"\n  {hint}"))
        return fragments


class DiffPage(Page):
    """Diff view between two commits."""

    title = "Diff"

    def __init__(self, commit: dict):
        super().__init__()
        self._commit = commit

    def render_layout(self) -> Layout:
        msg = FormattedTextControl([
            ("class:prompt", f"  {self._commit.get('message', '?')}\n"),
            ("class:muted", f"  {self._commit.get('hash', '?')}\n\n"),
            ("", self._commit.get("diff", "No diff available.") + "\n"),
        ])
        return Layout(HSplit([Window(msg)]))
