"""信号服务测试"""
import pytest
from app.services.signal import determine_signal_type, calculate_position


class TestSignalType:
    """信号类型判定测试"""

    def test_buy_signal(self):
        """高分应产生买入信号"""
        score = type("S", (), {
            "total_score": 88.0, "quality_score": 26.0,
            "valuation_score": 18.0, "growth_score": 18.0,
            "trend_score": 18.0, "risk_score": 8.0,
        })()
        sig_type, strength, logic = determine_signal_type(score)
        assert sig_type == "BUY"
        assert 1 <= strength <= 5
        assert isinstance(logic, (str, dict))

    def test_sell_signal(self):
        """低分应产生卖出信号"""
        score = type("S", (), {
            "total_score": 20.0, "quality_score": 5.0,
            "valuation_score": 5.0, "growth_score": 3.0,
            "trend_score": 3.0, "risk_score": 4.0,
        })()
        sig_type, strength, logic = determine_signal_type(score)
        assert sig_type == "SELL"

    def test_watch_signal(self):
        """中等分应产生观望信号"""
        score = type("S", (), {
            "total_score": 50.0, "quality_score": 15.0,
            "valuation_score": 10.0, "growth_score": 10.0,
            "trend_score": 10.0, "risk_score": 5.0,
        })()
        sig_type, strength, logic = determine_signal_type(score)
        assert sig_type in ("WATCH", "ADD", "REDUCE")


class TestPosition:
    """仓位计算测试"""

    def test_buy_position(self):
        """买入信号应建议正仓位"""
        pos = calculate_position("BUY", 4)
        assert pos > 0
        assert pos <= 20

    def test_sell_position(self):
        """卖出信号应建议 0 仓位"""
        pos = calculate_position("SELL", 5)
        assert pos == 0

    def test_watch_position(self):
        """观望信号仓位应较低"""
        pos = calculate_position("WATCH", 3)
        assert pos <= 5
