# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""YAML frontmatter parsing for article and review source files.

PeerPedia source files use ``---``-delimited YAML frontmatter:

    ---
    title: My Paper
    abstract: We prove that...
    keywords: [P2P, peer review]
    ---
    Content starts here...
"""

from __future__ import annotations


def parse_frontmatter(source: str) -> dict:
    """Parse ``---``-delimited YAML frontmatter from *source*.

    Returns a dict of metadata, or an empty dict on any mismatch.
    """
    import yaml

    if not source.startswith("---"):
        return {}
    parts = source.split("---", 2)
    if len(parts) < 3:
        return {}
    try:
        result = yaml.safe_load(parts[1])
        return result if isinstance(result, dict) else {}
    except yaml.YAMLError:
        return {}


def make_frontmatter(data: dict) -> str:
    """Serialize *data* to a ``---``-delimited YAML frontmatter block."""
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


def strip_frontmatter(source: str) -> str:
    """Remove YAML frontmatter from *source*, return body only."""
    if not source.startswith("---"):
        return source
    parts = source.split("---", 2)
    if len(parts) >= 3:
        return parts[2].strip()
    return source
