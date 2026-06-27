# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

r"""Sedimentation pool — pure computation, zero storage dependencies.

Two pure functions used by ``commands/workflow.py``:

    is_ready_to_publish(eta) → bool
        Compare sink ETA against current UTC time.  Handles timezone-naive
        datetimes by treating them as UTC.  Returns False for None.

    apply_no_review_penalty(scores) → dict
        Subtract the configured penalty from every score dimension, floor
        at 0.0.  Raises TypeError on None (fail fast — caller should check).

Reviewer's checklist
--------------------
- Is this file free of storage/ and Session imports?
- Does apply_no_review_penalty raise on None rather than returning {}?
"""

from datetime import datetime, timezone

from peerpedia_core.config.params import params


def is_ready_to_publish(sink_eta: datetime | None) -> bool:
    """Check if the sink time has elapsed. Returns False if sink_eta is None."""
    if sink_eta is None:
        return False
    now = datetime.now(timezone.utc)
    if sink_eta.tzinfo is None:
        sink_eta = sink_eta.replace(tzinfo=timezone.utc)
    return now >= sink_eta


def apply_no_review_penalty(scores: dict) -> dict:
    """Apply penalty when an article receives zero reviews in the pool.

    Returns a new scores dict with penalty applied (each dimension reduced).
    Raises TypeError if scores is None — fail fast.
    """
    if scores is None:
        raise TypeError("scores must not be None — fail fast")
    penalty = params.score.no_review_penalty()
    return {dim: max(0.0, value - penalty) for dim, value in scores.items()}
