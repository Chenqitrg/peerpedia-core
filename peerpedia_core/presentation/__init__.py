# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Presentation layer — shared Rich components for CLI and REPL.

Architecture constraint:
  ``presentation/`` imports from ``types/`` and stdlib only.
  It NEVER imports from ``cli/``, ``repl/``, ``app/``, ``core/``, or ``storage/``.
  Both ``cli/`` and ``repl/`` import from here.
"""
