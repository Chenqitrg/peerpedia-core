# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Placeholder page — used to verify the page stack works."""

from __future__ import annotations

from prompt_toolkit.layout import HSplit, Window
from prompt_toolkit.layout.controls import FormattedTextControl

from peerpedia_core.repl.pages import Page


class PlaceholderPage(Page):
    """A page that displays a static greeting — stack verification only."""

    title = "Hello"

    def render_layout(self):
        from prompt_toolkit.layout import Layout

        msg = FormattedTextControl([
            ("class:prompt", "Hello, REPL!\n\n"),
            ("", "Press Esc to go back.\n"),
        ])
        return Layout(HSplit([Window(msg)]))
