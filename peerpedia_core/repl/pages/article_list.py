# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Article list page — vertical article panel list with focus and filter."""

from __future__ import annotations

from prompt_toolkit.layout import HSplit, Layout, Window
from prompt_toolkit.layout.controls import FormattedTextControl

from peerpedia_core.presentation.rich.components import (
    article_meta_panel,
    focused_panel,
)
from peerpedia_core.repl.pages import Page
from peerpedia_core.repl.state import console


class ArticleListPage(Page):
    """Vertical list of article meta panels."""

    title = "Articles"

    def __init__(self, articles: list[dict]):
        super().__init__()
        self.items = articles

    def render_layout(self) -> Layout:
        return Layout(HSplit([Window(FormattedTextControl(self._render))]))

    def _render(self):
        """Build Rich-markup fragments for the article list."""
        fragments: list[tuple[str, str]] = [
            ("class:prompt", f"  {self.title} ({len(self.filtered())} of {len(self._items)})\n\n"),
        ]

        for i, a in enumerate(self.filtered()):
            is_focused = (i == self.focus_index)
            prefix = "▌" if is_focused else " "
            style = "class:prompt" if is_focused else ""

            # Title line with focus indicator
            title = a.get("title", a.get("id", "?"))
            status = a.get("status", "draft")
            fragments.append((style, f"{prefix} {title}  "))
            fragments.append(("class:muted", f"[{status}]\n"))

            # Authors line
            authors = a.get("authors", [])
            if authors:
                names = ", ".join(authors if isinstance(authors, list) else [str(authors)])
                fragments.append(("class:muted", f"   by {names}\n"))

            # Abstract preview
            abstract = a.get("abstract", "")
            if abstract:
                preview = abstract[:120] + ("…" if len(abstract) > 120 else "")
                fragments.append(("", f"   {preview}\n"))

            fragments.append(("", "\n"))

        if not self.filtered():
            fragments.append(("class:muted", "  (no matching articles)\n"))

        # Status bar
        item = self.focused_item()
        hint = ""
        if item:
            aid = item.get("id", "?")
            hint = f"▸ {aid}  │  Enter:view  Esc:back"
        fragments.append(("class:status-bar", f"\n  {hint}"))

        return fragments
