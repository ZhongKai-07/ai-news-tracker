import pytest
from unittest.mock import AsyncMock, patch
from app.services.semantic_matcher import SemanticMatcher, classify_rule_matches

class TestClassifyRuleMatches:
    def test_title_match_is_strong(self):
        keywords = [{"id": 1, "name": "AI Agent", "aliases": ["智能体"]}]
        result = classify_rule_matches("AI Agent launches today", "Some content about stuff", keywords)
        assert result["strong"] == [{"keyword_id": 1, "match_location": "title", "context_snippet": "AI Agent launches today"}]
        assert result["weak"] == []

    def test_content_only_match_is_weak(self):
        keywords = [{"id": 1, "name": "AI Agent", "aliases": []}]
        result = classify_rule_matches("Breaking news today", "The new AI Agent framework is released", keywords)
        assert len(result["strong"]) == 0
        assert len(result["weak"]) == 1
        assert result["weak"][0]["keyword_id"] == 1

    def test_no_match(self):
        keywords = [{"id": 1, "name": "blockchain", "aliases": []}]
        result = classify_rule_matches("AI is the future", "Machine learning content here", keywords)
        assert result["strong"] == []
        assert result["weak"] == []

    def test_alias_title_match_is_strong(self):
        keywords = [{"id": 1, "name": "AI Agent", "aliases": ["智能体"]}]
        result = classify_rule_matches("智能体框架发布", "一些内容", keywords)
        assert len(result["strong"]) == 1

class TestSemanticMatcher:
    @pytest.mark.asyncio
    async def test_strong_hits_skip_llm(self):
        """Articles with only strong hits should not call LLM."""
        matcher = SemanticMatcher(llm_service=AsyncMock())
        keywords = [{"id": 1, "name": "AI Agent", "aliases": []}]
        articles = [{"id": 100, "title": "AI Agent is here", "cleaned_content": "Content about AI Agent"}]

        results = await matcher.match_batch(articles, keywords)
        matcher.llm_service.call_json.assert_not_called()
        assert len(results) == 1
        assert results[0]["match_method"] == "rule"

    @pytest.mark.asyncio
    async def test_weak_and_miss_trigger_llm(self):
        """Articles without strong hits should be sent to LLM."""
        mock_llm = AsyncMock()
        mock_llm.call_json = AsyncMock(return_value=[
            {"index": 1, "matched_keywords": ["RAG"], "confidence": "high", "reason": "Discusses retrieval augmented generation"}
        ])
        matcher = SemanticMatcher(llm_service=mock_llm)
        keywords = [{"id": 1, "name": "RAG", "aliases": []}]
        articles = [{"id": 100, "title": "New retrieval methods", "cleaned_content": "Discussing retrieval augmented generation approaches"}]

        results = await matcher.match_batch(articles, keywords)
        mock_llm.call_json.assert_called_once()
        assert any(r["match_method"] == "llm" for r in results)

    @pytest.mark.asyncio
    async def test_llm_failure_falls_back_to_rule(self):
        """When LLM fails, weak rule matches should be returned as fallback."""
        mock_llm = AsyncMock()
        mock_llm.call_json = AsyncMock(side_effect=Exception("LLM unavailable"))
        matcher = SemanticMatcher(llm_service=mock_llm)
        keywords = [{"id": 1, "name": "AI Agent", "aliases": []}]
        articles = [{"id": 100, "title": "Breaking news", "cleaned_content": "The new AI Agent framework is released"}]

        results = await matcher.match_batch(articles, keywords)
        # Should fall back to rule match for content-only hit
        assert len(results) == 1
        assert results[0]["match_method"] == "rule"
        assert "LLM unavailable" in results[0]["match_reason"]

    @pytest.mark.asyncio
    async def test_medium_confidence_is_llm_uncertain(self):
        """Medium confidence LLM matches should use llm_uncertain method."""
        mock_llm = AsyncMock()
        mock_llm.call_json = AsyncMock(return_value=[
            {"index": 1, "matched_keywords": ["MCP"], "confidence": "medium", "reason": "Loosely related"}
        ])
        matcher = SemanticMatcher(llm_service=mock_llm)
        keywords = [{"id": 1, "name": "MCP", "aliases": []}]
        articles = [{"id": 100, "title": "New protocol announced", "cleaned_content": "Some content about protocols"}]

        results = await matcher.match_batch(articles, keywords)
        assert any(r["match_method"] == "llm_uncertain" for r in results)
