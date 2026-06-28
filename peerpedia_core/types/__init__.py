# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Shared types and display helpers — pure, no IO."""


def short_id(id_str: str, n: int = 8) -> str:
    """Return the first *n* characters of an ID string (UUID, git hash, etc.).

    >>> short_id("a1b2c3d4-e5f6-7890-abcd-ef1234567890")
    'a1b2c3d4'
    """
    return id_str[:n]
