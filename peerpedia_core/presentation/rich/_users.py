# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""User display — panels, table, line text."""

from __future__ import annotations

from rich.console import Console
from rich.table import Table
from rich.text import Text

from peerpedia_core.presentation.rich._common import print_panel
from peerpedia_core.presentation.rich._scores import score_stars
from peerpedia_core.types.entities import UserExchange

_USER_TABLE_RANK_W = 3
_USER_TABLE_ID_W = 10


def display_user(console: Console, user: UserExchange) -> None:
    """Render a UserExchange as a Rich panel."""
    body = Text()
    body.append(str(user.name), style="bold info")
    body.append(f"\n{user.id}", style="accent")
    if user.address:
        body.append("\nAffiliation: ")
        body.append(str(user.address), style="info")
    if user.reputation:
        body.append("\nReputation:\n")
        body.append(Text.from_markup(score_stars(user.reputation)))
    print_panel(console, "User", body)


def user_panels(console: Console, items: list[UserExchange]) -> None:
    """Render a list of UserExchange objects as Rich panels."""
    for u in items:
        display_user(console, u)


def user_line_text(user: UserExchange) -> Text:
    """Build a single-line Rich Text renderable from a UserExchange."""
    affiliation = f" · {user.address}" if user.address else ""
    return Text(f"{user.name} ({user.id}){affiliation}")


def user_list_table(users, *, title: str = "") -> Table:
    """Build a user picker table: #, ID, Affiliation."""
    t = Table(title=title, border_style="muted")
    t.add_column("#", style="muted", width=_USER_TABLE_RANK_W)
    t.add_column("ID", style="accent", width=_USER_TABLE_ID_W)
    t.add_column("Affiliation", style="muted")
    for i, u in enumerate(users, 1):
        t.add_row(str(i), u.id, u.affiliation or "—")
    return t
