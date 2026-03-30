import asyncio
import json
import logging
import math
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import DataSource, Article, Keyword, KeywordMention, TrendSnapshot
from app.services.rss_parser import parse_rss_feed
from app.services.web_scraper import scrape_web_page
from app.services.keyword_matcher import match_keywords_in_article
from app.services.trend_calculator import calculate_daily_score
from app.config import settings

logger = logging.getLogger(__name__)


class CrawlerService:
    def __init__(self, concurrency=5):
        self._lock = asyncio.Lock()
        self._semaphore = asyncio.Semaphore(concurrency)
        self._status = "idle"
        self._is_running = False

    @property
    def is_running(self):
        return self._is_running

    @property
    def status(self):
        return self._status

    async def run(self, db):
        if self._lock.locked():
            raise RuntimeError("Crawl is already running")
        async with self._lock:
            self._is_running = True
            self._status = "running"
            try:
                await self._crawl_all_sources(db)
            finally:
                self._is_running = False
                self._status = "idle"

    async def _crawl_all_sources(self, db):
        result = await db.execute(
            select(DataSource).where(DataSource.enabled == True, DataSource.status != "disabled")
        )
        sources = result.scalars().all()

        # Filter out sources in exponential backoff
        active_sources = []
        for source in sources:
            if source.consecutive_failures >= settings.failure_backoff_threshold:
                if source.last_fetched_at:
                    from datetime import timedelta
                    backoff_minutes = 60 * (2 ** (source.consecutive_failures - settings.failure_backoff_threshold))
                    next_allowed = source.last_fetched_at + timedelta(minutes=backoff_minutes)
                    if datetime.now(timezone.utc) < next_allowed:
                        logger.info(f"Skipping {source.name} (backoff until {next_allowed})")
                        continue
            active_sources.append(source)

        kw_result = await db.execute(select(Keyword).where(Keyword.is_active == True))
        keywords = [
            {"id": kw.id, "name": kw.name, "aliases": kw.aliases or []}
            for kw in kw_result.scalars().all()
        ]

        tasks = [self._crawl_source(db, source, keywords) for source in active_sources]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _crawl_source(self, db, source, keywords):
        async with self._semaphore:
            try:
                if source.type == "rss":
                    articles = await parse_rss_feed(
                        source.url,
                        proxy_url=source.proxy_url,
                        custom_headers=json.loads(source.custom_headers) if source.custom_headers else None,
                    )
                elif source.type in ("web_scraper", "api"):
                    config = json.loads(source.parser_config) if source.parser_config else {}
                    articles = await scrape_web_page(
                        source.url, config,
                        proxy_url=source.proxy_url,
                        custom_headers=json.loads(source.custom_headers) if source.custom_headers else None,
                    )
                else:
                    logger.warning(f"Unknown source type: {source.type}")
                    return

                for article_data in articles:
                    await self._process_article(db, source, article_data, keywords)

                source.consecutive_failures = 0
                source.status = "normal"
                source.last_fetched_at = datetime.now(timezone.utc)
                source.last_error = None
                await db.commit()

            except Exception as e:
                logger.error(f"Error crawling {source.name}: {e}")
                source.consecutive_failures += 1
                source.last_error = str(e)[:500]
                if source.consecutive_failures >= 3:
                    source.status = "error"
                source.last_fetched_at = datetime.now(timezone.utc)
                await db.commit()

    async def _process_article(self, db, source, article_data, keywords):
        if not article_data.get("url"):
            return

        existing = await db.execute(
            select(Article).where(Article.url == article_data["url"])
        )
        if existing.scalar_one_or_none():
            return

        article = Article(
            source_id=source.id,
            title=article_data["title"],
            url=article_data["url"],
            content=article_data.get("content"),
            published_at=article_data.get("published_at"),
        )
        db.add(article)
        await db.flush()

        matches = match_keywords_in_article(
            title=article.title, content=article.content, keywords=keywords,
        )

        for match in matches:
            mention = KeywordMention(
                keyword_id=match["keyword_id"],
                article_id=article.id,
                match_location=match["match_location"],
                context_snippet=match.get("context_snippet"),
            )
            db.add(mention)

            today = datetime.now(timezone.utc).date()
            snap_result = await db.execute(
                select(TrendSnapshot).where(
                    TrendSnapshot.keyword_id == match["keyword_id"],
                    TrendSnapshot.date == today,
                )
            )
            snapshot = snap_result.scalar_one_or_none()
            new_mention_score = calculate_daily_score(
                [{"match_location": match["match_location"], "source_weight": source.weight}]
            )
            if snapshot:
                snapshot.mention_count += 1
                raw = math.exp(snapshot.score) - 1 if snapshot.score > 0 else 0
                new_raw = raw + (2.0 if match["match_location"] == "title" else 1.0) * source.weight
                snapshot.score = math.log(1 + new_raw)
            else:
                snapshot = TrendSnapshot(
                    keyword_id=match["keyword_id"],
                    date=today,
                    score=new_mention_score,
                    mention_count=1,
                )
                db.add(snapshot)

        await db.commit()


crawler_service = CrawlerService()
