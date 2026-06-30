# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Thread view page — review conversation with connector bars."""

from __future__ import annotations

from prompt_toolkit.layout import HSplit, Layout, Window
from prompt_toolkit.layout.controls import FormattedTextControl

from peerpedia_core.repl.pages import Page


class ThreadViewPage(Page):
    """Messages connected by left vertical bar.  Enter → compile message."""

    title = "Thread"

    def __init__(self, *, thread_id: str, article_id: str, messages: list[str]):
        super().__init__()
        self._thread_id = thread_id
        self._article_id = article_id
        self._messages = messages
        self.items = [{"content": m} for m in messages] if messages else []

    def render_layout(self) -> Layout:
        return Layout(HSplit([Window(FormattedTextControl(self._render))]))

    def handle_key(self, key: str) -> Page | None:
        if key == "enter":
            item = self.focused_item()
            if item:
                _open_compiled(item.get("content", ""))
        return None

    def _render(self):
        fragments: list[tuple[str, str]] = [
            ("class:prompt", f"  Thread — {self._thread_id}\n\n"),
        ]

        for i, m in enumerate(self._messages):
            is_focused = (i == self.focus_index)
            prefix = "▌" if is_focused else "│"
            style = "class:prompt" if is_focused else "class:muted"

            # Connector bar
            connector = "├─" if i < len(self._messages) - 1 else "└─"
            fragments.append((style, f" {prefix}  {connector} "))

            # Message content (truncated)
            content = str(m)[:200]
            fragments.append(("", f"{content}\n"))
            fragments.append(("", "\n"))

        hint = "Enter: compile  Esc: back"
        fragments.append(("class:status-bar", f"\n  {hint}"))
        return fragments


def _open_compiled(content: str) -> None:
    """Compile markdown content to HTML and open in browser."""
    import tempfile
    import webbrowser

    html = f"<!DOCTYPE html><html><body><pre>{content}</pre></body></html>"
    with tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w") as f:
        f.write(html)
        webbrowser.open(f"file://{f.name}")
