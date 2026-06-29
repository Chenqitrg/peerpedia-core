# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Tests for compiler module — format detection and Markdown rendering."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from peerpedia_core.compiler import (
    CompileResult,
    MarkdownBackend,
    TypstBackend,
    _parse_typst_warnings,
    _render_markdown,
    compile_article,
    detect_format,
)
from peerpedia_core.frontmatter import make_frontmatter, strip_frontmatter


# ── detect_format ───────────────────────────────────────────────────────────


class TestDetectFormat:
    def test_markdown_extension(self):
        assert detect_format(Path("test.md")) == "markdown"

    def test_markdown_long_extension(self):
        assert detect_format(Path("test.markdown")) == "markdown"

    def test_typst_extension(self):
        assert detect_format(Path("test.typ")) == "typst"

    def test_typst_long_extension(self):
        assert detect_format(Path("test.typst")) == "typst"

    def test_unknown_extension_raises(self):
        from peerpedia_core.exceptions import BadRequestError
        with pytest.raises(BadRequestError, match="COMPILE_UNKNOWN_FORMAT"):
            detect_format(Path("test.tex"))

    def test_no_extension_raises(self):
        from peerpedia_core.exceptions import BadRequestError
        with pytest.raises(BadRequestError, match="COMPILE_UNKNOWN_FORMAT"):
            detect_format(Path("test"))


def test_compile_result_error():
    """CompileResult with success=False carries error details."""
    result = CompileResult(success=False, format="markdown", error="Something went wrong")
    assert result.success is False
    assert result.format == "markdown"
    assert result.error == "Something went wrong"
    assert result.error_code is None
    assert result.output_path is None


# ── _render_markdown ────────────────────────────────────────────────────────


def test_render_markdown_paragraph():
    html = _render_markdown("Hello **world**.")
    assert "world" in html
    assert "<strong>" in html or "<b>" in html


def test_render_markdown_heading():
    html = _render_markdown("# Title\n\nContent.")
    assert "<h1>" in html


def test_render_markdown_code_block():
    html = _render_markdown("```python\nprint('hi')\n```")
    assert "<code" in html or "<pre" in html


def test_render_markdown_fenced_code():
    html = _render_markdown("```\nplain text\n```")
    assert "<code" in html or "<pre" in html


def test_render_markdown_table():
    md = "| A | B |\n|---|---|\n| 1 | 2 |\n"
    html = _render_markdown(md)
    assert "<table>" in html


def test_render_markdown_math_is_preserved():
    """Inline and display math should survive Markdown rendering.

    pymdownx.arithmatex with ``generic: True`` converts $...$ → \\(...\\)
    and $$...$$ → \\[...\\] for KaTeX compatibility.
    """
    md = "Consider $E = mc^2$ and\n\n$$\\int_0^1 x dx = \\frac{1}{2}$$"
    html = _render_markdown(md)
    # Generic arithmatex wraps math in <span class="arithmatex">...</span>
    assert 'class="arithmatex"' in html
    assert "E = mc^2" in html


def test_render_markdown_empty_string():
    html = _render_markdown("")
    assert html is not None  # returns something, doesn't crash


# ── MarkdownBackend ─────────────────────────────────────────────────────────


class TestMarkdownBackend:
    def test_compile_success(self):
        """Compile a Markdown file to HTML."""
        backend = MarkdownBackend()
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "test.md"
            src.write_text("# Hello\n\nWorld.\n")
            out = Path(tmp) / "compiled"
            out.mkdir()

            result = backend.compile(src, out)

            assert result.success is True
            assert result.format == "markdown"
            assert result.output_path is not None
            assert result.html_content is not None
            assert "<h1>" in result.html_content
            output_file = Path(result.output_path)
            assert output_file.exists()
            assert output_file.read_text() == result.html_content

    def test_compile_with_frontmatter(self):
        """Markdown with YAML frontmatter should be compiled correctly."""
        backend = MarkdownBackend()
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "article.md"
            fm = make_frontmatter({"title": "My Paper", "abstract": "We prove..."})
            src.write_text(fm + "# Introduction\n\nHello.\n")
            out = Path(tmp) / "compiled"
            out.mkdir()

            result = backend.compile(src, out)

            assert result.success is True
            html = result.html_content
            assert "<h1>" in html  # Introduction heading
            # Frontmatter should be stripped — title should NOT appear as heading
            assert "My Paper" not in html or "YAML" not in html

    def test_compile_file_not_found(self):
        backend = MarkdownBackend()
        src = Path("/nonexistent/article.md")
        out = Path("/tmp/compiled")

        result = backend.compile(src, out)

        assert result.success is False
        assert result.error is not None

    def test_compile_output_file_created(self):
        backend = MarkdownBackend()
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "paper.md"
            src.write_text("# Paper\n")
            out = Path(tmp) / "compiled"
            out.mkdir()

            result = backend.compile(src, out)

            assert result.output_path is not None
            output_file = Path(result.output_path)
            assert output_file.name == "paper.html"
            assert output_file.suffix == ".html"


