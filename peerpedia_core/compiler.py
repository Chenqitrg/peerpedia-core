# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

r"""Compiler backends for Typst, Markdown, and bTeX.

Converts article source files into rendered output (HTML, PDF, SVG, PNG).
The backend is selected based on the article's format field.

Architecture
------------
::

    CLI: peerpedia compile <id> [--format pdf|svg|png|html]
      |
      v
    compiler.detect_format(article_path) -> "typst" | "markdown"
      |
      v
    TypstBackend or MarkdownBackend
      |
      v
    CompileResult(html, pdf_path, pages, warnings)

Backends are pluggable -- new formats can be added by subclassing
``CompilerBackend`` without touching the core protocol.

.. todo:: LeanBackend

    Extract ``\`\`\`lean`` blocks from Markdown articles, feed to ``lean --check``
    as a subprocess.  Mathlib 4 provides the standard library — articles
    can import theorems from Reservoir.  Peer-review workflow: reviewer runs
    ``peerpedia verify <id>`` → Lean verifies all proof blocks → updates
    credibility score.

    No new article format needed — ``.md`` with ``lean`` fenced code blocks
    is enough.  Requires Lean toolchain detection (like TypstBackend).

Classes and key functions
-------------------------
CompileResult           Dataclass: html, pdf_path, pages, warnings
CompilerBackend (ABC)   Abstract: compile(), extract_metadata()
TypstBackend            Calls ``typst compile`` via subprocess
MarkdownBackend         Pure Python: markdown -> HTML with math protection

Frontmatter helpers (used by commands/articles/)
--------------------------------------------------
extract_frontmatter     Parse YAML frontmatter from source text
parse_frontmatter       Same as extract, with error handling
make_frontmatter        Build frontmatter string from dict
make_article_frontmatter  Convenience: title, abstract, keywords, categories
_strip_frontmatter      Remove frontmatter, return body only

Callers
-------
- ``cli.py``: ``_cmd_compile`` -> ``detect_format`` -> backend.compile()
- ``commands/articles/``: ``create_article_with_content`` ->
  ``make_article_frontmatter``; ``update_article_content`` ->
  ``make_article_frontmatter`` + ``_strip_frontmatter``

Reviewer's checklist
--------------------
- Does each backend call ``shutil.which()`` to check the external tool is
  installed before trying to run it?
- Are subprocess calls using timeouts?
- Is math ($...$ and $$...$$) protected from Markdown parser interference?
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from peerpedia_core.frontmatter import strip_frontmatter
# ── Result types ───────────────────────────────────────────────────────────────


@dataclass
class CompileResult:
    """Result of a compilation."""

    success: bool
    format: str
    output_path: str | None = None  # Path to compiled file (PDF, HTML)
    html_content: str | None = None  # Inline HTML (for Markdown rendering)
    error: str | None = None
    warnings: list[str] = field(default_factory=list)


# ── Format detection ───────────────────────────────────────────────────────────


def compile_article(source_path: Path, fmt: str | None = None) -> CompileResult:
    """Compile an article source file to the requested format.

    *fmt*: output format (pdf, svg, png, html).  Defaults to pdf for Typst,
    html for Markdown.
    """
    detected = fmt or detect_format(source_path)
    out_dir = source_path.parent / "compiled"
    out_dir.mkdir(exist_ok=True)

    if detected == "typst":
        return TypstBackend().compile(source_path, out_dir, fmt=fmt or "pdf")
    else:
        return MarkdownBackend().compile(source_path, out_dir)


def detect_format(file_path: Path) -> str:
    """Detect article format from file extension. Returns "markdown" or "typst"."""
    suffix = file_path.suffix.lower()
    if suffix in (".typ", ".typst"):
        return "typst"
    if suffix in (".md", ".markdown"):
        return "markdown"
    raise ValueError(f"Unknown article format: {suffix}")


def _fail(format: str, error: str) -> CompileResult:
    return CompileResult(success=False, format=format, error=error)


# ── Typst backend ──────────────────────────────────────────────────────────────


class TypstBackend:
    """Compile Typst source via subprocess `typst compile`."""

    def compile(self, source_path: Path, output_dir: Path, fmt: str = "pdf") -> CompileResult:
        """Run ``typst compile --format <fmt> <source> <output>``."""
        typst_bin = shutil.which("typst")
        if typst_bin is None:
            return _fail("typst", "typst CLI not found. Install from https://github.com/typst/typst")

        fmt = fmt if fmt in ("pdf", "svg", "png") else "pdf"
        output_file = output_dir / f"{source_path.stem}.{fmt}"
        try:
            result = subprocess.run(
                [typst_bin, "compile", "--format", fmt, str(source_path), str(output_file)],
                capture_output=True, text=True, timeout=30,
            )
        except subprocess.TimeoutExpired:
            return _fail("typst", "typst compilation timed out (30s)")

        if result.returncode != 0:
            return _fail("typst", result.stderr.strip() or "Unknown typst error")

        return CompileResult(
            success=True,
            format=f"typst-{fmt}",
            output_path=str(output_file),
            html_content=output_file.read_text() if fmt == "svg" else None,
            warnings=_parse_typst_warnings(result.stderr),
        )


def _parse_typst_warnings(stderr: str) -> list[str]:
    """Parse warning lines from typst stderr output."""
    return [
        line.strip()
        for line in stderr.split("\n")
        if line.strip().startswith("warning:")
    ]


# ── Markdown backend ───────────────────────────────────────────────────────────


class MarkdownBackend:
    """Compile Markdown to HTML with KaTeX math rendering."""

    def compile(self, source_path: Path, output_dir: Path) -> CompileResult:
        """Compile Markdown to HTML with KaTeX math support."""
        try:
            source = source_path.read_text()
        except Exception as e:
            return _fail("markdown", str(e))

        try:
            body = strip_frontmatter(source)
            html_body = _render_markdown(body)
            # Math is protected by pymdownx.arithmatex.  The front-end
            # is responsible for loading KaTeX and calling renderMathInElement.

            output_path = output_dir / f"{source_path.stem}.html"
            output_path.write_text(html_body)

            return CompileResult(
                success=True,
                format="markdown",
                output_path=str(output_path),
                html_content=html_body,
            )
        except Exception as e:
            return _fail("markdown", str(e))


def _render_markdown(md_text: str) -> str:
    """Render Markdown to HTML with math protection via pymdown-extensions."""
    import markdown

    return markdown.markdown(
        md_text,
        extensions=[
            "fenced_code", "tables", "codehilite",
            "pymdownx.arithmatex",
        ],
        extension_configs={
            "pymdownx.arithmatex": {"generic": True},
        },
    )
