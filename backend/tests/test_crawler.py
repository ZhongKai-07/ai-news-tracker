import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from sqlalchemy import select
from app.services.crawler import CrawlerService
from app.models.data_source import DataSource
from app.models.keyword import Keyword
from app.models.article import Article
from app.models.keyword_mention import KeywordMention

@pytest.fixture
def crawler():
    return CrawlerService(concurrency=2)

def test_crawler_initial_state(crawler):
    assert crawler.is_running is False
    assert crawler.status == "idle"

@pytest.mark.asyncio
async def test_crawler_lock_prevents_concurrent_runs(crawler):
    call_count = 0
    async def slow_crawl_sources(db):
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.1)
    with patch.object(crawler, "_crawl_all_sources", side_effect=slow_crawl_sources):
        db_mock = AsyncMock()
        task1 = asyncio.create_task(crawler.run(db_mock))
        await asyncio.sleep(0.01)
        with pytest.raises(RuntimeError, match="already running"):
            await crawler.run(db_mock)
        await task1
    assert call_count == 1

@pytest.mark.asyncio
async def test_crawler_status_updates(crawler):
    async def quick_crawl(db):
        pass
    with patch.object(crawler, "_crawl_all_sources", side_effect=quick_crawl):
        db_mock = AsyncMock()
        assert crawler.status == "idle"
        await crawler.run(db_mock)
        assert crawler.status == "idle"


# --- Integration tests for Phase 1 cleaning pipeline ---

@pytest.mark.asyncio
async def test_process_article_sets_cleaned_content(db_session):
    """Phase 1: _process_article should clean HTML and set cleaned_content."""
    source = DataSource(name="test", type="rss", url="http://test.com", trust_level="high")
    db_session.add(source)
    await db_session.flush()
    kw = Keyword(name="AI", aliases=[])
    db_session.add(kw)
    await db_session.flush()

    article_data = {
        "title": "AI is transforming everything",
        "url": "http://test.com/article1",
        "content": "<p>AI is transforming the world.</p><script>bad</script>",
        "published_at": None,
    }
    from app.services.crawler import crawler_service
    await crawler_service._process_article(db_session, source, article_data, [{"id": kw.id, "name": "AI", "aliases": []}])
    await db_session.flush()

    result = await db_session.execute(select(Article).where(Article.url == "http://test.com/article1"))
    article = result.scalar_one()
    assert article.cleaned_content is not None
    assert "bad" not in article.cleaned_content
    assert article.quality_score is not None
    assert article.quality_tag in ("passed", "pending_review", "filtered")


@pytest.mark.asyncio
async def test_filtered_article_skips_matching(db_session):
    """Articles with quality_score < 30 should not create KeywordMention."""
    source = DataSource(name="lowq", type="rss", url="http://spam.com", trust_level="low")
    db_session.add(source)
    await db_session.flush()
    kw = Keyword(name="AI", aliases=[])
    db_session.add(kw)
    await db_session.flush()

    article_data = {
        "title": "AD",
        "url": "http://spam.com/ad/redirect/buy",
        "content": "",
        "published_at": None,
    }
    from app.services.crawler import crawler_service
    await crawler_service._process_article(db_session, source, article_data, [{"id": kw.id, "name": "AI", "aliases": []}])
    await db_session.flush()

    result = await db_session.execute(select(KeywordMention))
    mentions = result.scalars().all()
    assert len(mentions) == 0

    # Article should still be created but marked filtered
    art_result = await db_session.execute(select(Article))
    article = art_result.scalar_one()
    assert article.quality_tag == "filtered"


@pytest.mark.asyncio
async def test_passed_article_title_match_sets_rule_method(db_session):
    """Title strong hit should create KeywordMention with match_method='rule'."""
    source = DataSource(name="good", type="rss", url="http://good.com", trust_level="high")
    db_session.add(source)
    await db_session.flush()
    kw = Keyword(name="AI", aliases=[])
    db_session.add(kw)
    await db_session.flush()

    article_data = {
        "title": "AI is the future of technology",
        "url": "http://good.com/article1",
        "content": "<p>A deep dive into artificial intelligence trends and developments in the tech industry.</p>" * 5,
        "published_at": None,
    }
    from app.services.crawler import crawler_service
    await crawler_service._process_article(db_session, source, article_data, [{"id": kw.id, "name": "AI", "aliases": []}])
    await db_session.flush()

    result = await db_session.execute(select(KeywordMention))
    mention = result.scalar_one()
    assert mention.match_method == "rule"
    assert mention.match_location == "title"


@pytest.mark.asyncio
async def test_content_only_match_marks_needs_llm(db_session):
    """Content-only match should still create mention but mark article for LLM."""
    source = DataSource(name="good", type="rss", url="http://good.com", trust_level="high")
    db_session.add(source)
    await db_session.flush()
    kw = Keyword(name="transformer", aliases=[])
    db_session.add(kw)
    await db_session.flush()

    article_data = {
        "title": "New developments in deep learning research",
        "url": "http://good.com/article2",
        "content": "<p>The transformer architecture has revolutionized natural language processing and continues to evolve rapidly.</p>" * 5,
        "published_at": None,
    }
    from app.services.crawler import crawler_service
    await crawler_service._process_article(db_session, source, article_data, [{"id": kw.id, "name": "transformer", "aliases": []}])
    await db_session.flush()

    result = await db_session.execute(select(Article).where(Article.url == "http://good.com/article2"))
    article = result.scalar_one()
    assert article.needs_llm_matching is True
    assert article.quality_tag == "passed"

    # Content match should still be created
    mentions = (await db_session.execute(select(KeywordMention))).scalars().all()
    assert len(mentions) == 1
    assert mentions[0].match_method == "rule"
