# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""User profile page — Phase 4 will implement fully."""

from __future__ import annotations

from prompt_toolkit.layout import HSplit, Layout, Window
from prompt_toolkit.layout.controls import FormattedTextControl

from peerpedia_core.repl.pages import Page


class UserProfilePage(Page):
    """Stub — Phase 4 will render user info + articles + followers."""

    title = "User Profile"

    def __init__(self, user_id: str):
        super().__init__()
        self._user_id = user_id

    def render_layout(self) -> Layout:
        msg = FormattedTextControl([
            ("class:prompt", f"User: {self._user_id}\n"),
            ("class:muted", "(full profile coming in Phase 4)\n"),
        ])
        return Layout(HSplit([Window(msg)]))
