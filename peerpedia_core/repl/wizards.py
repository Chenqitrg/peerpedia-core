# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Interactive REPL wizards — guided workflows that call back into dispatch.

Each wizard receives an *execute* callback ``(cmd_str) -> bool``
instead of importing dispatch directly — this avoids a circular import.
"""

from __future__ import annotations

import shlex

from rich.prompt import Prompt

import peerpedia_core.repl.state as _st
from peerpedia_core.repl.state import console

_DEFAULT_SELF_REVIEW_SCORES = "orig=4,rigor=3,comp=4,ped=3,imp=4"


def _prompt_title() -> str | None:
    """Prompt for article title.  Returns None if cancelled."""
    try:
        title = Prompt.ask(f"  [{_st.theme.styles['accent']}]Title[/]")
    except (EOFError, KeyboardInterrupt):
        return None
    return title.strip() or None


def _prompt_content() -> str:
    """Prompt for multi-line article content.  Returns content string."""
    console.print(f"  [muted]Content (Ctrl+D or empty line to finish):[/]")
    lines = []
    try:
        while True:
            line = Prompt.ask("", default="")
            if line == "":
                break
            lines.append(line)
    except (EOFError, KeyboardInterrupt):
        pass
    return "\n".join(lines)


def _meta_write(execute) -> bool:
    """Guided article creation wizard. Returns True to continue REPL."""
    console.print(f"[bold {_st.theme.styles['info']}]▔▔▔ New Article ▔▔▔[/]")

    title = _prompt_title()
    if not title:
        console.print("[muted]Cancelled — empty title.[/]")
        return True

    content = _prompt_content()
    if not content:
        console.print("[muted]Created with empty content.[/]")

    cmd = f"article create --title {shlex.quote(title)} --content {shlex.quote(content)}"
    console.print(f"  [dim]{cmd[:80]}...[/]")
    execute(cmd)

    # Offer to publish
    if _st._repl_article_id:
        try:
            pub = Prompt.ask(
                f"  [{_st.theme.styles['accent']}]Publish now?[/] [muted][y/N][/]",
                default="n"
            )
            if pub.lower() in ("y", "yes"):
                return execute(
                    f'article publish {_st._repl_article_id} --scores "{_DEFAULT_SELF_REVIEW_SCORES}"'
                )
        except (EOFError, KeyboardInterrupt):
            pass

    return True
