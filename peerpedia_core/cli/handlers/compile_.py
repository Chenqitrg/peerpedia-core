# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Compile command — render article to PDF/SVG/PNG/HTML."""

from __future__ import annotations

from peerpedia_core.cli.display import console
from peerpedia_core.cli.handler import with_context
from peerpedia_core.cli.output import _ok, _open_file, _out, _page
from peerpedia_core.compiler import compile_article
import peerpedia_core.app.commands.article as _article


@with_context
def _cmd_compile(ctx, args):
    """Compile an article to PDF/SVG/PNG/HTML."""
    source_result = _article.get_source_path(ctx, article_ref=args.id)
    source_path = source_result.data.get("path", "")
    if not source_path:
        _out(args, "SOURCE_NOT_FOUND", article_id=args.id)
    from pathlib import Path
    with console.status("[info]Compiling...[/]", spinner="dots"):
        result = compile_article(Path(source_path), args.format)

    if not result.success:
        _out(args, "COMPILE_FAILED", error=result.error or "Compilation failed")

    if result.output_path:
        _ok(f"Compiled to [accent]{result.format.upper()}[/]")
        console.print(f"  [dim]{result.output_path}[/]")
        _open_file(str(result.output_path))
    if result.html_content:
        _page(result.html_content) if len(result.html_content) > 500 else console.print(result.html_content)
