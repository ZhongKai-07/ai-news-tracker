import pytest
import math
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
from sqlalchemy import select
from app.models.article import Article
from app.models.data_source import DataSource
from app.models.keyword import Keyword
from app.models.keyword_mention import KeywordMention
from app.models.trend_snapshot import TrendSnapshot
from app.services.llm_process_job import (
    _run_title_dedup,
    _run_quality_review,
    _run_semantic_matching,
)


@pytest.fixture
def source_factory(db_session):
    async def _create(name="Test Source", trust_level="medium", weight=1.0):
        src = DataSource(
            name=name, type="rss", url=f"https://example.com/{name}",
            trust_level=trust_level, weight=weight,
        )
        db_session.add(src)
        await db_session.flush()
        return src
    return _create


@pytest.fixture
def article_factory(db_session):
    async def _create(source_id, title="Test Article", quality_tag="passed",
                      needs_llm_matching=False, url=None, content="Some content"):
        a = Article(
            source_id=source_id,
            title=title,
            url=url or f"https://example.com/{title.replace(' ', '-')}",
            content=content,
            cleaned_content=content,
            quality_tag=quality_tag,
            needs_llm_matching=needs_llm_matching,
            fetched_at=datetime.now(timezone.utc),
        )
        db_session.add(a)
        await db_session.flush()
        return a
    return _create


class TestTitleDedup:
    @pytest.mark.asyncio
    async def test_filters_duplicate_titles(self, db_session, source_factory, article_factory):
        src = await source_factory(trust_level="high")
        src2 = await source_factory(name="Low Source", trust_level="low")
        a1 = await article_factory(src.id, title="AI Agent Framework Released", url="https://a.com/1")
        a2 = await article_factory(src2.id, title="AI Agent Framework Released", url="https://a.com/2")
        await db_session.commit()

        await _run_title_dedup(db_session)
        await db_session.flush()

        await db_session.refresh(a1)
        await db_session.refresh(a2)
        assert a1.quality_tag != "filtered"  # higher trust kept
        assert a2.quality_tag == "filtered"  # lower trust filtered

    @pytest.mark.asyncio
    async def test_skips_when_less_than_2_articles(self, db_session, source_factory, article_factory):
        src = await source_factory()
        await article_factory(src.id, title="Only one article")
        await db_session.commit()
        # Should not raise
        await _run_title_dedup(db_session)


class TestQualityReview:
    @pytest.mark.asyncio
    async def test_passes_approved_articles(self, db_session, source_factory, article_factory):
        src = await source_factory()
        a1 = await article_factory(src.id, title="Good tech article", quality_tag="pending_review")
        await db_session.commit()

        mock_response = [{"index": 1, "verdict": "pass", "reason": "Good content"}]
        with patch("app.services.llm_process_job.llm_service") as mock_llm:
            mock_llm.call_json = AsyncMock(return_value=mock_response)
            await _run_quality_review(db_session)

        await db_session.flush()
        await db_session.refresh(a1)
        assert a1.quality_tag == "passed"
        assert a1.needs_llm_matching is True

    @pytest.mark.asyncio
    async def test_filters_rejected_articles(self, db_session, source_factory, article_factory):
        src = await source_factory()
        a1 = await article_factory(src.id, title="Spam article", quality_tag="pending_review")
        await db_session.commit()

        mock_response = [{"index": 1, "verdict": "reject", "reason": "Advertising"}]
        with patch("app.services.llm_process_job.llm_service") as mock_llm:
            mock_llm.call_json = AsyncMock(return_value=mock_response)
            await _run_quality_review(db_session)

        await db_session.flush()
        await db_session.refresh(a1)
        assert a1.quality_tag == "filtered"

    @pytest.mark.asyncio
    async def test_keeps_pending_on_llm_failure(self, db_session, source_factory, article_factory):
        src = await source_factory()
        a1 = await article_factory(src.id, title="Article", quality_tag="pending_review")
        await db_session.commit()

        with patch("app.services.llm_process_job.llm_service") as mock_llm:
            mock_llm.call_json = AsyncMock(side_effect=Exception("LLM down"))
            await _run_quality_review(db_session)

        await db_session.refresh(a1)
        assert a1.quality_tag == "pending_review"

    @pytest.mark.asyncio
    async def test_skips_when_no_pending(self, db_session, source_factory, article_factory):
        src = await source_factory()
        await article_factory(src.id, quality_tag="passed")
        await db_session.commit()
        # Should not call LLM at all
        with patch("app.services.llm_process_job.llm_service") as mock_llm:
            await _run_quality_review(db_session)
            mock_llm.call_json.assert_not_called()


