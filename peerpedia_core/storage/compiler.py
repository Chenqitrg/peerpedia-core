# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Layer 1: Compiler backends for Typst and Markdown.

This is a versioned module — new backends can be added via PIP without
changing the core protocol.

Abstract interface:
    CompilerBackend.compile(source_path, output_dir) -> CompileResult
    CompilerBackend.extract_metadata(source_content) -> dict
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
    """Extract YAML-like frontmatter from Typst or Markdown source.

    Frontmatter is delimited by --- on its own lines at the start of the file.
    Only simple key: value pairs and list items (with - prefix) are supported
    for MVP. No PyYAML dependency required.

    Example:
        ---
        title: My Article
        abstract: A summary.
        categories:
          - physics
          - math
        ---

        = Actual content starts here
    """
    lines = source.split("\n")
    if not lines or lines[0].strip() != "---":
        return {}

    end_idx = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_idx = i
            break

    if end_idx is None:
        return {}

    fm_lines = lines[1:end_idx]
    return _parse_simple_yaml(fm_lines)


def _parse_simple_yaml(lines: list[str]) -> dict:
    """Parse a minimal YAML subset: scalar keys and list values.

    Supports:
        key: value
        key:
          - item1
          - item2

    No nested dicts, no quotes, no anchors. Just enough for article metadata.
    """
    result = {}
    current_key = None
    current_list = []

    for line in lines:
        # Skip empty lines
        if not line.strip():
            continue

        # List item
        if line.strip().startswith("- "):
            item = line.strip()[2:].strip()
            if current_key is not None:
                current_list.append(item)
            continue

        # Key: value — flush any pending list
        if ":" in line:
            if current_key is not None and current_list:
                result[current_key] = current_list
                current_list = []

            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip()

            if value:
                # Scalar value: key: value
                result[key] = _parse_scalar(value)
                current_key = None
            else:
                # List follows: key:
                current_key = key

    # Flush final list
    if current_key is not None and current_list:
        result[current_key] = current_list

    # Chinese alias mapping
    zh_aliases = {
        "标题": "title",
        "摘要": "abstract",
        "中文摘要": "abstract_zh",
        "分类": "categories",
        "关键词": "keywords",
        "语言": "language",
        "关于人物": "about_person",
        "原始著作": "original_works",
    }
    for zh_key, en_key in zh_aliases.items():
        if zh_key in result and en_key not in result:
            result[en_key] = result.pop(zh_key)

    return result


def _parse_scalar(value: str):
    """Parse a scalar YAML value. Returns str, bool, int, or float."""
    if value.lower() == "true":
        return True
    if value.lower() == "false":
        return False
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        pass
    return value


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
    warnings = []
    for line in stderr.split("\n"):
        line = line.strip()
        if line.startswith("warning:"):
            warnings.append(line)
    return warnings


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
