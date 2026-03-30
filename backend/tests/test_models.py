import pytest
from sqlalchemy import inspect
from app.database import Base
from app.models import DataSource, Article, Keyword, KeywordMention, TrendSnapshot

@pytest.mark.asyncio
async def test_create_all_tables(db_engine):
    async with db_engine.connect() as conn:
        tables = await conn.run_sync(lambda sync_conn: inspect(sync_conn).get_table_names())
    assert set(tables) >= {"data_sources", "articles", "keywords", "keyword_mentions", "trend_snapshots"}

@pytest.mark.asyncio
async def test_create_keyword_with_aliases(db_session):
    kw = Keyword(name="AI Agent", aliases=["AI助手", "intelligent agent"], color="#ff0000")
    db_session.add(kw)
    await db_session.commit()
    await db_session.refresh(kw)
    assert kw.id is not None
    assert kw.aliases == ["AI助手", "intelligent agent"]
    assert kw.is_active is True

@pytest.mark.asyncio
async def test_article_url_unique(db_session):
    source = DataSource(name="Test", type="rss", url="http://example.com/rss", weight=1.0)
    db_session.add(source)
    await db_session.commit()
    a1 = Article(source_id=source.id, title="T1", url="http://example.com/1", content="c1")
    db_session.add(a1)
    await db_session.commit()
    a2 = Article(source_id=source.id, title="T2", url="http://example.com/1", content="c2")
    db_session.add(a2)
    with pytest.raises(Exception):
        await db_session.commit()
