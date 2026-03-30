import asyncio
import json
import logging
import math
from datetime import datetime, timezone, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import DataSource, Article, Keyword, KeywordMention, TrendSnapshot
from app.services.rss_parser import parse_rss_feed
from app.services.web_scraper import scrape_web_page
from app.services.keyword_matcher import match_keywords_in_article
from app.services.trend_calculator import calculate_daily_score
from app.services.content_cleaner import clean_html, complete_data, extract_summary
from app.services.quality_scorer import calculate_quality_score
from app.config import settings

from app.database import async_session

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
        now = datetime.now(timezone.utc)
        active_sources = []
        for source in sources:
            if source.consecutive_failures >= settings.failure_backoff_threshold:
                if source.last_fetched_at:
                    # SQLite returns naive datetimes — make it aware for comparison
                    last_fetched = source.last_fetched_at
                    if last_fetched.tzinfo is None:
                        last_fetched = last_fetched.replace(tzinfo=timezone.utc)
                    backoff_minutes = 60 * (2 ** (source.consecutive_failures - settings.failure_backoff_threshold))
                    next_allowed = last_fetched + timedelta(minutes=backoff_minutes)
                    if now < next_allowed:
                        logger.info(f"Skipping {source.name} (backoff until {next_allowed})")
                        continue
            active_sources.append(source)

        kw_result = await db.execute(select(Keyword).where(Keyword.is_active == True))
        keywords = [
            {"id": kw.id, "name": kw.name, "aliases": kw.aliases or []}
            for kw in kw_result.scalars().all()
        ]

        tasks = [self._crawl_source(source.id, keywords) for source in active_sources]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _crawl_source(self, source_id, keywords):
        async with self._semaphore:
            async with async_session() as db:
                source_result = await db.execute(select(DataSource).where(DataSource.id == source_id))
                source = source_result.scalar_one_or_none()
                if not source:
                    return

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
                    await db.rollback()
                    # Re-fetch source after rollback since the ORM object is stale
                    source_result = await db.execute(select(DataSource).where(DataSource.id == source_id))
                    source = source_result.scalar_one_or_none()
                    if source:
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

        # Phase 1: Data cleaning pipeline (all rule-based, no LLM)
        cleaned_content = clean_html(article_data.get("content"))
        article_data = complete_data(article_data)
        quality_score = calculate_quality_score(
            title=article_data["title"],
            content=cleaned_content or article_data.get("content"),
            url=article_data["url"],
            trust_level=getattr(source, "trust_level", None) or "low",
        )
        summary = extract_summary(cleaned_content) if cleaned_content else ""

        # Determine quality tag
        if quality_score >= 60:
            quality_tag = "passed"
        elif quality_score >= 30:
            quality_tag = "pending_review"
        else:
            quality_tag = "filtered"

        article = Article(
            source_id=source.id,
            title=article_data["title"],
            url=article_data["url"],
            content=article_data.get("content"),
            cleaned_content=cleaned_content or None,
            quality_score=quality_score,
            quality_tag=quality_tag,
            summary=summary or None,
            published_at=article_data.get("published_at"),
            needs_llm_matching=(quality_tag == "pending_review"),
        )
        db.add(article)
        await db.flush()

        # Skip keyword matching for filtered/pending_review articles
        if quality_tag != "passed":
            return

        # Rule-based keyword matching on passed articles
        matches = match_keywords_in_article(
            title=article.title, content=article.cleaned_content or article.content, keywords=keywords,
        )

        has_title_hit = any(m["match_location"] == "title" for m in matches)
        has_content_only = any(m["match_location"] == "content" for m in matches)

        # If no title strong hit, mark for LLM semantic matching
        if not has_title_hit:
            article.needs_llm_matching = True

        for match in matches:
            mention = KeywordMention(
                keyword_id=match["keyword_id"],
                article_id=article.id,
                match_location=match["match_location"],
                context_snippet=match.get("context_snippet"),
                match_method="rule",
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


crawler_service = CrawlerService()
