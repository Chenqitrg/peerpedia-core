# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Interactive REPL wizards — guided workflows that call back into dispatch.

Each wizard receives a *dispatch_fn* callback instead of importing
``_dispatch`` directly — this avoids a circular import since
``dispatch.py`` imports from this module.
"""

from __future__ import annotations

import shlex

from rich.prompt import Prompt

import peerpedia_core.repl.state as _st
from peerpedia_core.repl.state import console


def _meta_write(dispatch_fn, parser) -> bool:
    """Guided article creation wizard. Returns True to continue REPL."""
    console.print(f"[bold {_st.theme.styles['info']}]▔▔▔ New ArticleMetaStorage ▔▔▔[/]")
    try:
        title = Prompt.ask(f"  [{_st.theme.styles['accent']}]Title[/]")
    except (EOFError, KeyboardInterrupt):
        console.print("[muted]Cancelled.[/]")
        return True

    if not title.strip():
        console.print("[muted]Cancelled — empty title.[/]")
        return True

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

    content = "\n".join(lines) if lines else ""
    if not content:
        console.print("[muted]Created with empty content.[/]")

    # Build and dispatch — use shlex.quote for safe shell embedding.
    cmd = f"create --title {shlex.quote(title)} --content {shlex.quote(content)}"
    console.print(f"  [dim]{cmd[:80]}...[/]")
    result = dispatch_fn(cmd, parser)

    # Offer to publish
    if result and _st._repl_article_id:
        try:
            pub = Prompt.ask(
                f"  [{_st.theme.styles['accent']}]Publish now?[/] [muted][y/N][/]",
                default="n"
            )
            if pub.lower() in ("y", "yes"):
                return dispatch_fn(
                    f'publish {_st._repl_article_id} --scores "orig=4,rig=3,comp=4,ped=3,imp=4"',
                    parser
                )
        except (EOFError, KeyboardInterrupt):
            pass

    return True
