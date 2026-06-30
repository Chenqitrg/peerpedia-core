# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""School page — leaderboard of top users by followers."""

from __future__ import annotations

from prompt_toolkit.layout import HSplit, Layout, Window
from prompt_toolkit.layout.controls import FormattedTextControl

from peerpedia_core.repl.pages import Page
from peerpedia_core.repl.pages.user_profile import UserProfilePage


class SchoolPage(Page):
    """Top users ranked by follower count."""

    title = "School"

    def __init__(self, users: list[dict]):
        super().__init__()
        self.items = users

    def render_layout(self) -> Layout:
        return Layout(HSplit([Window(FormattedTextControl(self._render))]))

    def handle_key(self, key: str) -> Page | None:
        if key == "enter":
            item = self.focused_item()
            if item:
                return UserProfilePage(
                    user_id=item.get("id", ""),
                    name=item.get("name", ""),
                )
        return None

    def _render(self):
        fragments: list[tuple[str, str]] = [
            ("class:prompt", f"  {self.title} — Top Users\n\n"),
        ]

        for i, u in enumerate(self.filtered()):
            is_focused = (i == self.focus_index)
            prefix = "▌" if is_focused else " "
            style = "class:prompt" if is_focused else ""
            rank = i + 1

            fragments.append((style, f"{prefix} {rank:>3}. "))
            fragments.append(("", f"{u.get('name', u.get('id', '?'))}"))
            fc = u.get("follower_count", 0)
            fragments.append(("class:muted", f"  ({fc} followers)\n"))

        hint = "Enter: profile  Esc: back"
        fragments.append(("class:status-bar", f"\n  {hint}"))
        return fragments
