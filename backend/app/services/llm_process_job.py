import logging
import math
from datetime import date, datetime, timezone
from sqlalchemy import select, and_
from app.database import async_session
from app.models.article import Article
from app.models.keyword import Keyword
from app.models.keyword_mention import KeywordMention
from app.models.trend_snapshot import TrendSnapshot
from app.models.data_source import DataSource
from app.services.llm_service import llm_service
from app.services.semantic_matcher import SemanticMatcher
from app.services.title_dedup import find_duplicates

logger = logging.getLogger(__name__)


async def run_llm_process():
    """Independent job: process pending articles with LLM.

    Runs as APScheduler job every 10-15 minutes. Handles:
    1. Title similarity dedup
    2. Quality review for pending_review articles (Tier 1 LLM)
    3. Semantic keyword matching for needs_llm_matching articles (Tier 2 LLM)
    """
    async with async_session() as db:
        try:
            await _run_title_dedup(db)
            await _run_quality_review(db)
            await _run_semantic_matching(db)
            await db.commit()
        except Exception as e:
            await db.rollback()
            logger.error(f"LLM process job failed: {e}")


async def _run_title_dedup(db):
    """Step 0: Dedup similar titles among today's new articles."""
    utc_now = datetime.now(timezone.utc)
    today_start = utc_now.replace(hour=0, minute=0, second=0, microsecond=0)
    result = await db.execute(
        select(Article).where(
            and_(
                Article.quality_tag != "filtered",
                Article.fetched_at >= today_start,
            )
        )
    )
    articles = result.scalars().all()
    if len(articles) < 2:
        return

    source_cache = {}
    article_dicts = []
    for a in articles:
        if a.source_id not in source_cache:
            src_result = await db.execute(select(DataSource).where(DataSource.id == a.source_id))
            source_cache[a.source_id] = src_result.scalar_one_or_none()
        src = source_cache.get(a.source_id)
        article_dicts.append({
            "id": a.id,
            "title": a.title,
            "trust_level": src.trust_level if src else "low",
        })

    dupe_ids = find_duplicates(article_dicts)
    for a in articles:
        if a.id in dupe_ids:
            a.quality_tag = "filtered"
    if dupe_ids:
        logger.info(f"Title dedup: filtered {len(dupe_ids)} duplicate articles")


async def _run_quality_review(db):
    """Step 1: LLM review of pending_review articles."""
    result = await db.execute(
        select(Article).where(Article.quality_tag == "pending_review").limit(100)
    )
    articles = result.scalars().all()
    if not articles:
        return

    batch_size = 20
    for i in range(0, len(articles), batch_size):
        batch = articles[i: i + batch_size]
        articles_text = []
        for idx, a in enumerate(batch):
            content_preview = (a.cleaned_content or a.content or "")[:300]
            articles_text.append(f"{idx + 1}. 标题：{a.title}\n   来源摘要：{content_preview}")

        prompt = (
            "你是一个技术内容质量审核员。以下是一批文章，请判断每篇是否为有实质内容的技术文章。\n"
            "排除：广告软文、纯转载无增量信息、过短无意义内容、非技术内容。\n\n"
            + "\n".join(articles_text)
            + '\n\n返回 JSON 数组：[{"index": 1, "verdict": "pass/reject", "reason": "..."}]'
        )

        try:
            results = await llm_service.call_json("tier1", prompt)
            for item in results:
                idx = item.get("index", 0) - 1
                if 0 <= idx < len(batch):
                    if item.get("verdict") == "pass":
                        batch[idx].quality_tag = "passed"
                        batch[idx].needs_llm_matching = True
                    else:
                        batch[idx].quality_tag = "filtered"
        except Exception as e:
            logger.warning(f"Quality review LLM call failed: {e}, keeping articles as pending_review")


async def _run_semantic_matching(db):
    """Step 2: Semantic keyword matching for pending articles."""
    result = await db.execute(
        select(Article).where(Article.needs_llm_matching == True).limit(100)  # noqa: E712
    )
    articles = result.scalars().all()
    if not articles:
        return

    kw_result = await db.execute(select(Keyword).where(Keyword.is_active == True))  # noqa: E712
    keywords = kw_result.scalars().all()
    if not keywords:
        return

    kw_dicts = [{"id": k.id, "name": k.name, "aliases": k.aliases or []} for k in keywords]
    article_dicts = [
        {"id": a.id, "title": a.title, "cleaned_content": a.cleaned_content or a.content or ""}
        for a in articles
    ]

    matcher = SemanticMatcher(llm_service=llm_service)
    matches = await matcher.match_batch(article_dicts, kw_dicts)

    # Create KeywordMention records and update TrendSnapshot
    for match in matches:
        mention = KeywordMention(
            keyword_id=match["keyword_id"],
            article_id=match["article_id"],
            match_location=match["match_location"],
            context_snippet=match.get("context_snippet", ""),
            match_method=match["match_method"],
            match_reason=match.get("match_reason"),
        )
        db.add(mention)

        # Find the article to get its source for weight
        article = next((a for a in articles if a.id == match["article_id"]), None)
        if article:
            src_result = await db.execute(select(DataSource).where(DataSource.id == article.source_id))
            source = src_result.scalar_one_or_none()
            source_weight = source.weight if source else 1.0
            location_weight = 2.0 if match["match_location"] == "title" else 1.0

            # Update TrendSnapshot (use UTC date for consistency)
            today = datetime.now(timezone.utc).date()
            snap_result = await db.execute(
                select(TrendSnapshot).where(
                    and_(TrendSnapshot.keyword_id == match["keyword_id"], TrendSnapshot.date == today)
                )
            )
            snapshot = snap_result.scalar_one_or_none()
            contribution = location_weight * source_weight

            if snapshot:
                raw = math.exp(snapshot.score) - 1
                raw += contribution
                snapshot.score = math.log(1 + raw)
                snapshot.mention_count += 1
            else:
                snapshot = TrendSnapshot(
                    keyword_id=match["keyword_id"],
                    date=today,
                    score=math.log(1 + contribution),
                    mention_count=1,
                )
                db.add(snapshot)

    # Mark articles as processed
    for a in articles:
        a.needs_llm_matching = False
