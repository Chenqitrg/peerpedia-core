# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Review list page — review panels with Tab sub-focus."""

from __future__ import annotations

from prompt_toolkit.layout import HSplit, Layout, Window
from prompt_toolkit.layout.controls import FormattedTextControl

from peerpedia_core.repl.pages import Page
from peerpedia_core.repl.pages.thread_view import ThreadViewPage
from peerpedia_core.repl.pages.user_profile import UserProfilePage


_REVIEW_PREVIEW_CHARS = 400


class ReviewListPage(Page):
    """Vertical list of review panels.  Tab toggles body ↔ reviewer name."""

    title = "Reviews"
    _SUB_FOCUS_BODY = "body"
    _SUB_FOCUS_REVIEWER = "reviewer"

    def __init__(self, reviews: list[dict], article_id: str):
        super().__init__()
        self.items = reviews
        self._article_id = article_id
        self._sub_focus: str = self._SUB_FOCUS_BODY

    def render_layout(self) -> Layout:
        return Layout(HSplit([Window(FormattedTextControl(self._render))]))

    def handle_key(self, key: str) -> Page | None:
        if key == "enter":
            item = self.focused_item()
            if item is None:
                return None
            if self._sub_focus == self._SUB_FOCUS_BODY:
                return ThreadViewPage(
                    thread_id=item.get("reviewer_id", "?"),
                    article_id=self._article_id,
                    messages=item.get("thread", []),
                )
            else:
                return UserProfilePage(user_id=item.get("reviewer_id", "?"))
        if key == "tab":
            self._sub_focus = (
                self._SUB_FOCUS_REVIEWER if self._sub_focus == self._SUB_FOCUS_BODY
                else self._SUB_FOCUS_BODY
            )
        return None

    def _render(self):
        fragments: list[tuple[str, str]] = [
            ("class:prompt", f"  {self.title} ({len(self.filtered())})\n\n"),
        ]

        for i, r in enumerate(self.filtered()):
            is_focused = (i == self.focus_index)
            prefix = "▌" if is_focused else " "
            style = "class:prompt" if is_focused else ""

            # Score stars
            scores = r.get("scores", {})
            if scores and isinstance(scores, dict):
                stars = _stars(scores)
                fragments.append((style, f"{prefix} {stars}  "))
            else:
                fragments.append((style, f"{prefix} —  "))

            # Reviewer name (underline when sub-focused)
            name = r.get("reviewer_name", r.get("reviewer_id", "?"))
            name_focused = is_focused and self._sub_focus == self._SUB_FOCUS_REVIEWER
            if name_focused:
                fragments.append(("class:prompt", f"_{name}_"))
            else:
                fragments.append(("", name))

            fragments.append(("", "\n"))

            # Thread preview
            thread = r.get("thread", [])
            if thread and isinstance(thread, list) and thread[0]:
                preview = str(thread[0])[:_REVIEW_PREVIEW_CHARS]
                fragments.append(("class:muted", f"   {preview}\n"))

            fragments.append(("", "\n"))

        # Status bar
        item = self.focused_item()
        hint = ""
        if item:
            if self._sub_focus == self._SUB_FOCUS_BODY:
                hint = "Enter: thread  Tab: reviewer  Esc: back"
            else:
                hint = "Enter: user profile  Tab: body  Esc: back"
        fragments.append(("class:status-bar", f"\n  {hint}"))
        return fragments


def _stars(scores: dict) -> str:
    """Convert score dict to simple star string."""
    if not scores:
        return "—"
    avg = sum(scores.values()) / len(scores)
    filled = int(avg)
    return "★" * filled + "☆" * (5 - filled)
