# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Centralised filesystem paths — change one file to relocate all PeerPedia data.

Override the data root by setting the ``PEERPEDIA_HOME`` environment variable.
All paths below are relative to ``DATA_ROOT``.
"""

from __future__ import annotations

import os
from pathlib import Path

# ═══════════════════════════════════════════════════════════════════════════════
# Root
# ═══════════════════════════════════════════════════════════════════════════════

DATA_ROOT = Path(os.environ.get("PEERPEDIA_HOME", Path.home() / ".peerpedia"))

# ═══════════════════════════════════════════════════════════════════════════════
# Database
# ═══════════════════════════════════════════════════════════════════════════════

DB_PATH = DATA_ROOT / "peerpedia.db"
DB_URL = f"sqlite:///{DB_PATH}"

# ═══════════════════════════════════════════════════════════════════════════════
# Articles (git repos)
# ═══════════════════════════════════════════════════════════════════════════════

ARTICLES_DIR = DATA_ROOT / "articles"

# ═══════════════════════════════════════════════════════════════════════════════
# Session
# ═══════════════════════════════════════════════════════════════════════════════

SESSION_FILE = DATA_ROOT / "session.json"

# ═══════════════════════════════════════════════════════════════════════════════
# REPL
# ═══════════════════════════════════════════════════════════════════════════════

REPL_HISTORY_FILE = DATA_ROOT / ".repl_history"

# ═══════════════════════════════════════════════════════════════════════════════
# Sync
# ═══════════════════════════════════════════════════════════════════════════════

PENDING_OPS_FILE = DATA_ROOT / "pending_ops.json"
