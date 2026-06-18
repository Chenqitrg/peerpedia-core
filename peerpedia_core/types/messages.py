# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Thread messages — used in Review and MergeProposal conversations."""

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class ThreadMessage:
    """A single message in a review or merge-proposal thread.

    Messages are immutable after creation — reply instead of editing.
    """

    author_id: str
    content: str
    author_name: str = ""  # resolved at post time; stored for display
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self):
        if not self.content or not self.content.strip():
            raise ValueError("Content cannot be empty")
        if len(self.content) > 300:
            raise ValueError(f"Content must be ≤ 300 characters, got {len(self.content)}")

    def to_dict(self) -> dict:
        return {
            "author_id": self.author_id,
            "content": self.content,
            "author_name": self.author_name,
            "created_at": self.created_at.isoformat(),
        }
