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

Classes and key functions
-------------------------
CompileResult           Dataclass: html, pdf_path, pages, warnings
CompilerBackend (ABC)   Abstract: compile(), extract_metadata()
TypstBackend            Calls ``typst compile`` via subprocess
MarkdownBackend         Pure Python: markdown -> HTML with math protection

Frontmatter helpers (used by commands/articles.py)
--------------------------------------------------
extract_frontmatter     Parse YAML frontmatter from source text
parse_frontmatter       Same as extract, with error handling
make_frontmatter        Build frontmatter string from dict
make_article_frontmatter  Convenience: title, abstract, keywords, categories
_strip_frontmatter      Remove frontmatter, return body only

Callers
-------
- ``cli.py``: ``_cmd_compile`` -> ``detect_format`` -> backend.compile()
- ``commands/articles.py``: ``create_article_with_content`` ->
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

import re
import shutil
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# ── Result types ───────────────────────────────────────────────────────────────


@dataclass
class CompileResult:
    """Result of a compilation."""

    success: bool
    format: str
    output_path: Optional[str] = None  # Path to compiled file (PDF, HTML)
    html_content: Optional[str] = None  # Inline HTML (for Markdown rendering)
    error: Optional[str] = None
    warnings: list[str] = field(default_factory=list)


# ── Frontmatter parsing ────────────────────────────────────────────────────────


def extract_frontmatter(source: str) -> dict:
    """Extract YAML frontmatter from an article or review source.

    Delegates to ``parse_frontmatter`` — kept for backward compatibility.
    """
    return parse_frontmatter(source)


# ── Public frontmatter API (PyYAML-backed) ─────────────────────────────────


def parse_frontmatter(source: str) -> dict:
    """Parse ``---``-delimited YAML frontmatter from *source*.

    Requires the first line to be exactly ``---`` (no leading whitespace,
    no trailing content) and a matching closing ``---`` on its own line.
    Returns a dict of metadata, or an empty dict on any mismatch.
    """
    import yaml

    lines = source.split("\n")
    if not lines or lines[0].strip() != "---":
        return {}

    # Find closing --- (must be on its own line)
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return {}

    yaml_block = "\n".join(lines[1:end]).strip()
    if not yaml_block:
        return {}
    try:
        result = yaml.safe_load(yaml_block)
    except yaml.YAMLError:
        return {}

    if not isinstance(result, dict):
        return {}

    # Only known article metadata keys are allowed.
    allowed = {"title", "abstract", "keywords", "categories"}
    unknown = set(result.keys()) - allowed
    if unknown:
        return {}

    return result


def make_frontmatter(data: dict) -> str:
    """Serialize *data* to a ``---``-delimited YAML frontmatter block.

    Returns a string suitable for prepending to an article or review body.
    """
    import yaml

    yaml_str = yaml.dump(data, default_flow_style=False, allow_unicode=True, sort_keys=False)
    return f"---\n{yaml_str}---\n"


def make_article_frontmatter(
    title: str,
    abstract: str | None = None,
    keywords: list[str] | None = None,
    categories: list[str] | None = None,
) -> str:
    """Build YAML frontmatter for an article file."""
    data: dict = {"title": title}
    if abstract:
        data["abstract"] = abstract
    if keywords:
        data["keywords"] = keywords
    if categories:
        data["categories"] = categories
    return make_frontmatter(data)


# ── Format detection ───────────────────────────────────────────────────────────


def detect_format(file_path: Path) -> str:
    """Detect article format from file extension."""
    suffix = file_path.suffix.lower()
    if suffix in (".typ", ".typst"):
        return "typst"
    elif suffix in (".md", ".markdown"):
        return "markdown"
    return "typst"  # default


# ── Abstract compiler ──────────────────────────────────────────────────────────


class CompilerBackend(ABC):
    """Abstract compiler backend — versioned via PIP."""

    @abstractmethod
    def compile(self, source_path: Path, output_dir: Path) -> CompileResult:
        """Compile source to output format (PDF for Typst, HTML for Markdown)."""
        ...

    @property
    @abstractmethod
    def format_name(self) -> str:
        """Return the format name: 'typst' or 'markdown'."""
        ...


# ── Typst backend ──────────────────────────────────────────────────────────────


