import math
import pytest
from app.services.trend_calculator import calculate_daily_score, detect_trend_direction

def test_calculate_daily_score_title_weighted():
    mentions = [{"match_location": "title", "source_weight": 1.0}, {"match_location": "content", "source_weight": 1.0}]
    score = calculate_daily_score(mentions)
    assert score == pytest.approx(math.log(1 + 3.0), rel=1e-3)

def test_calculate_daily_score_with_source_weight():
    mentions = [{"match_location": "title", "source_weight": 2.0}]
    score = calculate_daily_score(mentions)
    assert score == pytest.approx(math.log(1 + 4.0), rel=1e-3)

def test_calculate_daily_score_empty():
    assert calculate_daily_score([]) == 0.0

def test_detect_trend_direction_rising():
    scores = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0]
    assert detect_trend_direction(scores) == "rising"

def test_detect_trend_direction_falling():
    scores = [7.0, 6.0, 5.0, 4.0, 3.0, 2.0, 1.0]
    assert detect_trend_direction(scores) == "falling"

def test_detect_trend_direction_stable():
    scores = [3.0, 3.1, 2.9, 3.0, 3.1, 2.9, 3.0]
    assert detect_trend_direction(scores) == "stable"

def test_detect_trend_direction_empty():
    assert detect_trend_direction([]) == "stable"
