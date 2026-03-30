from datetime import date, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Keyword, TrendSnapshot, KeywordMention, Article
from app.services.trend_calculator import detect_trend_direction

router = APIRouter(prefix="/api/summary", tags=["summary"])


@router.get("/weekly")
async def weekly_summary(db: AsyncSession = Depends(get_db)):
    end = date.today()
    start = end - timedelta(days=6)

    kw_result = await db.execute(select(Keyword).where(Keyword.is_active == True))
    keywords = kw_result.scalars().all()

    result_keywords = []
    for kw in keywords:
        snaps_result = await db.execute(
            select(TrendSnapshot)
            .where(TrendSnapshot.keyword_id == kw.id, TrendSnapshot.date >= start, TrendSnapshot.date <= end)
            .order_by(TrendSnapshot.date)
        )
        snaps = snaps_result.scalars().all()
        scores = [s.score for s in snaps]
        total_mentions = sum(s.mention_count for s in snaps)
        trend = detect_trend_direction(scores)

        mentions_result = await db.execute(
            select(KeywordMention, Article)
            .join(Article, KeywordMention.article_id == Article.id)
            .where(KeywordMention.keyword_id == kw.id)
            .order_by(Article.fetched_at.desc())
            .limit(3)
        )
        top_articles = [
            {"title": article.title, "url": article.url}
            for mention, article in mentions_result.all()
        ]

        result_keywords.append({
            "name": kw.name, "trend": trend, "mention_count": total_mentions, "top_articles": top_articles,
        })

    return {"keywords": result_keywords, "period": "last_7_days"}
