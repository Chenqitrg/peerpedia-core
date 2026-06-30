# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Tests for config/params.py utility functions."""


# ═══════════════════════════════════════════════════════════════════════════════
# make_peerpedia_email / extract_user_id_from_email
# ═══════════════════════════════════════════════════════════════════════════════


class TestPeerpediaEmail:
    def test_make_email_appends_suffix(self):
        """Local part + @peerpedia suffix."""
        from peerpedia_core.config.params import make_peerpedia_email
        assert make_peerpedia_email("alice") == "alice@peerpedia"

    def test_make_platform_email(self):
        """Platform email uses 'system' local part."""
        from peerpedia_core.config.params import PLATFORM_EMAIL, make_peerpedia_email
        assert PLATFORM_EMAIL == "system@peerpedia"

    def test_extract_user_id_from_email(self):
        """Extracts local part — inverse of make_peerpedia_email."""
        from peerpedia_core.config.params import extract_user_id_from_email
        assert extract_user_id_from_email("alice@peerpedia") == "alice"
        assert extract_user_id_from_email("user-123@peerpedia") == "user-123"


# ═══════════════════════════════════════════════════════════════════════════════
# article_format / article_filename
# ═══════════════════════════════════════════════════════════════════════════════


class TestArticleFormatUtils:
    def test_format_to_ext_markdown(self):
        from peerpedia_core.config.params import article_format_to_ext
        assert article_format_to_ext("markdown") == ".md"

    def test_format_to_ext_typst(self):
        from peerpedia_core.config.params import article_format_to_ext
        assert article_format_to_ext("typst") == ".typ"

    def test_ext_to_format_md(self):
        from peerpedia_core.config.params import article_ext_to_format
        assert article_ext_to_format(".md") == "markdown"

    def test_ext_to_format_typ(self):
        from peerpedia_core.config.params import article_ext_to_format
        assert article_ext_to_format(".typ") == "typst"

    def test_article_filename_md(self):
        from peerpedia_core.config.params import article_filename
        assert article_filename(".md") == "article.md"

    def test_article_filename_typ(self):
        from peerpedia_core.config.params import article_filename
        assert article_filename(".typ") == "article.typ"
