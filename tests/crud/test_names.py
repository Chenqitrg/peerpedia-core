# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Tests for anonymous name generation (no DB dependency)."""


class TestAnonymousNames:
    def test_generate_anonymous_name(self):
        from peerpedia_core.names import generate_anonymous_name
        name = generate_anonymous_name()
        assert isinstance(name, str)
        assert len(name) >= 2

    def test_derive_anonymous_name_deterministic(self):
        from peerpedia_core.names import derive_anonymous_name
        n1 = derive_anonymous_name("seed-abc")
        n2 = derive_anonymous_name("seed-abc")
        assert n1 == n2

    def test_derive_anonymous_name_different_seeds(self):
        from peerpedia_core.names import derive_anonymous_name
        n1 = derive_anonymous_name("seed-1")
        n2 = derive_anonymous_name("seed-2")
        assert n1 != n2
