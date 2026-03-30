import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.crawler import CrawlerService

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
