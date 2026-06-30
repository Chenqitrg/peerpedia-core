# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

# TODO(peerpedia-markup): full CommonMark compatibility + MyST-style semantic
# extensions.  A custom markup language (indentation-based, no closing
# delimiters) is architecturally cleaner but not viable until AI models
# support it — every LLM is trained on CommonMark.  Strategy:
#   - Syntax: strict CommonMark superset (every standard .md file parses)
#   - Semantics: MyST-style directives (:::{theorem}, :::{figure}) on top
#   - Extensions: @key citations, ```lean blocks, {prf:*} environments
#   - Revisit custom syntax only when Markdown's limitations become a real
#     bottleneck, not an aesthetic preference.

r"""Compiler backends for Typst, Markdown, and bTeX.

Converts article source files into rendered output (HTML, PDF, SVG, PNG).
The backend is selected based on the article's format field.

TODO(markdown-formatter): auto-format Markdown on commit/publish to unify
redundant syntax variants into one canonical style — PeerPedia's equivalent
of ``black`` / ``prettier``.  Normalisation rules:

  Inline emphasis:     *italic* and _italic_       → _italic_
  Inline strong:       **bold** and __bold__        → **bold**
  Unordered lists:     *, -, +                      → -
  Headings (setext):   heading\n=======              → # heading
  Links (reference):   [text][ref] → [text](url)     → whichever is canonical
  Thematic breaks:     ***, ---, ___                 → ---

Runs automatically: git pre-commit hook → formatter → commit.  Authors never
see inconsistent formatting and never need to think about which style they
used.  The canonical style is enforced in git history — a reviewer verifying
the commit sees the formatted version.

TODO(code-block-pipeline): fenced code blocks are the universal extension
point.  The info string (first word after ```) routes to a handler — no new
Markdown syntax needed.  TypstBackend already exists and compiles .typ →
SVG/PNG; the compiler just needs to extract code blocks and route them:

  ```typst          → TypstBackend → SVG     (figures, diagrams, plots)
  ```typst_figure   → TypstBackend → SVG     (same, with caption support)
  ```cd             → TypstBackend → SVG     (commutative diagrams)
  ```lean           → lean --run    → pass/fail badge  (theorem verification)
  ```mermaid        → mermaid.js    → SVG     (flowcharts, if wanted)

All these share one pattern:
  1. Parser extracts fenced block by info string
  2. Route to handler (Typst subprocess, LEAN subprocess, JS runtime)
  3. Embed rendered output (SVG/HTML) in compiled page

Typst is the universal diagram AND math backend — TeX-quality math ($...$),
commutative diagrams, plots, trees, circuits, chemical structures — all
expressible in Typst's scripting language.  Even inline math can route
through Typst instead of KaTeX for consistency.  Zero new deps.

Architecture:  Markdown → structure (headings, paragraphs, lists, citations)
               Typst    → rendering (math, diagrams, figures, code blocks)

TODO(citation-compile): resolve @key citation markers in Markdown/Typst
source and render a references list.  Currently citation markers pass through
unchanged to output.

  CitationStorage syntax uses bare @key — no brackets:
    @wiles1995 showed that ...          →  "Wiles (1995) showed that ..."
    ... as demonstrated previously @wiles1995, @smith2020  →  "... as
    demonstrated previously [1, 3]."

  @ prefix is the delimiter — no closing bracket needed.  Disambiguation:
  email addresses (name@domain.com) contain a dot after @; citation keys
  (@key) are alphanumeric immediately after @.  The parser splits on this.

  Same philosophy as Python's indentation: a visual convention (@ = citation)
  becomes actual syntax.  Brackets are noise for both humans and AI models
  that already output @key naturally.

TODO(multi-file-articles): support articles composed of multiple source files
(e.g. chapter1.md, chapter2.md, figures/, data/).  Currently _find_article_file
hardcodes article.md or article.typ as the sole source file.

TODO(lean-blocks): support ```lean fenced code blocks alongside the article
text.  Not formalising the entire paper — just the key theorems.  Each
natural-language claim can optionally carry a LEAN proof block:

  **Theorem 1.** The scoring function is bounded on [1, 5].
  ```lean
  theorem score_bounded (s : Score) : 1 ≤ s.total ∧ s.total ≤ 5 := by
    ...
  ```

The compiler runs LEAN on these blocks during ``peerpedia compile`` and
reports pass/fail per block.  Reviewers don't need to manually check the
math — they verify the LEAN proof compiles.  A paper where every formal
claim carries a verified proof block gets a ``lean-verified`` badge.

This turns peer review from "trust the author's reasoning" to "verify the
author's proof."  The paper still reads as natural language — the LEAN
blocks are optional annotations for rigor.

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

from peerpedia_core.exceptions import BadRequestError

from peerpedia_core.config.params import (
    _ARTICLE_EXT_TO_FMT,
    FMT_HTML, FMT_MARKDOWN, FMT_PDF, FMT_PNG, FMT_SVG, FMT_TYPST,
    MD_ARITHMATEX_KEY, MD_EXTENSIONS, MD_OUTPUT_DIR,
    TYPST_BIN, TYPST_COMPILE_CMD, TYPST_FORMAT_FLAG,
    TYPST_TIMEOUT, TYPST_VALID_FMTS, TYPST_WARNING_PREFIX,
)
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
    error_code: str | None = None   # Machine-readable code (see messages.py)
    warnings: list[str] = field(default_factory=list)


# ── Format detection ───────────────────────────────────────────────────────────


def compile_article(source_path: Path, fmt: str | None = None) -> CompileResult:
    """Compile an article source file to the requested format.

    *fmt*: output format (pdf, svg, png, html).  Defaults to pdf for Typst,
    html for Markdown.
    """
    actual_format = detect_format(source_path)

    # Markdown backend only supports HTML output.  Validate upfront so the
    # user gets a clear error instead of silent HTML output.
    if actual_format == FMT_MARKDOWN and fmt and fmt != FMT_HTML:
        return CompileResult(
            success=False, format=fmt,
            error_code="COMPILE_FORMAT_MISMATCH",
        )

    detected = fmt or actual_format
    out_dir = source_path.parent / MD_OUTPUT_DIR
    out_dir.mkdir(exist_ok=True)

    if detected == FMT_TYPST:
        return TypstBackend().compile(source_path, out_dir, fmt=fmt or FMT_PDF)
    else:
        return MarkdownBackend().compile(source_path, out_dir)


def detect_format(file_path: Path) -> str:
    """Detect article format from file extension. Returns "markdown" or "typst".

    Raises BadRequestError if the file extension is not recognised.
    """
    suffix = file_path.suffix.lower()
    fmt = _ARTICLE_EXT_TO_FMT.get(suffix)
    if fmt is not None:
        return fmt
    raise BadRequestError(code="COMPILE_UNKNOWN_FORMAT", suffix=suffix)


def _output_path(source_path: Path, output_dir: Path, ext: str) -> Path:
    """Build output file path: ``output_dir / stem.ext``."""
    return output_dir / f"{source_path.stem}.{ext}"


def _typst_format_label(fmt: str) -> str:
    """Build Typst result format label: ``typst-pdf``, ``typst-svg``, etc."""
    return f"typst-{fmt}"


# ── Typst backend ──────────────────────────────────────────────────────────────


class TypstBackend:
    """Compile Typst source via subprocess `typst compile`."""

    def compile(self, source_path: Path, output_dir: Path, fmt: str = FMT_PDF) -> CompileResult:
        """Run ``typst compile --format <fmt> <source> <output>``."""
        typst_bin = shutil.which(TYPST_BIN)
        if typst_bin is None:
            return CompileResult(success=False, format=FMT_TYPST, error_code="COMPILE_TYPST_NOT_FOUND")

        fmt = fmt if fmt in TYPST_VALID_FMTS else FMT_PDF
        output_file = _output_path(source_path, output_dir, fmt)
        try:
            result = subprocess.run(
                [typst_bin, TYPST_COMPILE_CMD, TYPST_FORMAT_FLAG, fmt,
                 str(source_path), str(output_file)],
                capture_output=True, text=True, timeout=TYPST_TIMEOUT,
            )
        except subprocess.TimeoutExpired:
            return CompileResult(success=False, format=FMT_TYPST, error_code="COMPILE_TIMEOUT")

        if result.returncode != 0:
            return CompileResult(success=False, format=FMT_TYPST,
                                error=result.stderr.strip(),
                                error_code="COMPILE_TYPST_ERROR")

        return CompileResult(
            success=True,
            format=_typst_format_label(fmt),
            output_path=str(output_file),
            html_content=output_file.read_text() if fmt == FMT_SVG else None,
            warnings=_parse_typst_warnings(result.stderr),
        )


def _parse_typst_warnings(stderr: str) -> list[str]:
    """Parse warning lines from typst stderr output."""
    return [
        line.strip()
        for line in stderr.splitlines()
        if line.strip().startswith(TYPST_WARNING_PREFIX)
    ]


# ── Markdown backend ───────────────────────────────────────────────────────────


class MarkdownBackend:
    """Compile Markdown to HTML with KaTeX math rendering."""

    def compile(self, source_path: Path, output_dir: Path) -> CompileResult:
        """Compile Markdown to HTML with KaTeX math support."""
        try:
            source = source_path.read_text()
        except Exception as e:
            return CompileResult(success=False, format=FMT_MARKDOWN, error=str(e))

        try:
            body = strip_frontmatter(source)
            html_body = _render_markdown(body)

            output_path = _output_path(source_path, output_dir, FMT_HTML)
            output_path.write_text(html_body)

            return CompileResult(
                success=True,
                format=FMT_MARKDOWN,
                output_path=str(output_path),
                html_content=html_body,
            )
        except Exception as e:
            return CompileResult(success=False, format=FMT_MARKDOWN, error=str(e))


def _render_markdown(md_text: str) -> str:
    """Render Markdown to HTML with math protection via pymdown-extensions."""
    import markdown

    return markdown.markdown(
        md_text,
        extensions=list(MD_EXTENSIONS),
        extension_configs={
            MD_ARITHMATEX_KEY: {"generic": True},
        },
    )
