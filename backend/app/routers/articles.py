from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Article, KeywordMention, DataSource

router = APIRouter(prefix="/api", tags=["articles"])


@router.get("/articles")
async def list_articles(
    keyword_id: int | None = None,
    limit: int = Query(default=50, le=200),
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    query = select(Article).order_by(Article.fetched_at.desc())
    if keyword_id:
        query = (
            query.join(KeywordMention, KeywordMention.article_id == Article.id)
            .where(KeywordMention.keyword_id == keyword_id)
        )
    query = query.offset(offset).limit(limit)
    result = await db.execute(query)
    articles = result.scalars().all()
    return [
        {"id": a.id, "title": a.title, "url": a.url, "published_at": str(a.published_at) if a.published_at else None, "source_id": a.source_id}
        for a in articles
    ]


@router.get("/keywords/{keyword_id}/mentions")
async def list_keyword_mentions(
    keyword_id: int,
    limit: int = Query(default=50, le=200),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(KeywordMention, Article, DataSource)
        .join(Article, KeywordMention.article_id == Article.id)
        .join(DataSource, Article.source_id == DataSource.id)
        .where(KeywordMention.keyword_id == keyword_id)
        .order_by(Article.fetched_at.desc())
        .limit(limit)
    )
    return [
        {"id": mention.id, "article_title": article.title, "article_url": article.url, "source_name": source.name, "match_location": mention.match_location, "context_snippet": mention.context_snippet, "published_at": str(article.published_at) if article.published_at else None}
        for mention, article, source in result.all()
    ]
