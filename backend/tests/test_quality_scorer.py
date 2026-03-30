import pytest
from app.services.quality_scorer import calculate_quality_score

class TestQualityScorer:
    def test_high_trust_long_content(self):
        score = calculate_quality_score(
            title="A detailed analysis of AI trends in 2026",
            content="x" * 600,
            url="https://blog.anthropic.com/ai-trends",
            trust_level="high",
        )
        assert score >= 60  # should pass
        assert score <= 100

    def test_low_trust_short_content(self):
        score = calculate_quality_score(
            title="Hi",
            content="short",
            url="https://unknown.xyz/post",
            trust_level="low",
        )
        assert score < 30  # should be filtered

    def test_medium_trust_normal_content(self):
        score = calculate_quality_score(
            title="New developments in machine learning research",
            content="x" * 300,
            url="https://techcrunch.com/article",
            trust_level="medium",
        )
        assert 30 <= score <= 100

    def test_ad_url_penalty(self):
        score_normal = calculate_quality_score(
            title="Good article", content="x" * 300,
            url="https://example.com/article", trust_level="medium",
        )
        score_ad = calculate_quality_score(
            title="Good article", content="x" * 300,
            url="https://example.com/ad/sponsored-post", trust_level="medium",
        )
        assert score_ad < score_normal

    def test_spam_title_penalty(self):
        score = calculate_quality_score(
            title="Sponsored: Buy this product now",
            content="x" * 300,
            url="https://example.com/post",
            trust_level="medium",
        )
        # medium(50) + content(+5) + title(+5) - spam(-30) = 30 → grey zone
        assert score <= 30

    def test_score_clamped_to_0_100(self):
        # Low trust + empty content + bad URL + spam title = deeply negative raw score
        score = calculate_quality_score(
            title="AD sponsored", content="",
            url="https://x.com/ad/redirect/campaign", trust_level="low",
        )
        assert score >= 0

        # High trust + long content + good title
        score = calculate_quality_score(
            title="A perfectly normal technology article title",
            content="x" * 1000, url="https://good.com/post", trust_level="high",
        )
        assert score <= 100

    def test_empty_content_penalty(self):
        score = calculate_quality_score(
            title="Normal article title here",
            content="", url="https://example.com/post", trust_level="high",
        )
        # high(80) + good title(+5) + empty content(-20) = 65
        assert score >= 60
