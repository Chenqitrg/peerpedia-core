# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Spec: YAML frontmatter parsing and generation."""

from peerpedia_core.frontmatter import (
    make_article_frontmatter,
    make_frontmatter,
    parse_frontmatter,
    strip_frontmatter,
)


class TestParseFrontmatter:
    def test_basic_frontmatter(self):
        source = "---\ntitle: My Paper\nabstract: We prove X\n---\nContent here."
        fm = parse_frontmatter(source)
        assert fm == {"title": "My Paper", "abstract": "We prove X"}

    def test_no_frontmatter_returns_empty(self):
        assert parse_frontmatter("Just content, no frontmatter.") == {}

    def test_one_dash_not_frontmatter(self):
        """--- is required — single dash is not frontmatter."""
        assert parse_frontmatter("--\ntitle: Nope\n--\ncontent") == {}

    def test_invalid_yaml_returns_empty(self):
        source = "---\n: invalid yaml: :\n---\nContent."
        assert parse_frontmatter(source) == {}

    def test_non_dict_yaml_returns_empty(self):
        source = "---\n- list item\n- another\n---\nContent."
        assert parse_frontmatter(source) == {}

    def test_keywords_list_parsed(self):
        source = "---\ntitle: Paper\nkeywords: [P2P, peer review]\n---\nContent."
        fm = parse_frontmatter(source)
        assert fm["keywords"] == ["P2P", "peer review"]


class TestMakeFrontmatter:
    def test_make_basic(self):
        yaml_str = make_frontmatter({"title": "Test"})
        assert yaml_str.startswith("---\n")
        assert yaml_str.endswith("---\n")
        assert "title: Test" in yaml_str

    def test_roundtrip(self):
        data = {"title": "Roundtrip Test", "abstract": "Verify roundtrip.",
                "keywords": ["P2P"]}
        yaml_str = make_frontmatter(data)
        parsed = parse_frontmatter(yaml_str)
        assert parsed == data


class TestMakeArticleFrontmatter:
    def test_title_only(self):
        result = make_article_frontmatter("My Title")
        assert "title: My Title" in result
        assert "abstract" not in result

    def test_all_fields(self):
        result = make_article_frontmatter(
            "Full", abstract="An abstract",
            keywords=["a", "b"], categories=["cs"])
        assert "title: Full" in result
        assert "abstract: An abstract" in result
        assert "keywords:" in result
        assert "categories:" in result


class TestStripFrontmatter:
    def test_strip_removes_frontmatter(self):
        source = "---\ntitle: Test\n---\nBody content here."
        assert strip_frontmatter(source) == "Body content here."

    def test_no_frontmatter_passes_through(self):
        source = "Just body content."
        assert strip_frontmatter(source) == source

    def test_strip_trims_whitespace(self):
        source = "---\ntitle: Test\n---\n  Body with spaces.  "
        assert strip_frontmatter(source) == "Body with spaces."
