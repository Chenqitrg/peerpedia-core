# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Backward-compat re-export of ``peerpedia_core.messages``."""

from peerpedia_core.messages import (
    Kind,
    Msg as _Msg,
    REGISTRY as _REGISTRY,
    log_text as _log_text,
    lookup as _lookup,
)

__all__ = ["Kind", "_Msg", "_REGISTRY", "_log_text", "_lookup"]
