# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Tests for config/git.py — SSH signing env builders and gitignore generation."""

import os
from pathlib import Path


# ═══════════════════════════════════════════════════════════════════════════════
# make_article_gitignore
# ═══════════════════════════════════════════════════════════════════════════════


class TestMakeArticleGitignore:
    def test_starts_with_star_glob(self):
        """First rule ignores everything — only whitelisted patterns pass."""
        from peerpedia_core.config.git import make_article_gitignore
        content = make_article_gitignore()
        lines = content.split("\n")
        # Two comment lines, then the "*" glob
        assert "*" in lines, "Expected '*' glob line in gitignore"

    def test_includes_article_md(self):
        """article.md is whitelisted — the primary source file."""
        from peerpedia_core.config.git import make_article_gitignore
        assert "!article.md" in make_article_gitignore()

    def test_includes_article_typ(self):
        """article.typ is whitelisted — Typst source files."""
        from peerpedia_core.config.git import make_article_gitignore
        assert "!article.typ" in make_article_gitignore()

    def test_includes_reviews_dir(self):
        """reviews/ patterns are whitelisted — scores and threads."""
        from peerpedia_core.config.git import make_article_gitignore
        content = make_article_gitignore()
        assert "!reviews/" in content
        assert "!reviews/*/scores.json" in content

    def test_includes_compiled_dir(self):
        """compiled/ patterns are whitelisted — rendered output."""
        from peerpedia_core.config.git import make_article_gitignore
        content = make_article_gitignore()
        assert "!compiled/" in content
        assert "!compiled/*.html" in content


# ═══════════════════════════════════════════════════════════════════════════════
# ssh_sign_env
# ═══════════════════════════════════════════════════════════════════════════════


class TestSshSignEnv:
    def test_includes_git_config_count_3(self):
        """SSH signing uses exactly 3 GIT_CONFIG_ keys (format + signersFile + signingkey)."""
        from peerpedia_core.config.git import ssh_sign_env
        env = ssh_sign_env(Path("/tmp/signers"), Path("/tmp/key"))
        assert env["GIT_CONFIG_COUNT"] == "3"

    def test_sets_ssh_format(self):
        """gpg.format is set to 'ssh'."""
        from peerpedia_core.config.git import ssh_sign_env
        env = ssh_sign_env(Path("/tmp/signers"), Path("/tmp/key"))
        assert env["GIT_CONFIG_VALUE_0"] == "ssh"

    def test_sets_allowed_signers_file(self):
        """gpg.ssh.allowedSignersFile is set to the signers path."""
        from peerpedia_core.config.git import ssh_sign_env
        env = ssh_sign_env(Path("/tmp/signers"), Path("/tmp/key"))
        assert env["GIT_CONFIG_VALUE_1"] == "/tmp/signers"

    def test_sets_signing_key(self):
        """user.signingkey is set to the key path."""
        from peerpedia_core.config.git import ssh_sign_env
        env = ssh_sign_env(Path("/tmp/signers"), Path("/tmp/key"))
        assert env["GIT_CONFIG_VALUE_2"] == "/tmp/key"

    def test_inherits_os_environ(self):
        """Caller's environment is preserved — only GIT_CONFIG_ keys are overlaid."""
        from peerpedia_core.config.git import ssh_sign_env
        env = ssh_sign_env(Path("/t/s"), Path("/t/k"))
        for k, v in os.environ.items():
            if k.startswith("GIT_CONFIG_"):
                continue  # these are intentionally overridden
            assert env[k] == v, f"env[{k!r}] changed from {v!r} to {env[k]!r}"


# ═══════════════════════════════════════════════════════════════════════════════
# ssh_verify_env
# ═══════════════════════════════════════════════════════════════════════════════


class TestSshVerifyEnv:
    def test_includes_git_config_count_2(self):
        """SSH verify uses exactly 2 GIT_CONFIG_ keys (format + signersFile) — no signing key."""
        from peerpedia_core.config.git import ssh_verify_env
        env = ssh_verify_env(Path("/tmp/signers"))
        assert env["GIT_CONFIG_COUNT"] == "2"

    def test_sets_ssh_format(self):
        """gpg.format is set to 'ssh'."""
        from peerpedia_core.config.git import ssh_verify_env
        env = ssh_verify_env(Path("/tmp/signers"))
        assert env["GIT_CONFIG_VALUE_0"] == "ssh"

    def test_sets_allowed_signers_file(self):
        """gpg.ssh.allowedSignersFile is set, no signingkey."""
        from peerpedia_core.config.git import ssh_verify_env
        env = ssh_verify_env(Path("/tmp/signers"))
        assert env["GIT_CONFIG_VALUE_1"] == "/tmp/signers"

    def test_no_signing_key_in_verify_env(self):
        """verify-commit must not include a signing key — it only checks."""
        from peerpedia_core.config.git import ssh_verify_env
        env = ssh_verify_env(Path("/tmp/signers"))
        assert "user.signingkey" not in str(env)
        assert "GIT_CONFIG_KEY_2" not in env
