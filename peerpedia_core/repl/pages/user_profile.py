# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""User profile page — user info + articles + followers/following."""

from __future__ import annotations

from prompt_toolkit.layout import HSplit, Layout, Window
from prompt_toolkit.layout.controls import FormattedTextControl

from peerpedia_core.app.commandspec import spec_for_cmd_id
from peerpedia_core.app.context import build_context
from peerpedia_core.repl.pages import Page
from peerpedia_core.repl.state import new_session


class UserProfilePage(Page):
    """User metadata panel + article list + expandable followers/following."""

    title = "User Profile"

    def __init__(self, user_id: str, *, name: str = "",
                 articles: list[dict] | None = None,
                 followers: list[dict] | None = None,
                 following: list[dict] | None = None):
        super().__init__()
        self._user_id = user_id
        self._name = name or user_id
        self._articles = articles or []
        self._followers = followers or []
        self._following = following or []
        self._show_followers = False
        self._show_following = False
        # Build combined items list for focus navigation
        self.items = (
            [{"type": "header", "name": name, "id": user_id}] +
            [{"type": "article", **a} for a in self._articles] +
            [{"type": "section", "label": f"Followers ({len(self._followers)})"}] +
            ([{"type": "user", **f} for f in self._followers] if self._show_followers else [{"type": "toggle", "label": "  [Enter to show followers]"}] if self._followers else []) +
            [{"type": "section", "label": f"Following ({len(self._following)})"}] +
            ([{"type": "user", **f} for f in self._following] if self._show_following else [{"type": "toggle", "label": "  [Enter to show following]"}] if self._following else [])
        )

    def render_layout(self) -> Layout:
        return Layout(HSplit([Window(FormattedTextControl(self._render))]))

    def handle_key(self, key: str) -> Page | None:
        item = self.focused_item()
        if item is None:
            return None
        if key == "enter":
            itype = item.get("type", "")
            if itype == "article":
                from peerpedia_core.repl.pages.review_list import ReviewListPage
                return ReviewListPage(
                    reviews=_fetch_reviews(item["id"]),
                    article_id=item["id"],
                )
            if itype == "user":
                return UserProfilePage(user_id=item.get("id", ""), name=item.get("name", ""))
            if itype == "toggle":
                if "followers" in item.get("label", ""):
                    self._show_followers = True
                else:
                    self._show_following = True
                self.__init__(self._user_id, name=self._name,
                             articles=self._articles,
                             followers=self._followers,
                             following=self._following)
        return None

    def _render(self):
        fragments: list[tuple[str, str]] = []
        fragments.append(("class:prompt", f"  {self._name}\n"))
        fragments.append(("class:muted", f"  {self._user_id}\n\n"))

        for i, item in enumerate(self.items):
            is_focused = (i == self.focus_index)
            prefix = "▌" if is_focused else " "
            style = "class:prompt" if is_focused else ""
            itype = item.get("type", "")

            if itype == "header":
                fragments.append((style, f"{prefix} [{self._name}] \n\n"))
            elif itype == "section":
                fragments.append(("class:muted", f"  {item.get('label', '')}\n"))
            elif itype == "article":
                fragments.append((style, f"{prefix} {item.get('title', item.get('id', '?'))}"))
                fragments.append(("class:muted", f" [{item.get('status', '?')}]\n"))
            elif itype == "user":
                fragments.append((style, f"{prefix} @{item.get('name', item.get('id', '?'))}\n"))
            elif itype == "toggle":
                fragments.append(("class:muted", f"  {item.get('label', '')}\n"))

        hint = "Enter: view  Esc: back"
        fragments.append(("class:status-bar", f"\n  {hint}"))
        return fragments


def _fetch_reviews(article_id: str) -> list[dict]:
    """Fetch reviews for an article via the app layer."""
    db = new_session()
    try:
        ctx = build_context(db)
        spec = spec_for_cmd_id("review.list")
        result = spec.handler(ctx, {"article_id": article_id})
        return result.data.get("items", []) if result.data else []
    finally:
        db.close()
