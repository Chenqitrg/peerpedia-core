# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Tests for peerpedia_core.config.params — all tunable system parameters."""

import pytest

from peerpedia_core.config.params import (
    CommentParams,
    Params,
    ReputationParams,
    ScoreParams,
    SinkParams,
)
from peerpedia_core.config.params import (
    params as default_params,
)


class TestSinkParams:
    """沉淀池参数"""

    def test_defaults(self):
        p = SinkParams()
        assert p.new_article_default_days == 7
        assert p.edit_article_default_days == 3
        assert p.min_days == 2
        assert p.max_days == 180

    def test_custom_values(self):
        p = SinkParams(
            new_article_default_days=14,
            edit_article_default_days=5,
            min_days=1,
            max_days=90,
        )
        assert p.new_article_default_days == 14
        assert p.edit_article_default_days == 5
        assert p.min_days == 1
        assert p.max_days == 90


class TestScoreParams:
    """评分参数"""

    def test_defaults(self):
        p = ScoreParams()
        assert p.max_score == 5.0
        assert p.self_review_weight == 0.15
        assert p.community_weight == 0.85

    def test_score_to_sink_multiplier_max_score(self):
        """最高分 → 沉淀最快（乘数最小，接近 min_days 比例）"""
        p = ScoreParams()
        multiplier = p.score_to_sink_multiplier(5.0)
        # 满分应该让沉淀时间接近最短
        assert multiplier == pytest.approx(0.0, abs=0.1)

    def test_score_to_sink_multiplier_min_score(self):
        """最低分 → 沉淀最慢（乘数最大，接近 max_days 比例）"""
        p = ScoreParams()
        multiplier = p.score_to_sink_multiplier(0.0)
        # 0 分应该让沉淀时间接近最长
        assert multiplier == pytest.approx(1.0, abs=0.1)

    def test_score_to_sink_multiplier_mid_score(self):
        """中间分 → 沉淀时间在中间"""
        p = ScoreParams()
        m_low = p.score_to_sink_multiplier(0.0)
        m_mid = p.score_to_sink_multiplier(2.5)
        m_high = p.score_to_sink_multiplier(5.0)
        # 单调递减
        assert m_low > m_mid > m_high

    def test_score_to_sink_multiplier_range(self):
        """返回值在 [0, 1] 内"""
        p = ScoreParams()
        for score in [0.0, 1.0, 2.0, 3.0, 4.0, 5.0]:
            m = p.score_to_sink_multiplier(score)
            assert 0.0 <= m <= 1.0

    def test_no_review_penalty_default(self):
        """无评分默认减分"""
        p = ScoreParams()
        penalty = p.no_review_penalty()
        assert penalty > 0.0
        assert penalty <= 1.0

    def test_no_review_penalty_is_positive(self):
        """减分值为正数（降低分数）"""
        p = ScoreParams()
        assert p.no_review_penalty() > 0.0


class TestReputationParams:
    """信誉参数"""

    def test_defaults(self):
        p = ReputationParams()
        assert p.article_to_author_weight == 0.3
        assert p.author_weight_in_review == 0.2


class TestCommentParams:
    """评论参数"""

    def test_default_max_length(self):
        p = CommentParams()
        assert p.max_length == 300


class TestParams:
    """全局参数单例"""

    def test_singleton_has_all_groups(self):
        p = Params()
        assert isinstance(p.sink, SinkParams)
        assert isinstance(p.score, ScoreParams)
        assert isinstance(p.reputation, ReputationParams)
        assert isinstance(p.comment, CommentParams)

    def test_default_singleton(self):
        assert isinstance(default_params, Params)
        assert default_params.sink.new_article_default_days == 7
        assert default_params.comment.max_length == 300