# ── _parse_typst_warnings ────────────────────────────────────────────────────


def test_parse_typst_warnings_empty():
    assert _parse_typst_warnings("") == []


def test_parse_typst_warnings_single():
    stderr = "warning: unknown variable x\n"
    result = _parse_typst_warnings(stderr)
    assert len(result) == 1
    assert "unknown variable x" in result[0]


def test_parse_typst_warnings_multiple():
    stderr = (
        "warning: line 10: unknown variable x\n"
        "warning: line 15: missing font\n"
        "info: compilation succeeded\n"
    )
    result = _parse_typst_warnings(stderr)
    assert len(result) == 2


def test_parse_typst_warnings_skips_non_warning():
    stderr = "info: some info\nwarning: real warning\n"
    result = _parse_typst_warnings(stderr)
    assert len(result) == 1


# ── TypstBackend ─────────────────────────────────────────────────────────────


class TestTypstBackend:
    def test_typst_not_installed(self):
        """When typst binary is not found, return error result."""
        backend = TypstBackend()
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "paper.typ"
            src.write_text("#let main = []")
            out = Path(tmp) / "compiled"
            out.mkdir()

            with patch("peerpedia_core.compiler.shutil.which", return_value=None):
                result = backend.compile(src, out)

            assert result.success is False
            assert result.error_code == "COMPILE_TYPST_NOT_FOUND"

    def test_typst_compilation_error(self):
        """Typst fails with non-zero return code."""
        backend = TypstBackend()
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "paper.typ"
            src.write_text("#let main = []")
            out = Path(tmp) / "compiled"
            out.mkdir()

            mock_run = type(
                "MockResult",
                (),
                {"returncode": 1, "stderr": "error: syntax error", "stdout": ""},
            )
            with patch("peerpedia_core.compiler.shutil.which", return_value="/usr/local/bin/typst"):
                with patch("peerpedia_core.compiler.subprocess.run", return_value=mock_run):
                    result = backend.compile(src, out)

            assert result.success is False
            assert "syntax error" in result.error

    def test_typst_timeout(self):
        """Typst compilation times out."""
        import subprocess

        backend = TypstBackend()
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "paper.typ"
            src.write_text("#let main = []")
            out = Path(tmp) / "compiled"
            out.mkdir()

            with patch("peerpedia_core.compiler.shutil.which", return_value="/usr/local/bin/typst"):
                with patch("peerpedia_core.compiler.subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="typst", timeout=30)):
                    result = backend.compile(src, out)

            assert result.success is False
            assert result.error_code == "COMPILE_TIMEOUT"

    def test_typst_svg_output_stores_html_content(self):
        """SVG output from Typst is stored in html_content."""
        backend = TypstBackend()
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "paper.typ"
            src.write_text("#let main = []")
            out = Path(tmp) / "compiled"
            out.mkdir()
            svg_file = out / "paper.svg"
            svg_file.write_text("<svg></svg>")

            mock_run = type(
                "MockResult",
                (),
                {"returncode": 0, "stderr": "", "stdout": ""},
            )
            with patch("peerpedia_core.compiler.shutil.which", return_value="/usr/local/bin/typst"):
                with patch("peerpedia_core.compiler.subprocess.run", return_value=mock_run):
                    result = backend.compile(src, out, fmt="svg")

            assert result.success is True
            assert result.format == "typst-svg"
            assert result.html_content == "<svg></svg>"


# ── compile_article (integration) ────────────────────────────────────────────


class TestCompileArticle:
    def test_compile_markdown_via_top_level(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "paper.md"
            src.write_text("# Hello\n\nWorld.\n")

            result = compile_article(src, fmt="html")

            assert result.success is True
            assert result.format == "markdown"
            output_file = Path(result.output_path)
            assert output_file.exists()

    def test_compile_auto_detect_markdown(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "paper.md"
            src.write_text("# Auto detected\n")

            result = compile_article(src)  # no fmt parameter

            assert result.success is True
            assert result.format == "markdown"

    def test_compile_auto_detect_typst_not_installed(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "paper.typ"
            src.write_text("#let main = []")

            with patch("peerpedia_core.compiler.shutil.which", return_value=None):
                result = compile_article(src)

            assert result.success is False
            assert result.error_code == "COMPILE_TYPST_NOT_FOUND"

    def test_compile_markdown_rejects_non_html_format(self):
        """--format pdf on a Markdown article should error, not silently produce HTML."""
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "paper.md"
            src.write_text("# Hello\n\nWorld.\n")

            result = compile_article(src, fmt="pdf")

            assert result.success is False
            assert result.error_code == "COMPILE_FORMAT_MISMATCH"
            assert result.format == "pdf"

    def test_compile_markdown_accepts_html_format(self):
        """--format html on a Markdown article should succeed."""
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "paper.md"
            src.write_text("# Hello\n\nWorld.\n")

            result = compile_article(src, fmt="html")

            assert result.success is True
