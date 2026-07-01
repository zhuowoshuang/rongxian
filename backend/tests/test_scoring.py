"""评分服务测试"""
import pytest
from app.services.scoring import (
    calculate_quality_score,
    calculate_valuation_score,
    calculate_growth_score,
    calculate_trend_score,
    calculate_risk_score,
    get_rating,
)


class TestQualityScore:
    """质量评分测试"""

    def test_high_quality(self):
        """高质量财务指标应得高分"""
        financial = type("F", (), {
            "roe": 25.0, "roa": 12.0, "gross_margin": 60.0,
            "net_margin": 30.0, "operating_cashflow": 100.0, "debt_ratio": 30.0,
        })()
        score, details = calculate_quality_score(financial)
        assert score >= 20
        assert isinstance(details, list)

    def test_low_quality(self):
        """低质量财务指标应得低分"""
        financial = type("F", (), {
            "roe": 2.0, "roa": 1.0, "gross_margin": 10.0,
            "net_margin": 1.0, "operating_cashflow": -50.0, "debt_ratio": 85.0,
        })()
        score, details = calculate_quality_score(financial)
        assert score < 15

    def test_none_financial(self):
        """无财务数据应返回默认分"""
        score, details = calculate_quality_score(None)
        assert score == 0
        assert isinstance(details, (str, list))


class TestValuationScore:
    """估值评分测试"""

    def test_low_valuation(self):
        """低 PE/PB 应得高分"""
        price = type("P", (), {"pe": 8.0, "pb": 0.8, "dividend_yield": 5.0, "close": 10.0})()
        financial = type("F", (), {"eps": 1.0, "book_value_per_share": 10.0})()
        score, details = calculate_valuation_score(price, financial)
        assert score >= 12

    def test_high_valuation(self):
        """高 PE/PB 应得低分"""
        price = type("P", (), {"pe": 200.0, "pb": 15.0, "dividend_yield": 0.1, "close": 100.0})()
        financial = type("F", (), {"eps": 0.5, "book_value_per_share": 5.0})()
        score, details = calculate_valuation_score(price, financial)
        assert score < 10


class TestGrowthScore:
    """成长评分测试"""

    def test_high_growth(self):
        """高增长应得高分"""
        financial = type("F", (), {
            "revenue_yoy": 50.0, "net_profit_yoy": 80.0,
        })()
        score, details = calculate_growth_score(financial)
        assert score >= 12

    def test_negative_growth(self):
        """负增长应得低分"""
        financial = type("F", (), {
            "revenue_yoy": -20.0, "net_profit_yoy": -30.0,
        })()
        score, details = calculate_growth_score(financial)
        assert score < 8


class TestRating:
    """评级测试"""

    def test_excellent(self):
        assert get_rating(90) == "BUY"

    def test_good(self):
        assert get_rating(75) == "ADD"

    def test_neutral(self):
        assert get_rating(65) == "WATCH"

    def test_poor(self):
        assert get_rating(50) == "REDUCE"

    def test_bad(self):
        assert get_rating(15) == "SELL"
