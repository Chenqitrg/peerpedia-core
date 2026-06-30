# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Unit tests for the mother command."""

from __future__ import annotations

from argparse import Namespace

from peerpedia_core.cli.cmds.mother import _cmd_mother


def test_mother_is_noop():
    """Mother handler is intentionally empty — help content lives in help/mother.txt."""
    _cmd_mother(Namespace())
