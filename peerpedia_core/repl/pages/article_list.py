# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Article list page — vertical article panel list with focus and filter."""

from __future__ import annotations

from prompt_toolkit.layout import HSplit, Layout, Window
from prompt_toolkit.layout.controls import FormattedTextControl

from peerpedia_core.repl.pages import Page
from peerpedia_core.repl.pages.review_list import ReviewListPage
from peerpedia_core.repl.pages.user_profile import _fetch_reviews
from peerpedia_core.types.entities import ArticleMetaExchange


class ArticleListPage(Page):
    """Vertical list of article meta panels."""

    title = "Articles"

    def __init__(self, articles: list[ArticleMetaExchange]):
        super().__init__()
        self.items = articles  # type: ignore[assignment]

    def render_layout(self) -> Layout:
        return Layout(HSplit([Window(FormattedTextControl(self._render))]))

    def handle_key(self, key: str) -> Page | None:
        if key == "enter":
            item: ArticleMetaExchange | None = self.focused_item()  # type: ignore[assignment]
            if item is None:
                return None
            reviews = _fetch_reviews(item.id)
            return ReviewListPage(reviews=reviews, article_id=item.id)
        return None

    # ── Rendering ─────────────────────────────────────────────────────────

    def _render(self):
        """Build Rich-markup fragments for the article list."""
        fragments: list[tuple[str, str]] = []
        fragments.extend(_render_header(self.title, len(self.filtered()), len(self._items)))
        if self.filtered():
            for i, a in enumerate(self.filtered()):
                fragments.extend(_render_item(a, i == self.focus_index))
        else:
            fragments.append(("class:muted", "  (no matching articles)\n"))
        fragments.extend(_render_status_bar(self.focused_item()))
        return fragments


# ── Rendering helpers ────────────────────────────────────────────────────────


def _render_header(title: str, filtered: int, total: int) -> list[tuple[str, str]]:
    """Title line with filtered/total count."""
    return [("class:prompt", f"  {title} ({filtered} of {total})\n\n")]


def _render_item(article: ArticleMetaExchange, is_focused: bool) -> list[tuple[str, str]]:
    """Render a single article panel (title, authors, abstract)."""
    prefix = "▌" if is_focused else " "
    style = "class:prompt" if is_focused else ""
    result: list[tuple[str, str]] = []
    result.extend(_render_title_line(article, prefix, style))
    result.extend(_render_authors_line(article))
    result.extend(_render_abstract_preview(article))
    result.append(("", "\n"))
    return result


def _render_title_line(article: ArticleMetaExchange, prefix: str, style: str) -> list[tuple[str, str]]:
    return [
        (style, f"{prefix} {article.title}  "),
        ("class:muted", f"[{article.status}]\n"),
    ]


def _render_authors_line(article: ArticleMetaExchange) -> list[tuple[str, str]]:
    if not article.authors:
        return []
    names = ", ".join(article.authors)
    return [("class:muted", f"   by {names}\n")]


def _render_abstract_preview(article: ArticleMetaExchange) -> list[tuple[str, str]]:
    if not article.abstract:
        return []
    preview = article.abstract[:120] + ("…" if len(article.abstract) > 120 else "")
    return [("", f"   {preview}\n")]


def _render_status_bar(item: ArticleMetaExchange | None) -> list[tuple[str, str]]:
    """Bottom hint showing focused item ID and available keys."""
    if item:
        hint = f"▸ {item.id}  │  Enter:view  Esc:back"
    else:
        hint = ""
    return [("class:status-bar", f"\n  {hint}")]
