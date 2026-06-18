# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Tests for core value objects — sharable types used across models."""

import pytest

from peerpedia_core.types.messages import ThreadMessage
from peerpedia_core.types.scores import FiveDimScores, ReputationScores


class TestFiveDimScores:
    """文章五维评分"""

    def test_create_with_values(self):
        s = FiveDimScores(
            originality=4.0,
            rigor=3.5,
            completeness=5.0,
            pedagogy=2.0,
            impact=4.5,
        )
        assert s.originality == 4.0
        assert s.rigor == 3.5
        assert s.completeness == 5.0
        assert s.pedagogy == 2.0
        assert s.impact == 4.5

    def test_average(self):
        s = FiveDimScores(
            originality=4.0,
            rigor=4.0,
            completeness=4.0,
            pedagogy=4.0,
            impact=4.0,
        )
        assert s.average() == 4.0

    def test_average_mixed(self):
        s = FiveDimScores(
            originality=5.0,
            rigor=0.0,
            completeness=5.0,
            pedagogy=0.0,
            impact=5.0,
        )
        assert s.average() == 3.0

    def test_to_dict(self):
        s = FiveDimScores(
            originality=4.0,
            rigor=3.0,
            completeness=5.0,
            pedagogy=2.0,
            impact=1.0,
        )
        d = s.to_dict()
        assert d == {
            "originality": 4.0,
            "rigor": 3.0,
            "completeness": 5.0,
            "pedagogy": 2.0,
            "impact": 1.0,
        }

    def test_defaults_are_zero(self):
        s = FiveDimScores()
        assert s.originality == 0.0
        assert s.rigor == 0.0
        assert s.completeness == 0.0
        assert s.pedagogy == 0.0
        assert s.impact == 0.0

    def test_clamp_range(self):
        """值超出 0-5 时截断"""
        s = FiveDimScores(
            originality=6.0,
            rigor=-1.0,
            completeness=5.0,
            pedagogy=2.0,
            impact=7.0,
        )
        assert s.originality == 5.0
        assert s.rigor == 0.0
        assert s.impact == 5.0

    def test_weighted_average(self):
        """带权重的平均"""
        s = FiveDimScores(
            originality=5.0,
            rigor=5.0,
            completeness=5.0,
            pedagogy=1.0,
            impact=1.0,
        )
        # 权重一样 → 简单平均
        result = s.weighted_average([1, 1, 1, 1, 1])
        assert result == pytest.approx(3.4)

    def test_weighted_average_zero_weights(self):
        """全零权重返回 0.0 而不是除零错误"""
        s = FiveDimScores(
            originality=3.0,
            rigor=3.0,
            completeness=3.0,
            pedagogy=3.0,
            impact=3.0,
        )
        result = s.weighted_average([0, 0, 0, 0, 0])
        assert result == 0.0

    def test_weighted_average_custom_weights(self):
        """自定义权重影响各维度贡献"""
        s = FiveDimScores(
            originality=5.0,
            rigor=5.0,
            completeness=1.0,
            pedagogy=1.0,
            impact=1.0,
        )
        # 只重视 originality 和 rigor
        result = s.weighted_average([0.5, 0.5, 0, 0, 0])
        assert result == 5.0


class TestReputationScores:
    """用户四维信誉评分"""

    def test_create_with_values(self):
        s = ReputationScores(
            professionalism=3.0,
            objectivity=4.0,
            collaboration=2.5,
            pedagogy=4.5,
        )
        assert s.professionalism == 3.0
        assert s.objectivity == 4.0
        assert s.collaboration == 2.5
        assert s.pedagogy == 4.5

    def test_defaults_are_zero(self):
        s = ReputationScores()
        assert s.professionalism == 0.0
        assert s.objectivity == 0.0
        assert s.collaboration == 0.0
        assert s.pedagogy == 0.0

    def test_average(self):
        s = ReputationScores(
            professionalism=4.0,
            objectivity=4.0,
            collaboration=4.0,
            pedagogy=4.0,
        )
        assert s.average() == 4.0

    def test_to_dict(self):
        s = ReputationScores(professionalism=3.0, objectivity=4.0, collaboration=2.0, pedagogy=5.0)
        assert s.to_dict() == {
            "professionalism": 3.0,
            "objectivity": 4.0,
            "collaboration": 2.0,
            "pedagogy": 5.0,
        }


class TestThreadMessage:
    """评论对话线程中的一条消息"""

    def test_create(self):
        msg = ThreadMessage(
            author_id="user123",
            content="这个公式推导可以更详细。",
        )
        assert msg.author_id == "user123"
        assert msg.content == "这个公式推导可以更详细。"
        assert msg.created_at is not None  # 自动生成时间戳

    def test_content_not_exceed_300_chars(self):
        """超过 300 字抛出异常"""
        long_content = "x" * 301
        with pytest.raises(ValueError, match="300"):
            ThreadMessage(author_id="user1", content=long_content)

    def test_content_exactly_300_chars(self):
        """刚好 300 字可以创建"""
        content = "a" * 300
        msg = ThreadMessage(author_id="user1", content=content)
        assert len(msg.content) == 300

    def test_empty_content_raises(self):
        with pytest.raises(ValueError):
            ThreadMessage(author_id="user1", content="")

    def test_to_dict(self):
        msg = ThreadMessage(author_id="user1", content="好文章")
        d = msg.to_dict()
        assert d["author_id"] == "user1"
        assert d["content"] == "好文章"
        assert "created_at" in d