class TestSemanticMatching:
    @pytest.mark.asyncio
    async def test_creates_mentions_and_snapshots(self, db_session, source_factory, article_factory):
        src = await source_factory(weight=1.5)
        a1 = await article_factory(
            src.id, title="New retrieval methods",
            content="Discussing RAG approaches in detail",
            needs_llm_matching=True,
        )
        kw = Keyword(name="RAG", aliases=[])
        db_session.add(kw)
        await db_session.commit()

        mock_match_results = [{
            "article_id": a1.id,
            "keyword_id": kw.id,
            "match_location": "content",
            "context_snippet": "Discussing RAG approaches",
            "match_method": "llm",
            "match_reason": "Discusses retrieval augmented generation",
        }]

        with patch("app.services.llm_process_job.SemanticMatcher") as MockMatcher:
            instance = AsyncMock()
            instance.match_batch = AsyncMock(return_value=mock_match_results)
            MockMatcher.return_value = instance
            await _run_semantic_matching(db_session)

        # Check KeywordMention was created
        mentions = (await db_session.execute(select(KeywordMention))).scalars().all()
        assert len(mentions) == 1
        assert mentions[0].match_method == "llm"
        assert mentions[0].keyword_id == kw.id

        # Check TrendSnapshot was created
        snaps = (await db_session.execute(select(TrendSnapshot))).scalars().all()
        assert len(snaps) == 1
        assert snaps[0].keyword_id == kw.id
        assert snaps[0].mention_count == 1
        # content match (1.0) * source weight (1.5) = 1.5
        assert snaps[0].score == pytest.approx(math.log(1 + 1.5), abs=0.01)

        # Check article marked as processed
        await db_session.refresh(a1)
        assert a1.needs_llm_matching is False

    @pytest.mark.asyncio
    async def test_skips_when_no_articles(self, db_session):
        with patch("app.services.llm_process_job.SemanticMatcher") as MockMatcher:
            await _run_semantic_matching(db_session)
            MockMatcher.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_when_no_keywords(self, db_session, source_factory, article_factory):
        src = await source_factory()
        await article_factory(src.id, needs_llm_matching=True)
        await db_session.commit()

        with patch("app.services.llm_process_job.SemanticMatcher") as MockMatcher:
            await _run_semantic_matching(db_session)
            MockMatcher.assert_not_called()

    @pytest.mark.asyncio
    async def test_updates_existing_snapshot(self, db_session, source_factory, article_factory):
        src = await source_factory(weight=1.0)
        a1 = await article_factory(src.id, title="Article about LLM", needs_llm_matching=True)
        kw = Keyword(name="LLM", aliases=[])
        db_session.add(kw)
        await db_session.flush()
        # Pre-existing snapshot (use UTC date to match implementation)
        utc_today = datetime.now(timezone.utc).date()
        existing_snap = TrendSnapshot(
            keyword_id=kw.id, date=utc_today, score=math.log(1 + 2.0), mention_count=1
        )
        db_session.add(existing_snap)
        await db_session.commit()

        mock_match_results = [{
            "article_id": a1.id,
            "keyword_id": kw.id,
            "match_location": "content",
            "context_snippet": "About LLM",
            "match_method": "llm",
            "match_reason": "Discusses large language models",
        }]

        with patch("app.services.llm_process_job.SemanticMatcher") as MockMatcher:
            instance = AsyncMock()
            instance.match_batch = AsyncMock(return_value=mock_match_results)
            MockMatcher.return_value = instance
            await _run_semantic_matching(db_session)

        await db_session.flush()
        await db_session.refresh(existing_snap)
        assert existing_snap.mention_count == 2
        # old raw=2.0, new contribution=1.0 (content * 1.0 weight), new raw=3.0
        assert existing_snap.score == pytest.approx(math.log(1 + 3.0), abs=0.01)