class TypstBackend(CompilerBackend):
    """Compile Typst source via subprocess `typst compile`."""

    format_name = "typst"

    def compile(self, source_path: Path, output_dir: Path, fmt: str = "pdf") -> CompileResult:
        """Run `typst compile --format <fmt> <source> <output>`.

        Supported formats: pdf (default), svg, png.
        SVG is recommended for browser preview; PDF for archival.
        """
        typst_bin = shutil.which("typst")
        if typst_bin is None:
            return CompileResult(
                success=False,
                format="typst",
                error="typst CLI not found. Install from https://github.com/typst/typst",
            )

        fmt = fmt if fmt in ("pdf", "svg", "png") else "pdf"
        output_file = output_dir / f"{source_path.stem}.{fmt}"
        try:
            result = subprocess.run(
                [typst_bin, "compile", "--format", fmt, str(source_path), str(output_file)],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                output_str = str(output_file)
                html_content = None
                # For SVG/PNG, embed in HTML for direct preview
                if fmt in ("svg", "png") and output_file.exists():
                    content = output_file.read_text() if fmt == "svg" else None
                    if content:
                        html_content = content  # SVG is inline HTML
                return CompileResult(
                    success=True,
                    format=f"typst-{fmt}",
                    output_path=output_str,
                    html_content=html_content,
                    warnings=_parse_typst_warnings(result.stderr),
                )
            else:
                return CompileResult(
                    success=False,
                    format="typst",
                    error=result.stderr.strip() or "Unknown typst error",
                )
        except subprocess.TimeoutExpired:
            return CompileResult(
                success=False,
                format="typst",
                error="typst compilation timed out (30s)",
            )
        except Exception as e:
            return CompileResult(
                success=False,
                format="typst",
                error=str(e),
            )


def _parse_typst_warnings(stderr: str) -> list[str]:
    """Parse warning lines from typst stderr output."""
    return [
        line.strip()
        for line in stderr.split("\n")
        if line.strip().startswith("warning:")
    ]


# ── Markdown backend ───────────────────────────────────────────────────────────


class MarkdownBackend(CompilerBackend):
    """Compile Markdown to HTML with KaTeX math rendering.

    Uses Python's markdown library for parsing. KaTeX is rendered
    client-side via CDN — the backend wraps $...$ in KaTeX-compatible
    HTML spans.
    """

    format_name = "markdown"

    def compile(self, source_path: Path, output_dir: Path) -> CompileResult:
        """Compile Markdown to HTML with KaTeX math support."""
        try:
            source = source_path.read_text()
        except Exception as e:
            return CompileResult(success=False, format="markdown", error=str(e))

        try:
            # Strip frontmatter for rendering
            body = _strip_frontmatter(source)
            # Protect math BEFORE Markdown rendering so underscores etc.
            # inside $...$ are not parsed as Markdown emphasis.
            protected_body, math_placeholders = _protect_math(body)
            html_body = _render_markdown(protected_body)
            html_body = _restore_math(html_body, math_placeholders)

            # KaTeX CSS/JS loaded in page <head>. Only body + render here.
            # Target #article-content so HTMX swaps get rendered correctly.
            full_html = f"""{html_body}
<script>
  (function() {{
    var el = document.getElementById('article-content');
    if (el && window.renderMathInElement) {{
      renderMathInElement(el, {{
        delimiters: [
          {{left: '$$', right: '$$', display: true}},
          {{left: '$', right: '$', display: false}},
        ]
      }});
    }}
  }})();
</script>"""

            output_path = output_dir / f"{source_path.stem}.html"
            output_path.write_text(full_html)

            return CompileResult(
                success=True,
                format="markdown",
                output_path=str(output_path),
                html_content=full_html,
            )
        except Exception as e:
            return CompileResult(success=False, format="markdown", error=str(e))


def _strip_frontmatter(source: str) -> str:
    """Remove YAML frontmatter from source, return body only."""
    if not source.startswith("---"):
        return source
    parts = source.split("---", 2)
    if len(parts) >= 3:
        return parts[2].strip()
    return source


def _render_markdown(md_text: str) -> str:
    """Render Markdown text to HTML.

    Uses built-in markdown parsing. Falls back to plain text with
    <br> line breaks if the markdown library is unavailable.
    """
    try:
        import markdown

        return markdown.markdown(
            md_text,
            extensions=["fenced_code", "tables", "codehilite"],
        )
    except ImportError:
        # Fallback: basic HTML wrapping
        escaped = md_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        paragraphs = escaped.split("\n\n")
        return "\n".join(f"<p>{p.replace(chr(10), '<br>')}</p>" for p in paragraphs if p.strip())


_MATH_PLACEHOLDER_PREFIX = "PEERPEDIA_MATH_"


def _protect_math(text: str) -> tuple[str, dict[str, str]]:
    """Replace math expressions with placeholders to protect them from Markdown parsing.

    $$...$$ → display math
    $...$   → inline math

    Returns (protected_text, {placeholder: original_math}).
    """
    placeholders: dict[str, str] = {}
    counter = 0

    def replace_display(m: re.Match) -> str:
        nonlocal counter
        key = f"{_MATH_PLACEHOLDER_PREFIX}D{counter}"
        placeholders[key] = f"$${m.group(1)}$$"
        counter += 1
        return key

    def replace_inline(m: re.Match) -> str:
        nonlocal counter
        key = f"{_MATH_PLACEHOLDER_PREFIX}I{counter}"
        placeholders[key] = f"${m.group(1)}$"
        counter += 1
        return key

    # Display math first (must be handled before inline to not conflict on $$)
    text = re.sub(r"\$\$(.+?)\$\$", replace_display, text, flags=re.DOTALL)
    # Inline math $...$ (single $ not adjacent to another $)
    text = re.sub(r"(?<!\$)\$(?!\$)(.+?)(?<!\$)\$(?!\$)", replace_inline, text)
    return text, placeholders


def _restore_math(html: str, placeholders: dict[str, str]) -> str:
    """Restore math expressions from placeholders, wrapped in KaTeX-compatible spans.

    Display math: <span class="katex-display">$$...$$</span>
    Inline math: <span class="katex-inline">$...$</span>
    """
    for key, math in sorted(placeholders.items(), key=lambda x: -len(x[0])):
        if key.startswith(f"{_MATH_PLACEHOLDER_PREFIX}D"):
            html = html.replace(key, f'<span class="katex-display">{math}</span>')
        else:
            html = html.replace(key, f'<span class="katex-inline">{math}</span>')
    return html
