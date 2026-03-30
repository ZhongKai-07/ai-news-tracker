import asyncio
from datetime import date as date_type

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db, async_session
from app.models import Keyword, Article, KeywordMention, TrendSnapshot
from app.services.keyword_matcher import match_keywords_in_article
from app.services.trend_calculator import calculate_daily_score

router = APIRouter(prefix="/api/keywords", tags=["keywords"])


class KeywordCreate(BaseModel):
    name: str
    aliases: list[str] = []
    color: str | None = None


class KeywordUpdate(BaseModel):
    name: str | None = None
    aliases: list[str] | None = None
    color: str | None = None


class KeywordResponse(BaseModel):
    id: int
    name: str
    aliases: list[str]
    color: str | None
    is_active: bool

    class Config:
        from_attributes = True


@router.post("", response_model=KeywordResponse)
async def create_keyword(data: KeywordCreate, db: AsyncSession = Depends(get_db)):
    kw = Keyword(name=data.name, aliases=data.aliases, color=data.color)
    db.add(kw)
    await db.commit()
    await db.refresh(kw)
    return kw


@router.get("", response_model=list[KeywordResponse])
async def list_keywords(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Keyword).where(Keyword.is_active == True))
    return result.scalars().all()


@router.put("/{keyword_id}", response_model=KeywordResponse)
async def update_keyword(keyword_id: int, data: KeywordUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Keyword).where(Keyword.id == keyword_id))
    kw = result.scalar_one_or_none()
    if not kw:
        raise HTTPException(status_code=404, detail="Keyword not found")
    if data.name is not None and data.name != kw.name:
        existing = await db.execute(select(Keyword).where(Keyword.name == data.name))
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="Keyword name already exists")
        kw.name = data.name
    if data.aliases is not None:
        kw.aliases = data.aliases
    if data.color is not None:
        kw.color = data.color
    await db.commit()
    await db.refresh(kw)
    return kw


@router.delete("/{keyword_id}")
async def delete_keyword(keyword_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Keyword).where(Keyword.id == keyword_id))
    kw = result.scalar_one_or_none()
    if not kw:
        raise HTTPException(status_code=404, detail="Keyword not found")
    kw.is_active = False
    await db.commit()
    return {"status": "deleted", "id": keyword_id}


async def _rescan_keyword_background(keyword_id: int, kw_name: str, kw_aliases: list):
    async with async_session() as db:
        await db.execute(delete(KeywordMention).where(KeywordMention.keyword_id == keyword_id))
        await db.execute(delete(TrendSnapshot).where(TrendSnapshot.keyword_id == keyword_id))

        articles_result = await db.execute(select(Article))
        articles = articles_result.scalars().all()

        kw_data = [{"id": keyword_id, "name": kw_name, "aliases": kw_aliases}]
        daily_mentions: dict[str, list] = {}

        for article in articles:
            matches = match_keywords_in_article(
                title=article.title, content=article.content, keywords=kw_data,
            )
            for match in matches:
                mention = KeywordMention(
                    keyword_id=match["keyword_id"],
                    article_id=article.id,
                    match_location=match["match_location"],
                    context_snippet=match.get("context_snippet"),
                )
                db.add(mention)

                article_date = (article.published_at or article.fetched_at).strftime("%Y-%m-%d")
                if article_date not in daily_mentions:
                    daily_mentions[article_date] = []
                daily_mentions[article_date].append({
                    "match_location": match["match_location"],
                    "source_weight": 1.0,
                })

        for date_str, mentions in daily_mentions.items():
            score = calculate_daily_score(mentions)
            snapshot = TrendSnapshot(
                keyword_id=keyword_id,
                date=date_type.fromisoformat(date_str),
                score=score,
                mention_count=len(mentions),
            )
            db.add(snapshot)

        await db.commit()


@router.post("/{keyword_id}/rescan")
async def rescan_keyword(keyword_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Keyword).where(Keyword.id == keyword_id))
    kw = result.scalar_one_or_none()
    if not kw:
        raise HTTPException(status_code=404, detail="Keyword not found")
    asyncio.create_task(_rescan_keyword_background(keyword_id, kw.name, kw.aliases or []))
    return {"status": "rescan_started", "keyword_id": keyword_id}
