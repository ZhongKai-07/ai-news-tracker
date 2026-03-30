from datetime import date, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Keyword, TrendSnapshot
from app.services.trend_calculator import detect_trend_direction

router = APIRouter(prefix="/api/trends", tags=["trends"])

PERIOD_DAYS = {"7d": 7, "30d": 30, "90d": 90, "120d": 120}


def _get_date_range(period, start_date, end_date):
    if start_date and end_date:
        return start_date, end_date
    days = PERIOD_DAYS.get(period, 7)
    end = date.today()
    start = end - timedelta(days=days - 1)
    return start, end


@router.get("")
async def get_trends(
    keyword_ids: str | None = None,
    period: str = "7d",
    start_date: date | None = None,
    end_date: date | None = None,
    db: AsyncSession = Depends(get_db),
):
    start, end = _get_date_range(period, start_date, end_date)
    query = select(TrendSnapshot).where(TrendSnapshot.date >= start, TrendSnapshot.date <= end)
    if keyword_ids:
        ids = [int(x) for x in keyword_ids.split(",")]
        query = query.where(TrendSnapshot.keyword_id.in_(ids))
    result = await db.execute(query.order_by(TrendSnapshot.date))
    snaps = result.scalars().all()
    return [
        {"keyword_id": s.keyword_id, "date": str(s.date), "score": s.score, "mention_count": s.mention_count}
        for s in snaps
    ]


@router.get("/heatmap")
async def get_heatmap(period: str = "7d", db: AsyncSession = Depends(get_db)):
    start, end = _get_date_range(period, None, None)
    keywords_result = await db.execute(select(Keyword).where(Keyword.is_active == True))
    keywords = keywords_result.scalars().all()

    heatmap_data = []
    for kw in keywords:
        snaps_result = await db.execute(
            select(TrendSnapshot)
            .where(TrendSnapshot.keyword_id == kw.id, TrendSnapshot.date >= start, TrendSnapshot.date <= end)
            .order_by(TrendSnapshot.date)
        )
        snaps = snaps_result.scalars().all()
        scores = [s.score for s in snaps]
        heatmap_data.append({
            "keyword": {"id": kw.id, "name": kw.name, "color": kw.color},
            "data": [{"date": str(s.date), "score": s.score, "mention_count": s.mention_count} for s in snaps],
            "trend": detect_trend_direction(scores),
        })
    return heatmap_data


@router.get("/hot")
async def get_hot_keywords(db: AsyncSession = Depends(get_db)):
    start = date.today() - timedelta(days=6)
    end = date.today()
    keywords_result = await db.execute(select(Keyword).where(Keyword.is_active == True))
    keywords = keywords_result.scalars().all()

    hot = []
    for kw in keywords:
        snaps_result = await db.execute(
            select(TrendSnapshot)
            .where(TrendSnapshot.keyword_id == kw.id, TrendSnapshot.date >= start, TrendSnapshot.date <= end)
            .order_by(TrendSnapshot.date)
        )
        snaps = snaps_result.scalars().all()
        scores = [s.score for s in snaps]
        trend = detect_trend_direction(scores)
        if trend == "rising":
            hot.append({
                "keyword": {"id": kw.id, "name": kw.name, "color": kw.color},
                "trend": trend,
                "latest_score": scores[-1] if scores else 0,
            })
    hot.sort(key=lambda x: x["latest_score"], reverse=True)
    return hot
