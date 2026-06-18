# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""All tunable system parameters — single source of truth.

To adjust any parameter, edit the defaults here or load from external config.
All tunable functions are replaceable so the community can iterate on mechanisms.
"""

from dataclasses import dataclass


@dataclass
class SinkParams:
    """Sedimentation pool timing parameters."""

    new_article_default_days: int = 7
    edit_article_default_days: int = 3
    min_days: int = 2
    max_days: int = 180


@dataclass
class ScoreParams:
    """Scoring weights and tunable functions."""

    max_score: float = 5.0
    self_review_weight: float = 0.15
    community_weight: float = 0.85

    def score_to_sink_multiplier(self, avg_score: float) -> float:
        """Convert average score (0..5) to a sink-time multiplier (0..1).

        5.0 → multiplier ~0 (shortest sink), 0.0 → multiplier ~1 (longest sink).
        Linear interpolation: multiplier = 1 - (avg_score / max_score)
        """
        return 1.0 - (avg_score / self.max_score)

    def no_review_penalty(self) -> float:
        """Penalty applied when an article receives zero reviews in the pool.

        Returns a positive value that reduces the article's effective score.
        Default: 0.5 (equivalent to losing half a point).
        """
        return 0.5


@dataclass
class ReputationParams:
    """Reputation mechanism parameters (forward-looking)."""

    article_to_author_weight: float = 0.3
    author_weight_in_review: float = 0.2


@dataclass
class CommentParams:
    """Comment and thread parameters."""

    max_length: int = 300


@dataclass
class Params:
    """Aggregate of all tunable parameter groups."""

    sink: SinkParams
    score: ScoreParams
    reputation: ReputationParams
    comment: CommentParams

    def __init__(self):
        self.sink = SinkParams()
        self.score = ScoreParams()
        self.reputation = ReputationParams()
        self.comment = CommentParams()


params = Params()
