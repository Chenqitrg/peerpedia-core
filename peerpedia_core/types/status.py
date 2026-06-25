# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Canonical article status values — single source of truth.

Import from here instead of hardcoding status sets in individual modules.
"""

VALID_ARTICLE_STATUSES = frozenset({"draft", "sedimentation", "published", "rejected"})
