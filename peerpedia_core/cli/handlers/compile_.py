# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Compile command — render article to PDF/SVG/PNG/HTML."""

from __future__ import annotations

from peerpedia_core.cli.helpers import _find_article_file, _page, _open_file, _ok, _die
from peerpedia_core.cli.display import console
from peerpedia_core.compiler import compile_article


def _cmd_compile(args):
    """Compile an article to PDF/SVG/PNG/HTML.

    args: id [positional], --format [pdf|svg|png|html], --json
    """
    source = _find_article_file(args.id)

    with console.status(f"[info]Compiling...[/]", spinner="dots"):
        result = compile_article(source, args.format)

    if result.success:
        if result.output_path:
            _ok(f"Compiled → {result.output_path}")
            console.print(f"[muted]Format: {result.format}[/]")
            _open_file(result.output_path)
        if result.html_content:
            _page(result.html_content) if len(result.html_content) > 500 else console.print(result.html_content)
    else:
        _die(result.error or "Compilation failed")
