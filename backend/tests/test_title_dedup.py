import pytest
from app.services.title_dedup import jaccard_similarity, find_duplicates

class TestJaccardSimilarity:
    def test_identical_titles(self):
        assert jaccard_similarity("Hello World", "Hello World") == 1.0

    def test_completely_different(self):
        assert jaccard_similarity("abc def", "xyz uvw") == 0.0

    def test_partial_overlap(self):
        score = jaccard_similarity("AI Agent Framework Released", "AI Agent Framework Launched")
        assert 0.5 < score < 1.0

    def test_chinese_bigram(self):
        score = jaccard_similarity("人工智能技术发展", "人工智能技术趋势")
        assert score > 0.5

    def test_empty_title(self):
        assert jaccard_similarity("", "Hello") == 0.0
        assert jaccard_similarity("", "") == 0.0

class TestFindDuplicates:
    def test_finds_duplicate_pair(self):
        articles = [
            {"id": 1, "title": "OpenAI releases new AI agent framework", "trust_level": "high"},
            {"id": 2, "title": "OpenAI releases new AI agent framework", "trust_level": "medium"},
        ]
        dupes = find_duplicates(articles, threshold=0.9)
        assert 2 in dupes  # lower trust article should be flagged
        assert 1 not in dupes

    def test_near_duplicate_below_threshold(self):
        """Titles that are similar but below threshold should not be flagged."""
        articles = [
            {"id": 1, "title": "OpenAI releases new AI agent framework", "trust_level": "high"},
            {"id": 2, "title": "OpenAI releases new AI agent framework today", "trust_level": "medium"},
        ]
        # Jaccard = 6/7 ≈ 0.857, below 0.9 threshold
        dupes = find_duplicates(articles, threshold=0.9)
        assert len(dupes) == 0

    def test_no_duplicates(self):
        articles = [
            {"id": 1, "title": "AI Agent developments in 2026", "trust_level": "high"},
            {"id": 2, "title": "Quantum computing breakthrough announced", "trust_level": "medium"},
        ]
        dupes = find_duplicates(articles, threshold=0.9)
        assert len(dupes) == 0

    def test_keeps_higher_trust(self):
        articles = [
            {"id": 1, "title": "Same article title here about AI", "trust_level": "low"},
            {"id": 2, "title": "Same article title here about AI", "trust_level": "high"},
        ]
        dupes = find_duplicates(articles, threshold=0.9)
        # Should flag article 1 (low trust) as duplicate, keep article 2 (high trust)
        assert 1 in dupes
        assert 2 not in dupes

    def test_length_prefilter(self):
        """Titles with >50% length difference should be skipped."""
        articles = [
            {"id": 1, "title": "Short", "trust_level": "high"},
            {"id": 2, "title": "This is a very long title that is completely different in length", "trust_level": "high"},
        ]
        dupes = find_duplicates(articles, threshold=0.9)
        assert len(dupes) == 0
