import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.database import Base

# Import all models so metadata is populated
from app.models.article import Article  # noqa: F401
from app.models.data_source import DataSource  # noqa: F401
from app.models.keyword import Keyword  # noqa: F401
from app.models.keyword_mention import KeywordMention  # noqa: F401
from app.models.trend_snapshot import TrendSnapshot  # noqa: F401

@pytest_asyncio.fixture
async def db_engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()

@pytest_asyncio.fixture
async def db_session(db_engine):
    session_factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
