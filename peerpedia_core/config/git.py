# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Git configuration — SSH signing env builders and repo structure constants.

SSH signing
  Git reads config from ``GIT_CONFIG_COUNT`` / ``GIT_CONFIG_KEY_*`` env vars,
  not ``-c`` flags (git >= 2.44 rejects ``-c`` after the subcommand).

Repo structure
  ``ARTICLE_REPO_TRACKED_PATTERNS`` defines which paths are allowed in an
  article git repo.  All other paths are git-ignored to prevent free-riding
  (arbitrary files being committed and synced to peers).
"""

from __future__ import annotations

import os
from pathlib import Path

# Patterns tracked in an article git repo — everything else is git-ignored.
ARTICLE_REPO_TRACKED_PATTERNS: frozenset[str] = frozenset({
    ".gitignore",
    "article.md",
    "article.typ",
    "reviews/",
    "reviews/*/",
    "reviews/*/scores.json",
    "reviews/*/threads/",
    "reviews/*/threads/*.md",
    "compiled/",
    "compiled/*.html",
    "compiled/*.svg",
})


def make_article_gitignore() -> str:
    """Return a ``.gitignore`` that only allows ``ARTICLE_REPO_TRACKED_PATTERNS``."""
    lines = [
        "# PeerPedia article repo — only approved paths are tracked.",
        "# Prevents free-riding by blocking arbitrary files from being committed.",
        "*",
    ]
    for pattern in sorted(ARTICLE_REPO_TRACKED_PATTERNS):
        lines.append(f"!{pattern}")
    lines.append("")
    return "\n".join(lines)


def ssh_sign_env(allowed_signers: Path, signing_key: Path) -> dict[str, str]:
    """Env dict for ``git commit -S`` with SSH signing (3 config keys)."""
    return {
        **os.environ,
        "GIT_CONFIG_COUNT": "3",
        "GIT_CONFIG_KEY_0": "gpg.format",
        "GIT_CONFIG_VALUE_0": "ssh",
        "GIT_CONFIG_KEY_1": "gpg.ssh.allowedSignersFile",
        "GIT_CONFIG_VALUE_1": str(allowed_signers),
        "GIT_CONFIG_KEY_2": "user.signingkey",
        "GIT_CONFIG_VALUE_2": str(signing_key),
    }


def ssh_verify_env(allowed_signers: Path) -> dict[str, str]:
    """Env dict for ``git verify-commit`` (2 config keys — no signing key)."""
    return {
        **os.environ,
        "GIT_CONFIG_COUNT": "2",
        "GIT_CONFIG_KEY_0": "gpg.format",
        "GIT_CONFIG_VALUE_0": "ssh",
        "GIT_CONFIG_KEY_1": "gpg.ssh.allowedSignersFile",
        "GIT_CONFIG_VALUE_1": str(allowed_signers),
    }
