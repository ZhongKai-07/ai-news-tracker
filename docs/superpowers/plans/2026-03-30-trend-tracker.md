# Trend Tracker Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a keyword/concept trend tracking system that crawls tech news sources via RSS and web scraping, matches keywords, and visualizes trends as heatmaps with multi-keyword color comparison.

**Architecture:** FastAPI async backend with SQLAlchemy ORM (SQLite local / PostgreSQL deploy), asyncio-based concurrent crawling (aiohttp + feedparser + BeautifulSoup), APScheduler for scheduling. React + TypeScript frontend with ECharts for heatmap and trend line visualization.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy 2.0, aiohttp, feedparser, BeautifulSoup4, APScheduler, Alembic | React 18, TypeScript, Vite, ECharts, Axios, React Router

**Spec:** `docs/superpowers/specs/2026-03-30-trend-tracker-design.md`

---

## Chunk 1: Backend Foundation (Database + Config + App Shell)

### Task 1: Project scaffolding and dependencies

**Files:**
- Create: `backend/requirements.txt`
- Create: `backend/app/__init__.py`
- Create: `backend/app/main.py`
- Create: `backend/app/config.py`
- Create: `backend/app/database.py`

- [ ] **Step 1: Create backend directory structure**

```bash
mkdir -p backend/app/models backend/app/routers backend/app/services
mkdir -p backend/tests
touch backend/app/__init__.py backend/app/models/__init__.py
touch backend/app/routers/__init__.py backend/app/services/__init__.py
```

- [ ] **Step 2: Write requirements.txt**

Create `backend/requirements.txt`:

```
fastapi==0.115.0
uvicorn[standard]==0.30.0
sqlalchemy==2.0.35
aiosqlite==0.20.0
alembic==1.13.0
aiohttp==3.10.0
feedparser==6.0.11
beautifulsoup4==4.12.3
apscheduler==3.10.4
pydantic==2.9.0
pydantic-settings==2.5.0
pytest==8.3.0
pytest-asyncio==0.24.0
httpx==0.27.0
```

- [ ] **Step 3: Write config.py**

Create `backend/app/config.py`:

```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite+aiosqlite:///./ai_news.db"
    crawl_concurrency: int = 5
    crawl_default_interval_minutes: int = 360
    failure_backoff_threshold: int = 3

    class Config:
        env_file = ".env"


settings = Settings()
```

- [ ] **Step 4: Write database.py**

Create `backend/app/database.py`:

```python
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

engine = create_async_engine(settings.database_url, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with async_session() as session:
        yield session
```

- [ ] **Step 5: Write main.py (minimal app shell)**

Create `backend/app/main.py`:

```python
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import engine, Base


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(title="AI News Trend Tracker", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
```

- [ ] **Step 6: Verify app starts**

```bash
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
# Visit http://localhost:8000/api/health → {"status": "ok"}
# Visit http://localhost:8000/docs → Swagger UI
# Ctrl+C to stop
```

- [ ] **Step 7: Commit**

```bash
git init
echo "__pycache__/" > .gitignore
echo "*.db" >> .gitignore
echo ".env" >> .gitignore
echo "node_modules/" >> .gitignore
echo "dist/" >> .gitignore
echo ".superpowers/" >> .gitignore
git add .
git commit -m "feat: project scaffolding with FastAPI, SQLAlchemy, config"
```

---

### Task 2: SQLAlchemy models

**Files:**
- Create: `backend/app/models/data_source.py`
- Create: `backend/app/models/article.py`
- Create: `backend/app/models/keyword.py`
- Create: `backend/app/models/keyword_mention.py`
- Create: `backend/app/models/trend_snapshot.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/tests/test_models.py`

- [ ] **Step 1: Write test for model creation**

Create `backend/tests/test_models.py`:

```python
import pytest
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.database import Base
from app.models import DataSource, Article, Keyword, KeywordMention, TrendSnapshot


@pytest.fixture
async def db_engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(db_engine):
    async with async_sessionmaker(db_engine, class_=AsyncSession)() as session:
        yield session


@pytest.mark.asyncio
async def test_create_all_tables(db_engine):
    """All 5 tables should be created."""
    async with db_engine.connect() as conn:
        tables = await conn.run_sync(
            lambda sync_conn: inspect(sync_conn).get_table_names()
        )
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
    with pytest.raises(Exception):  # IntegrityError
        await db_session.commit()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend
python -m pytest tests/test_models.py -v
# Expected: FAIL — ImportError, models don't exist yet
```

- [ ] **Step 3: Write DataSource model**

Create `backend/app/models/data_source.py`:

```python
from datetime import datetime, timezone

from sqlalchemy import String, Float, Boolean, Integer, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class DataSource(Base):
    __tablename__ = "data_sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    type: Mapped[str] = mapped_column(String(20))  # rss | web_scraper | api
    url: Mapped[str] = mapped_column(String(500))
    parser_config: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON
    auth_config: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON
    schedule: Mapped[str | None] = mapped_column(String(100), nullable=True)  # cron
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(20), default="normal")  # normal|error|disabled
    last_fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0)
    proxy_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    custom_headers: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON

    articles = relationship("Article", back_populates="source")
```

- [ ] **Step 4: Write Article model**

Create `backend/app/models/article.py`:

```python
from datetime import datetime, timezone

from sqlalchemy import String, Text, DateTime, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Article(Base):
    __tablename__ = "articles"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(Integer, ForeignKey("data_sources.id"))
    title: Mapped[str] = mapped_column(String(500))
    url: Mapped[str] = mapped_column(String(1000), unique=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    source = relationship("DataSource", back_populates="articles")
    mentions = relationship("KeywordMention", back_populates="article")
```

- [ ] **Step 5: Write Keyword model**

Create `backend/app/models/keyword.py`:

```python
from datetime import datetime, timezone

from sqlalchemy import String, Boolean, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Keyword(Base):
    __tablename__ = "keywords"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True)
    aliases: Mapped[list] = mapped_column(JSON, default=list)
    color: Mapped[str | None] = mapped_column(String(20), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    mentions = relationship("KeywordMention", back_populates="keyword")
    snapshots = relationship("TrendSnapshot", back_populates="keyword")
```

- [ ] **Step 6: Write KeywordMention model**

Create `backend/app/models/keyword_mention.py`:

```python
from sqlalchemy import String, Text, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class KeywordMention(Base):
    __tablename__ = "keyword_mentions"

    id: Mapped[int] = mapped_column(primary_key=True)
    keyword_id: Mapped[int] = mapped_column(Integer, ForeignKey("keywords.id"))
    article_id: Mapped[int] = mapped_column(Integer, ForeignKey("articles.id"))
    match_location: Mapped[str] = mapped_column(String(20))  # title | content
    context_snippet: Mapped[str | None] = mapped_column(Text, nullable=True)

    keyword = relationship("Keyword", back_populates="mentions")
    article = relationship("Article", back_populates="mentions")
```

- [ ] **Step 7: Write TrendSnapshot model**

Create `backend/app/models/trend_snapshot.py`:

```python
from datetime import date

from sqlalchemy import Date, Float, Integer, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class TrendSnapshot(Base):
    __tablename__ = "trend_snapshots"
    __table_args__ = (
        UniqueConstraint("keyword_id", "date", name="uq_keyword_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    keyword_id: Mapped[int] = mapped_column(Integer, ForeignKey("keywords.id"))
    date: Mapped[date] = mapped_column(Date)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    mention_count: Mapped[int] = mapped_column(Integer, default=0)

    keyword = relationship("Keyword", back_populates="snapshots")
```

- [ ] **Step 8: Write models __init__.py**

Create `backend/app/models/__init__.py`:

```python
from app.models.data_source import DataSource
from app.models.article import Article
from app.models.keyword import Keyword
from app.models.keyword_mention import KeywordMention
from app.models.trend_snapshot import TrendSnapshot

__all__ = ["DataSource", "Article", "Keyword", "KeywordMention", "TrendSnapshot"]
```

- [ ] **Step 9: Run tests to verify they pass**

```bash
cd backend
python -m pytest tests/test_models.py -v
# Expected: 3 tests PASS
```

- [ ] **Step 10: Commit**

```bash
git add backend/app/models/ backend/tests/test_models.py
git commit -m "feat: add SQLAlchemy models for all 5 tables"
```

---

## Chunk 2: Core Backend Services

### Task 3: Keyword matcher service

**Files:**
- Create: `backend/app/services/keyword_matcher.py`
- Create: `backend/tests/test_keyword_matcher.py`

- [ ] **Step 1: Write tests for keyword matching**

Create `backend/tests/test_keyword_matcher.py`:

```python
import pytest

from app.services.keyword_matcher import match_keywords_in_article


def test_match_in_title():
    keywords = [
        {"id": 1, "name": "AI Agent", "aliases": ["AI助手"]},
    ]
    matches = match_keywords_in_article(
        title="Building an AI Agent from scratch",
        content="Some unrelated content.",
        keywords=keywords,
    )
    assert len(matches) == 1
    assert matches[0]["keyword_id"] == 1
    assert matches[0]["match_location"] == "title"


def test_match_alias_case_insensitive():
    keywords = [
        {"id": 1, "name": "Spec-driven Design", "aliases": ["规约驱动设计", "specification-driven"]},
    ]
    matches = match_keywords_in_article(
        title="A new approach",
        content="We used SPECIFICATION-DRIVEN methodology in our project.",
        keywords=keywords,
    )
    assert len(matches) == 1
    assert matches[0]["match_location"] == "content"
    assert "SPECIFICATION-DRIVEN" in matches[0]["context_snippet"]


def test_match_both_title_and_content():
    keywords = [
        {"id": 1, "name": "MCP", "aliases": []},
    ]
    matches = match_keywords_in_article(
        title="MCP Protocol Overview",
        content="The MCP standard defines a new way to connect.",
        keywords=keywords,
    )
    # Title match takes priority, only one match per keyword
    assert len(matches) == 1
    assert matches[0]["match_location"] == "title"


def test_no_match():
    keywords = [
        {"id": 1, "name": "Blockchain", "aliases": ["区块链"]},
    ]
    matches = match_keywords_in_article(
        title="Python tips",
        content="How to write better code.",
        keywords=keywords,
    )
    assert len(matches) == 0


def test_multiple_keywords_match():
    keywords = [
        {"id": 1, "name": "AI Agent", "aliases": []},
        {"id": 2, "name": "MCP", "aliases": []},
    ]
    matches = match_keywords_in_article(
        title="AI Agent meets MCP",
        content="Content here.",
        keywords=keywords,
    )
    assert len(matches) == 2


def test_context_snippet_extraction():
    keywords = [
        {"id": 1, "name": "LLM", "aliases": []},
    ]
    content = "A" * 100 + " LLM is powerful " + "B" * 100
    matches = match_keywords_in_article(title="Title", content=content, keywords=keywords)
    assert len(matches) == 1
    snippet = matches[0]["context_snippet"]
    assert "LLM" in snippet
    assert len(snippet) <= 200  # snippet should be bounded
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend
python -m pytest tests/test_keyword_matcher.py -v
# Expected: FAIL — ImportError
```

- [ ] **Step 3: Implement keyword_matcher.py**

Create `backend/app/services/keyword_matcher.py`:

```python
def match_keywords_in_article(
    title: str,
    content: str | None,
    keywords: list[dict],
) -> list[dict]:
    """Match keywords against article title and content.

    Each keyword dict has: id, name, aliases (list[str]).
    Returns list of: {keyword_id, match_location, context_snippet}.
    Title match takes priority over content match (one match per keyword).
    """
    results = []
    title_lower = title.lower() if title else ""
    content_lower = content.lower() if content else ""

    for kw in keywords:
        terms = [kw["name"]] + kw.get("aliases", [])

        # Check title first
        title_matched = any(t.lower() in title_lower for t in terms)
        if title_matched:
            results.append({
                "keyword_id": kw["id"],
                "match_location": "title",
                "context_snippet": title[:200],
            })
            continue

        # Check content
        if not content:
            continue
        for term in terms:
            pos = content_lower.find(term.lower())
            if pos != -1:
                start = max(0, pos - 80)
                end = min(len(content), pos + len(term) + 80)
                snippet = content[start:end]
                results.append({
                    "keyword_id": kw["id"],
                    "match_location": "content",
                    "context_snippet": snippet,
                })
                break

    return results
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend
python -m pytest tests/test_keyword_matcher.py -v
# Expected: 6 tests PASS
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/keyword_matcher.py backend/tests/test_keyword_matcher.py
git commit -m "feat: add keyword matcher with case-insensitive substring matching"
```

---

### Task 4: Trend calculator service

**Files:**
- Create: `backend/app/services/trend_calculator.py`
- Create: `backend/tests/test_trend_calculator.py`

- [ ] **Step 1: Write tests for trend calculation**

Create `backend/tests/test_trend_calculator.py`:

```python
import math
import pytest
from datetime import date

from app.services.trend_calculator import calculate_daily_score, detect_trend_direction


def test_calculate_daily_score_title_weighted():
    mentions = [
        {"match_location": "title", "source_weight": 1.0},
        {"match_location": "content", "source_weight": 1.0},
    ]
    score = calculate_daily_score(mentions)
    # title=2x, content=1x, total raw=3.0, log(1+3)=log(4)
    assert score == pytest.approx(math.log(1 + 3.0), rel=1e-3)


def test_calculate_daily_score_with_source_weight():
    mentions = [
        {"match_location": "title", "source_weight": 2.0},  # 2x * 2.0 = 4
    ]
    score = calculate_daily_score(mentions)
    assert score == pytest.approx(math.log(1 + 4.0), rel=1e-3)


def test_calculate_daily_score_empty():
    assert calculate_daily_score([]) == 0.0


def test_detect_trend_direction_rising():
    # Scores increasing over time
    scores = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0]
    assert detect_trend_direction(scores) == "rising"


def test_detect_trend_direction_falling():
    scores = [7.0, 6.0, 5.0, 4.0, 3.0, 2.0, 1.0]
    assert detect_trend_direction(scores) == "falling"


def test_detect_trend_direction_stable():
    scores = [3.0, 3.1, 2.9, 3.0, 3.1, 2.9, 3.0]
    assert detect_trend_direction(scores) == "stable"


def test_detect_trend_direction_empty():
    assert detect_trend_direction([]) == "stable"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend
python -m pytest tests/test_trend_calculator.py -v
# Expected: FAIL — ImportError
```

- [ ] **Step 3: Implement trend_calculator.py**

Create `backend/app/services/trend_calculator.py`:

```python
import math


TITLE_WEIGHT = 2.0
CONTENT_WEIGHT = 1.0


def calculate_daily_score(mentions: list[dict]) -> float:
    """Calculate trend score for a keyword on a single day.

    Each mention dict: {match_location: "title"|"content", source_weight: float}.
    Returns log-normalized score: log(1 + raw_score).
    """
    if not mentions:
        return 0.0

    raw = 0.0
    for m in mentions:
        location_weight = TITLE_WEIGHT if m["match_location"] == "title" else CONTENT_WEIGHT
        raw += location_weight * m.get("source_weight", 1.0)

    return math.log(1 + raw)


def detect_trend_direction(scores: list[float]) -> str:
    """Detect trend direction from a list of daily scores (oldest first).

    Returns: "rising", "falling", or "stable".
    """
    if len(scores) < 2:
        return "stable"

    mid = len(scores) // 2
    first_half_avg = sum(scores[:mid]) / mid if mid > 0 else 0
    second_half_avg = sum(scores[mid:]) / (len(scores) - mid) if (len(scores) - mid) > 0 else 0

    diff = second_half_avg - first_half_avg
    threshold = 0.3  # sensitivity threshold

    if diff > threshold:
        return "rising"
    elif diff < -threshold:
        return "falling"
    return "stable"
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend
python -m pytest tests/test_trend_calculator.py -v
# Expected: 7 tests PASS
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/trend_calculator.py backend/tests/test_trend_calculator.py
git commit -m "feat: add trend calculator with log normalization and trend detection"
```

---

### Task 5: RSS parser service

**Files:**
- Create: `backend/app/services/rss_parser.py`
- Create: `backend/tests/test_rss_parser.py`

- [ ] **Step 1: Write tests for RSS parsing**

Create `backend/tests/test_rss_parser.py`:

```python
import pytest
from unittest.mock import patch, AsyncMock

from app.services.rss_parser import parse_rss_feed, parse_feed_entry


def test_parse_feed_entry_basic():
    entry = {
        "title": "Test Article",
        "link": "http://example.com/article1",
        "summary": "This is the summary.",
        "published_parsed": (2026, 3, 30, 12, 0, 0, 0, 89, 0),
    }
    result = parse_feed_entry(entry)
    assert result["title"] == "Test Article"
    assert result["url"] == "http://example.com/article1"
    assert result["content"] == "This is the summary."
    assert result["published_at"] is not None


def test_parse_feed_entry_with_content_detail():
    entry = {
        "title": "Test",
        "link": "http://example.com/2",
        "content": [{"value": "<p>Full content here</p>"}],
    }
    result = parse_feed_entry(entry)
    assert "Full content here" in result["content"]


def test_parse_feed_entry_missing_fields():
    entry = {"title": "Only Title", "link": "http://example.com/3"}
    result = parse_feed_entry(entry)
    assert result["title"] == "Only Title"
    assert result["content"] is None
    assert result["published_at"] is None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend
python -m pytest tests/test_rss_parser.py -v
# Expected: FAIL — ImportError
```

- [ ] **Step 3: Implement rss_parser.py**

Create `backend/app/services/rss_parser.py`:

```python
from datetime import datetime, timezone
from time import mktime

import aiohttp
import feedparser
from bs4 import BeautifulSoup


def parse_feed_entry(entry: dict) -> dict:
    """Parse a single feedparser entry into a normalized dict."""
    title = entry.get("title", "")
    url = entry.get("link", "")

    # Prefer full content over summary
    content = None
    if "content" in entry and entry["content"]:
        raw_html = entry["content"][0].get("value", "")
        content = BeautifulSoup(raw_html, "html.parser").get_text(strip=True)
    elif "summary" in entry:
        content = BeautifulSoup(entry["summary"], "html.parser").get_text(strip=True)

    published_at = None
    if "published_parsed" in entry and entry["published_parsed"]:
        try:
            published_at = datetime.fromtimestamp(
                mktime(entry["published_parsed"]), tz=timezone.utc
            )
        except (ValueError, OverflowError):
            pass

    return {
        "title": title,
        "url": url,
        "content": content if content else None,
        "published_at": published_at,
    }


async def parse_rss_feed(
    feed_url: str,
    proxy_url: str | None = None,
    custom_headers: dict | None = None,
) -> list[dict]:
    """Fetch and parse an RSS feed. Returns list of article dicts."""
    headers = {"User-Agent": "AI-News-Tracker/1.0"}
    if custom_headers:
        headers.update(custom_headers)

    async with aiohttp.ClientSession() as session:
        async with session.get(feed_url, headers=headers, proxy=proxy_url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
            text = await resp.text()

    feed = feedparser.parse(text)
    return [parse_feed_entry(e) for e in feed.entries]
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend
python -m pytest tests/test_rss_parser.py -v
# Expected: 3 tests PASS
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/rss_parser.py backend/tests/test_rss_parser.py
git commit -m "feat: add RSS parser with feedparser and HTML content extraction"
```

---

### Task 6: Web scraper service

**Files:**
- Create: `backend/app/services/web_scraper.py`
- Create: `backend/tests/test_web_scraper.py`

- [ ] **Step 1: Write tests for web scraping**

Create `backend/tests/test_web_scraper.py`:

```python
import pytest

from app.services.web_scraper import extract_articles_from_html


def test_extract_with_css_selectors():
    html = """
    <html><body>
      <div class="post">
        <h2><a href="/article/1">First Post</a></h2>
        <p class="summary">Summary of first post</p>
      </div>
      <div class="post">
        <h2><a href="/article/2">Second Post</a></h2>
        <p class="summary">Summary of second post</p>
      </div>
    </body></html>
    """
    config = {
        "item_selector": "div.post",
        "title_selector": "h2 a",
        "url_selector": "h2 a",
        "url_attribute": "href",
        "content_selector": "p.summary",
        "base_url": "http://example.com",
    }
    articles = extract_articles_from_html(html, config)
    assert len(articles) == 2
    assert articles[0]["title"] == "First Post"
    assert articles[0]["url"] == "http://example.com/article/1"
    assert articles[0]["content"] == "Summary of first post"


def test_extract_handles_absolute_urls():
    html = """
    <div class="item">
      <a href="http://full-url.com/post">Full URL Post</a>
    </div>
    """
    config = {
        "item_selector": "div.item",
        "title_selector": "a",
        "url_selector": "a",
        "url_attribute": "href",
        "base_url": "http://example.com",
    }
    articles = extract_articles_from_html(html, config)
    assert articles[0]["url"] == "http://full-url.com/post"


def test_extract_empty_html():
    articles = extract_articles_from_html("", {"item_selector": "div.post", "base_url": ""})
    assert articles == []
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend
python -m pytest tests/test_web_scraper.py -v
# Expected: FAIL — ImportError
```

- [ ] **Step 3: Implement web_scraper.py**

Create `backend/app/services/web_scraper.py`:

```python
from urllib.parse import urljoin

import aiohttp
from bs4 import BeautifulSoup


def extract_articles_from_html(html: str, config: dict) -> list[dict]:
    """Extract articles from HTML using CSS selectors defined in config."""
    if not html:
        return []

    soup = BeautifulSoup(html, "html.parser")
    items = soup.select(config.get("item_selector", ""))
    if not items:
        return []

    base_url = config.get("base_url", "")
    articles = []

    for item in items:
        title_el = item.select_one(config.get("title_selector", "")) if config.get("title_selector") else None
        url_el = item.select_one(config.get("url_selector", "")) if config.get("url_selector") else None
        content_el = item.select_one(config.get("content_selector", "")) if config.get("content_selector") else None

        title = title_el.get_text(strip=True) if title_el else ""
        if not title:
            continue

        raw_url = ""
        if url_el:
            attr = config.get("url_attribute", "href")
            raw_url = url_el.get(attr, "")

        url = raw_url if raw_url.startswith("http") else urljoin(base_url, raw_url)
        content = content_el.get_text(strip=True) if content_el else None

        articles.append({
            "title": title,
            "url": url,
            "content": content,
            "published_at": None,
        })

    return articles


async def scrape_web_page(
    page_url: str,
    config: dict,
    proxy_url: str | None = None,
    custom_headers: dict | None = None,
) -> list[dict]:
    """Fetch a web page and extract articles using config selectors."""
    headers = {"User-Agent": "AI-News-Tracker/1.0"}
    if custom_headers:
        headers.update(custom_headers)

    async with aiohttp.ClientSession() as session:
        async with session.get(page_url, headers=headers, proxy=proxy_url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
            html = await resp.text()

    config["base_url"] = config.get("base_url", page_url.rsplit("/", 1)[0])
    return extract_articles_from_html(html, config)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend
python -m pytest tests/test_web_scraper.py -v
# Expected: 3 tests PASS
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/web_scraper.py backend/tests/test_web_scraper.py
git commit -m "feat: add web scraper with configurable CSS selectors"
```

---

### Task 7: Crawler orchestrator service

**Files:**
- Create: `backend/app/services/crawler.py`
- Create: `backend/tests/test_crawler.py`

- [ ] **Step 1: Write tests for crawler orchestrator**

Create `backend/tests/test_crawler.py`:

```python
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
    """Two concurrent crawl attempts should not both run."""
    call_count = 0

    async def slow_crawl_sources(db):
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.1)

    with patch.object(crawler, "_crawl_all_sources", side_effect=slow_crawl_sources):
        db_mock = AsyncMock()
        task1 = asyncio.create_task(crawler.run(db_mock))
        await asyncio.sleep(0.01)
        # Second run should raise because lock is held
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend
python -m pytest tests/test_crawler.py -v
# Expected: FAIL — ImportError
```

- [ ] **Step 3: Implement crawler.py**

Create `backend/app/services/crawler.py`:

```python
import asyncio
import json
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.models import DataSource, Article, Keyword, KeywordMention, TrendSnapshot
from app.services.rss_parser import parse_rss_feed
from app.services.web_scraper import scrape_web_page
from app.services.keyword_matcher import match_keywords_in_article
from app.services.trend_calculator import calculate_daily_score

logger = logging.getLogger(__name__)


class CrawlerService:
    def __init__(self, concurrency: int = 5):
        self._lock = asyncio.Lock()
        self._semaphore = asyncio.Semaphore(concurrency)
        self._status = "idle"
        self._is_running = False

    @property
    def is_running(self) -> bool:
        return self._is_running

    @property
    def status(self) -> str:
        return self._status

    async def run(self, db: AsyncSession):
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

    async def _crawl_all_sources(self, db: AsyncSession):
        result = await db.execute(
            select(DataSource).where(DataSource.enabled == True, DataSource.status != "disabled")
        )
        sources = result.scalars().all()

        # Load all active keywords for matching
        kw_result = await db.execute(select(Keyword).where(Keyword.is_active == True))
        keywords = [
            {"id": kw.id, "name": kw.name, "aliases": kw.aliases or []}
            for kw in kw_result.scalars().all()
        ]

        tasks = [self._crawl_source(db, source, keywords) for source in sources]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _crawl_source(self, db: AsyncSession, source: DataSource, keywords: list[dict]):
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
                        source.url,
                        config,
                        proxy_url=source.proxy_url,
                        custom_headers=json.loads(source.custom_headers) if source.custom_headers else None,
                    )
                else:
                    logger.warning(f"Unknown source type: {source.type}")
                    return

                for article_data in articles:
                    await self._process_article(db, source, article_data, keywords)

                # Reset failure count on success
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
                await db.commit()

    async def _process_article(
        self, db: AsyncSession, source: DataSource, article_data: dict, keywords: list[dict]
    ):
        if not article_data.get("url"):
            return

        # Insert article with conflict ignore for dedup
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

        # Match keywords
        matches = match_keywords_in_article(
            title=article.title,
            content=article.content,
            keywords=keywords,
        )

        for match in matches:
            mention = KeywordMention(
                keyword_id=match["keyword_id"],
                article_id=article.id,
                match_location=match["match_location"],
                context_snippet=match.get("context_snippet"),
            )
            db.add(mention)

            # Update TrendSnapshot for today (incremental score accumulation)
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
                # Recompute from all mentions for this keyword today
                all_mentions_result = await db.execute(
                    select(KeywordMention)
                    .join(Article, KeywordMention.article_id == Article.id)
                    .where(
                        KeywordMention.keyword_id == match["keyword_id"],
                        Article.source_id == source.id,
                    )
                )
                # Use incremental: add new contribution to existing raw, then re-log
                # Simpler: just recompute score from mention_count and average weight
                import math
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


# Global singleton
crawler_service = CrawlerService()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend
python -m pytest tests/test_crawler.py -v
# Expected: 3 tests PASS
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/crawler.py backend/tests/test_crawler.py
git commit -m "feat: add crawler orchestrator with lock, semaphore, and backoff"
```

---

## Chunk 3: API Routes

### Task 8: Keywords API routes

**Files:**
- Create: `backend/app/routers/keywords.py`
- Create: `backend/tests/test_api_keywords.py`

- [ ] **Step 1: Write API tests**

Create `backend/tests/test_api_keywords.py`:

```python
import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.database import engine, Base


@pytest.fixture(autouse=True)
async def setup_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_create_keyword(client):
    resp = await client.post("/api/keywords", json={
        "name": "AI Agent",
        "aliases": ["AI助手"],
        "color": "#ff0000",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "AI Agent"
    assert data["aliases"] == ["AI助手"]


@pytest.mark.asyncio
async def test_list_keywords(client):
    await client.post("/api/keywords", json={"name": "KW1"})
    await client.post("/api/keywords", json={"name": "KW2"})
    resp = await client.get("/api/keywords")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


@pytest.mark.asyncio
async def test_update_keyword(client):
    create = await client.post("/api/keywords", json={"name": "Old"})
    kw_id = create.json()["id"]
    resp = await client.put(f"/api/keywords/{kw_id}", json={"name": "New", "color": "#00ff00"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "New"


@pytest.mark.asyncio
async def test_soft_delete_keyword(client):
    create = await client.post("/api/keywords", json={"name": "ToDelete"})
    kw_id = create.json()["id"]
    resp = await client.delete(f"/api/keywords/{kw_id}")
    assert resp.status_code == 200
    # Should not appear in active list
    list_resp = await client.get("/api/keywords")
    assert len(list_resp.json()) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend
python -m pytest tests/test_api_keywords.py -v
# Expected: FAIL — route not found
```

- [ ] **Step 3: Implement keywords router**

Create `backend/app/routers/keywords.py`:

```python
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Keyword

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
    if data.name is not None:
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
```

- [ ] **Step 4: Register router in main.py**

Add to `backend/app/main.py` after the CORS middleware:

```python
from app.routers import keywords

app.include_router(keywords.router)
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd backend
python -m pytest tests/test_api_keywords.py -v
# Expected: 4 tests PASS
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/keywords.py backend/tests/test_api_keywords.py backend/app/main.py
git commit -m "feat: add keywords CRUD API with soft delete"
```

---

### Task 9: Sources API routes

**Files:**
- Create: `backend/app/routers/sources.py`
- Create: `backend/tests/test_api_sources.py`

- [ ] **Step 1: Write API tests**

Create `backend/tests/test_api_sources.py`:

```python
import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.database import engine, Base


@pytest.fixture(autouse=True)
async def setup_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_create_source(client):
    resp = await client.post("/api/sources", json={
        "name": "Hacker News",
        "type": "rss",
        "url": "https://news.ycombinator.com/rss",
        "weight": 2.0,
    })
    assert resp.status_code == 200
    assert resp.json()["name"] == "Hacker News"


@pytest.mark.asyncio
async def test_list_sources_with_status(client):
    await client.post("/api/sources", json={"name": "S1", "type": "rss", "url": "http://a.com/rss"})
    resp = await client.get("/api/sources")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["status"] == "normal"


@pytest.mark.asyncio
async def test_update_source(client):
    create = await client.post("/api/sources", json={"name": "Old", "type": "rss", "url": "http://a.com/rss"})
    sid = create.json()["id"]
    resp = await client.put(f"/api/sources/{sid}", json={"name": "Updated", "weight": 3.0})
    assert resp.status_code == 200
    assert resp.json()["name"] == "Updated"


@pytest.mark.asyncio
async def test_delete_source(client):
    create = await client.post("/api/sources", json={"name": "Del", "type": "rss", "url": "http://a.com/rss"})
    sid = create.json()["id"]
    resp = await client.delete(f"/api/sources/{sid}")
    assert resp.status_code == 200
    list_resp = await client.get("/api/sources")
    assert len(list_resp.json()) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend
python -m pytest tests/test_api_sources.py -v
```

- [ ] **Step 3: Implement sources router**

Create `backend/app/routers/sources.py`:

```python
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import DataSource

router = APIRouter(prefix="/api/sources", tags=["sources"])


class SourceCreate(BaseModel):
    name: str
    type: str = "rss"
    url: str
    parser_config: str | None = None
    auth_config: str | None = None
    schedule: str | None = None
    weight: float = 1.0
    proxy_url: str | None = None
    custom_headers: str | None = None


class SourceUpdate(BaseModel):
    name: str | None = None
    type: str | None = None
    url: str | None = None
    parser_config: str | None = None
    auth_config: str | None = None
    schedule: str | None = None
    weight: float | None = None
    enabled: bool | None = None
    proxy_url: str | None = None
    custom_headers: str | None = None


class SourceResponse(BaseModel):
    id: int
    name: str
    type: str
    url: str
    weight: float
    enabled: bool
    status: str
    last_fetched_at: str | None = None
    last_error: str | None = None
    consecutive_failures: int

    class Config:
        from_attributes = True


@router.post("", response_model=SourceResponse)
async def create_source(data: SourceCreate, db: AsyncSession = Depends(get_db)):
    source = DataSource(**data.model_dump())
    db.add(source)
    await db.commit()
    await db.refresh(source)
    return source


@router.get("", response_model=list[SourceResponse])
async def list_sources(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(DataSource))
    return result.scalars().all()


@router.put("/{source_id}", response_model=SourceResponse)
async def update_source(source_id: int, data: SourceUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(DataSource).where(DataSource.id == source_id))
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(source, field, value)
    await db.commit()
    await db.refresh(source)
    return source


@router.delete("/{source_id}")
async def delete_source(source_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(DataSource).where(DataSource.id == source_id))
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    await db.delete(source)
    await db.commit()
    return {"status": "deleted", "id": source_id}
```

- [ ] **Step 4: Register router in main.py**

Add to `backend/app/main.py`:

```python
from app.routers import sources

app.include_router(sources.router)
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd backend
python -m pytest tests/test_api_sources.py -v
# Expected: 4 tests PASS
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/sources.py backend/tests/test_api_sources.py backend/app/main.py
git commit -m "feat: add data sources CRUD API"
```

---

### Task 10: Trends and crawl API routes

**Files:**
- Create: `backend/app/routers/trends.py`
- Create: `backend/app/routers/crawl.py`
- Create: `backend/tests/test_api_trends.py`

- [ ] **Step 1: Write trends API tests**

Create `backend/tests/test_api_trends.py`:

```python
import pytest
from datetime import date, timedelta
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.database import engine, Base, async_session
from app.models import Keyword, TrendSnapshot


@pytest.fixture(autouse=True)
async def setup_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def seed_data():
    async with async_session() as db:
        kw = Keyword(name="AI Agent", aliases=[], color="#ff0000")
        db.add(kw)
        await db.flush()
        today = date.today()
        for i in range(7):
            snap = TrendSnapshot(
                keyword_id=kw.id,
                date=today - timedelta(days=6 - i),
                score=float(i + 1),
                mention_count=i + 1,
            )
            db.add(snap)
        await db.commit()


@pytest.mark.asyncio
async def test_get_heatmap_data(client, seed_data):
    resp = await client.get("/api/trends/heatmap", params={"period": "7d"})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) > 0
    assert "keyword" in data[0]
    assert "data" in data[0]


@pytest.mark.asyncio
async def test_get_trends_with_keyword_filter(client, seed_data):
    resp = await client.get("/api/trends", params={"keyword_ids": "1", "period": "7d"})
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_crawl_status(client):
    resp = await client.get("/api/crawl/status")
    assert resp.status_code == 200
    assert resp.json()["status"] == "idle"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend
python -m pytest tests/test_api_trends.py -v
```

- [ ] **Step 3: Implement trends router**

Create `backend/app/routers/trends.py`:

```python
from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Keyword, TrendSnapshot
from app.services.trend_calculator import detect_trend_direction

router = APIRouter(prefix="/api/trends", tags=["trends"])

PERIOD_DAYS = {"7d": 7, "30d": 30, "90d": 90}


def _get_date_range(period: str, start_date: date | None, end_date: date | None):
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
    query = select(TrendSnapshot).where(
        TrendSnapshot.date >= start, TrendSnapshot.date <= end,
    )
    if keyword_ids:
        ids = [int(x) for x in keyword_ids.split(",")]
        query = query.where(TrendSnapshot.keyword_id.in_(ids))
    result = await db.execute(query.order_by(TrendSnapshot.date))
    return result.scalars().all()


@router.get("/heatmap")
async def get_heatmap(
    period: str = "7d",
    db: AsyncSession = Depends(get_db),
):
    start, end = _get_date_range(period, None, None)

    keywords_result = await db.execute(select(Keyword).where(Keyword.is_active == True))
    keywords = keywords_result.scalars().all()

    heatmap_data = []
    for kw in keywords:
        snaps_result = await db.execute(
            select(TrendSnapshot)
            .where(
                TrendSnapshot.keyword_id == kw.id,
                TrendSnapshot.date >= start,
                TrendSnapshot.date <= end,
            )
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
async def get_hot_keywords(
    db: AsyncSession = Depends(get_db),
):
    """Find keywords with rising trends in the last 7 days."""
    start = date.today() - timedelta(days=6)
    end = date.today()

    keywords_result = await db.execute(select(Keyword).where(Keyword.is_active == True))
    keywords = keywords_result.scalars().all()

    hot = []
    for kw in keywords:
        snaps_result = await db.execute(
            select(TrendSnapshot)
            .where(
                TrendSnapshot.keyword_id == kw.id,
                TrendSnapshot.date >= start,
                TrendSnapshot.date <= end,
            )
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
```

- [ ] **Step 4: Implement crawl router**

Create `backend/app/routers/crawl.py`:

```python
import asyncio

from fastapi import APIRouter, HTTPException

from app.database import async_session
from app.services.crawler import crawler_service

router = APIRouter(prefix="/api/crawl", tags=["crawl"])


async def _run_crawl_in_background():
    """Run crawl with its own DB session, independent of HTTP request lifecycle."""
    async with async_session() as db:
        await crawler_service.run(db)


@router.post("/trigger")
async def trigger_crawl():
    if crawler_service.is_running:
        raise HTTPException(status_code=409, detail="Crawl is already running")
    asyncio.create_task(_run_crawl_in_background())
    return {"status": "started"}


@router.get("/status")
async def crawl_status():
    return {"status": crawler_service.status}
```

- [ ] **Step 5: Register routers in main.py**

Add to `backend/app/main.py`:

```python
from app.routers import trends, crawl

app.include_router(trends.router)
app.include_router(crawl.router)
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
cd backend
python -m pytest tests/test_api_trends.py -v
# Expected: 3 tests PASS
```

- [ ] **Step 7: Commit**

```bash
git add backend/app/routers/trends.py backend/app/routers/crawl.py backend/tests/test_api_trends.py backend/app/main.py
git commit -m "feat: add trends heatmap API and crawl trigger with 409 guard"
```

---

### Task 11: Scheduler setup and keyword rescan API

**Files:**
- Create: `backend/app/scheduler.py`
- Modify: `backend/app/main.py` (add scheduler lifecycle)
- Modify: `backend/app/routers/keywords.py` (add rescan endpoint)

- [ ] **Step 1: Implement scheduler.py**

Create `backend/app/scheduler.py`:

```python
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.database import async_session
from app.services.crawler import crawler_service

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler()


async def scheduled_crawl():
    """Run by APScheduler on a cron schedule."""
    async with async_session() as db:
        try:
            await crawler_service.run(db)
        except RuntimeError:
            logger.info("Skipping scheduled crawl — already running")


def setup_scheduler():
    scheduler.add_job(
        scheduled_crawl,
        "interval",
        hours=6,
        id="default_crawl",
        replace_existing=True,
    )
    scheduler.start()
```

- [ ] **Step 2: Add scheduler to app lifespan**

Update `backend/app/main.py` lifespan:

```python
from app.scheduler import setup_scheduler, scheduler

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    setup_scheduler()
    yield
    scheduler.shutdown()
    await engine.dispose()
```

- [ ] **Step 3: Add rescan endpoint to keywords router**

Append to `backend/app/routers/keywords.py`:

```python
import asyncio
from datetime import date as date_type

from sqlalchemy import delete

from app.database import async_session
from app.models import Article, KeywordMention, TrendSnapshot
from app.services.keyword_matcher import match_keywords_in_article
from app.services.trend_calculator import calculate_daily_score


async def _rescan_keyword_background(keyword_id: int, kw_name: str, kw_aliases: list):
    """Background task: rescan all articles for a keyword. Uses its own DB session."""
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
```

- [ ] **Step 4: Run all backend tests**

```bash
cd backend
python -m pytest tests/ -v
# Expected: all tests PASS
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/scheduler.py backend/app/main.py backend/app/routers/keywords.py
git commit -m "feat: add APScheduler, keyword rescan/backfill endpoint"
```

---

### Task 11b: Articles and mentions API + exponential backoff

**Files:**
- Create: `backend/app/routers/articles.py`
- Modify: `backend/app/services/crawler.py` (add backoff logic)
- Modify: `backend/app/main.py` (register articles router)
- Modify: `backend/app/routers/keywords.py` (add duplicate name guard)

- [ ] **Step 1: Implement articles router**

Create `backend/app/routers/articles.py`:

```python
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Article, KeywordMention

router = APIRouter(prefix="/api", tags=["articles"])


@router.get("/articles")
async def list_articles(
    keyword_id: int | None = None,
    limit: int = Query(default=50, le=200),
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    query = select(Article).order_by(Article.published_at.desc())
    if keyword_id:
        query = (
            query.join(KeywordMention, KeywordMention.article_id == Article.id)
            .where(KeywordMention.keyword_id == keyword_id)
        )
    query = query.offset(offset).limit(limit)
    result = await db.execute(query)
    articles = result.scalars().all()
    return [
        {
            "id": a.id,
            "title": a.title,
            "url": a.url,
            "published_at": str(a.published_at) if a.published_at else None,
            "source_id": a.source_id,
        }
        for a in articles
    ]


@router.get("/keywords/{keyword_id}/mentions")
async def list_keyword_mentions(
    keyword_id: int,
    limit: int = Query(default=50, le=200),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(KeywordMention, Article)
        .join(Article, KeywordMention.article_id == Article.id)
        .where(KeywordMention.keyword_id == keyword_id)
        .order_by(Article.published_at.desc())
        .limit(limit)
    )
    return [
        {
            "id": mention.id,
            "article_title": article.title,
            "article_url": article.url,
            "match_location": mention.match_location,
            "context_snippet": mention.context_snippet,
            "published_at": str(article.published_at) if article.published_at else None,
        }
        for mention, article in result.all()
    ]
```

- [ ] **Step 2: Register articles router in main.py**

Add to `backend/app/main.py`:

```python
from app.routers import articles

app.include_router(articles.router)
```

- [ ] **Step 3: Add exponential backoff to crawler**

In `backend/app/services/crawler.py`, update `_crawl_all_sources` to skip sources in backoff:

```python
# Add this import at top
from app.config import settings

# In _crawl_all_sources, before creating tasks, filter out backed-off sources:
async def _crawl_all_sources(self, db: AsyncSession):
    result = await db.execute(
        select(DataSource).where(DataSource.enabled == True, DataSource.status != "disabled")
    )
    sources = result.scalars().all()

    # Filter out sources in exponential backoff
    active_sources = []
    for source in sources:
        if source.consecutive_failures >= settings.failure_backoff_threshold:
            # Exponential backoff: skip if not enough time has passed
            if source.last_fetched_at:
                from datetime import datetime, timezone, timedelta
                backoff_minutes = 60 * (2 ** (source.consecutive_failures - settings.failure_backoff_threshold))
                next_allowed = source.last_fetched_at + timedelta(minutes=backoff_minutes)
                if datetime.now(timezone.utc) < next_allowed:
                    logger.info(f"Skipping {source.name} (backoff until {next_allowed})")
                    continue
        active_sources.append(source)

    # ... rest of method uses active_sources instead of sources
```

- [ ] **Step 4: Add duplicate name guard to keyword update**

In `backend/app/routers/keywords.py`, update the `update_keyword` handler:

```python
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
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/articles.py backend/app/services/crawler.py backend/app/routers/keywords.py backend/app/main.py
git commit -m "feat: add articles/mentions API, exponential backoff, duplicate name guard"
```

---

## Chunk 4: Frontend Foundation

### Task 12: Frontend scaffolding

**Files:**
- Create: `frontend/` (via Vite)
- Create: `frontend/src/api/client.ts`
- Create: `frontend/src/App.tsx` (with routing)

- [ ] **Step 1: Create Vite React TypeScript project**

```bash
cd "E:/AI use case/ai-news"
npm create vite@latest frontend -- --template react-ts
cd frontend
npm install
npm install axios react-router-dom echarts echarts-for-react
npm install -D @types/react-router-dom
```

- [ ] **Step 2: Create API client**

Create `frontend/src/api/client.ts`:

```typescript
import axios from "axios";

const api = axios.create({
  baseURL: "http://localhost:8000/api",
});

export interface Keyword {
  id: number;
  name: string;
  aliases: string[];
  color: string | null;
  is_active: boolean;
}

export interface DataSource {
  id: number;
  name: string;
  type: string;
  url: string;
  weight: number;
  enabled: boolean;
  status: string;
  last_fetched_at: string | null;
  last_error: string | null;
  consecutive_failures: number;
}

export interface TrendDataPoint {
  date: string;
  score: number;
  mention_count: number;
}

export interface HeatmapSeries {
  keyword: { id: number; name: string; color: string | null };
  data: TrendDataPoint[];
  trend: "rising" | "falling" | "stable";
}

export const keywordsApi = {
  list: () => api.get<Keyword[]>("/keywords").then((r) => r.data),
  create: (data: { name: string; aliases?: string[]; color?: string }) =>
    api.post<Keyword>("/keywords", data).then((r) => r.data),
  update: (id: number, data: Partial<Keyword>) =>
    api.put<Keyword>(`/keywords/${id}`, data).then((r) => r.data),
  delete: (id: number) => api.delete(`/keywords/${id}`),
  rescan: (id: number) =>
    api.post(`/keywords/${id}/rescan`).then((r) => r.data),
};

export const sourcesApi = {
  list: () => api.get<DataSource[]>("/sources").then((r) => r.data),
  create: (data: Partial<DataSource>) =>
    api.post<DataSource>("/sources", data).then((r) => r.data),
  update: (id: number, data: Partial<DataSource>) =>
    api.put<DataSource>(`/sources/${id}`, data).then((r) => r.data),
  delete: (id: number) => api.delete(`/sources/${id}`),
};

export const trendsApi = {
  heatmap: (period: string = "7d") =>
    api
      .get<HeatmapSeries[]>("/trends/heatmap", { params: { period } })
      .then((r) => r.data),
  hot: () =>
    api.get("/trends/hot").then((r) => r.data),
  weekly: () =>
    api.get("/summary/weekly").then((r) => r.data),
};

export const articlesApi = {
  list: (keyword_id?: number) =>
    api
      .get("/articles", { params: keyword_id ? { keyword_id } : {} })
      .then((r) => r.data),
  mentions: (keyword_id: number) =>
    api.get(`/keywords/${keyword_id}/mentions`).then((r) => r.data),
};

export const crawlApi = {
  trigger: () => api.post("/crawl/trigger").then((r) => r.data),
  status: () =>
    api.get<{ status: string }>("/crawl/status").then((r) => r.data),
};
```

- [ ] **Step 3: Set up App.tsx with routing**

Replace `frontend/src/App.tsx`:

```tsx
import { BrowserRouter, Routes, Route, NavLink } from "react-router-dom";
import Dashboard from "./pages/Dashboard";
import TrendAnalysis from "./pages/TrendAnalysis";
import KeywordManage from "./pages/KeywordManage";
import SourceManage from "./pages/SourceManage";
import "./App.css";

function App() {
  return (
    <BrowserRouter>
      <div className="app">
        <nav className="sidebar">
          <h2>AI News Tracker</h2>
          <NavLink to="/">Dashboard</NavLink>
          <NavLink to="/trends">Trends</NavLink>
          <NavLink to="/keywords">Keywords</NavLink>
          <NavLink to="/sources">Sources</NavLink>
        </nav>
        <main className="main-content">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/trends" element={<TrendAnalysis />} />
            <Route path="/keywords" element={<KeywordManage />} />
            <Route path="/sources" element={<SourceManage />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}

export default App;
```

- [ ] **Step 4: Create placeholder pages**

Create `frontend/src/pages/Dashboard.tsx`:

```tsx
export default function Dashboard() {
  return <div><h1>Dashboard</h1><p>Coming soon...</p></div>;
}
```

Create `frontend/src/pages/TrendAnalysis.tsx`:

```tsx
export default function TrendAnalysis() {
  return <div><h1>Trend Analysis</h1><p>Coming soon...</p></div>;
}
```

Create `frontend/src/pages/KeywordManage.tsx`:

```tsx
export default function KeywordManage() {
  return <div><h1>Keyword Management</h1><p>Coming soon...</p></div>;
}
```

Create `frontend/src/pages/SourceManage.tsx`:

```tsx
export default function SourceManage() {
  return <div><h1>Source Management</h1><p>Coming soon...</p></div>;
}
```

- [ ] **Step 5: Add basic app CSS**

Replace `frontend/src/App.css`:

```css
.app {
  display: flex;
  min-height: 100vh;
}

.sidebar {
  width: 200px;
  background: #1a1a2e;
  color: white;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.sidebar h2 {
  font-size: 16px;
  margin-bottom: 20px;
}

.sidebar a {
  color: #8888aa;
  text-decoration: none;
  padding: 8px 12px;
  border-radius: 6px;
}

.sidebar a.active {
  background: #16213e;
  color: white;
}

.main-content {
  flex: 1;
  padding: 24px;
  background: #f5f5f5;
}
```

- [ ] **Step 6: Verify frontend starts**

```bash
cd frontend
npm run dev
# Visit http://localhost:5173 → should see sidebar with nav links
# Ctrl+C to stop
```

- [ ] **Step 7: Commit**

```bash
git add frontend/
git commit -m "feat: frontend scaffolding with React Router and API client"
```

---

## Chunk 5: Frontend Feature Pages

### Task 13: Keyword management page

**Files:**
- Modify: `frontend/src/pages/KeywordManage.tsx`

- [ ] **Step 1: Implement keyword management page**

Replace `frontend/src/pages/KeywordManage.tsx`:

```tsx
import { useEffect, useState } from "react";
import { keywordsApi, Keyword } from "../api/client";

const DEFAULT_COLORS = ["#e74c3c", "#3498db", "#2ecc71", "#9b59b6", "#e67e22", "#1abc9c", "#f39c12", "#e91e63"];

export default function KeywordManage() {
  const [keywords, setKeywords] = useState<Keyword[]>([]);
  const [name, setName] = useState("");
  const [aliases, setAliases] = useState("");
  const [color, setColor] = useState(DEFAULT_COLORS[0]);
  const [editingId, setEditingId] = useState<number | null>(null);

  const load = () => keywordsApi.list().then(setKeywords);
  useEffect(() => { load(); }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const data = {
      name,
      aliases: aliases ? aliases.split(",").map((s) => s.trim()) : [],
      color,
    };
    if (editingId) {
      await keywordsApi.update(editingId, data);
    } else {
      await keywordsApi.create(data);
    }
    setName(""); setAliases(""); setEditingId(null);
    setColor(DEFAULT_COLORS[keywords.length % DEFAULT_COLORS.length]);
    load();
  };

  const handleEdit = (kw: Keyword) => {
    setEditingId(kw.id);
    setName(kw.name);
    setAliases(kw.aliases.join(", "));
    setColor(kw.color || DEFAULT_COLORS[0]);
  };

  const handleDelete = async (id: number) => {
    if (confirm("Delete this keyword?")) {
      await keywordsApi.delete(id);
      load();
    }
  };

  const handleRescan = async (id: number) => {
    await keywordsApi.rescan(id);
    alert("Rescan complete");
  };

  return (
    <div>
      <h1>Keyword Management</h1>
      <form onSubmit={handleSubmit} style={{ display: "flex", gap: 8, marginBottom: 24 }}>
        <input placeholder="Keyword name" value={name} onChange={(e) => setName(e.target.value)} required />
        <input placeholder="Aliases (comma separated)" value={aliases} onChange={(e) => setAliases(e.target.value)} />
        <input type="color" value={color} onChange={(e) => setColor(e.target.value)} />
        <button type="submit">{editingId ? "Update" : "Add"}</button>
        {editingId && <button type="button" onClick={() => { setEditingId(null); setName(""); setAliases(""); }}>Cancel</button>}
      </form>

      <table style={{ width: "100%", borderCollapse: "collapse" }}>
        <thead>
          <tr>
            <th style={{ textAlign: "left", padding: 8 }}>Color</th>
            <th style={{ textAlign: "left", padding: 8 }}>Name</th>
            <th style={{ textAlign: "left", padding: 8 }}>Aliases</th>
            <th style={{ textAlign: "left", padding: 8 }}>Actions</th>
          </tr>
        </thead>
        <tbody>
          {keywords.map((kw) => (
            <tr key={kw.id} style={{ borderTop: "1px solid #ddd" }}>
              <td style={{ padding: 8 }}>
                <span style={{ display: "inline-block", width: 16, height: 16, borderRadius: "50%", background: kw.color || "#ccc" }} />
              </td>
              <td style={{ padding: 8 }}>{kw.name}</td>
              <td style={{ padding: 8 }}>{kw.aliases.join(", ")}</td>
              <td style={{ padding: 8, display: "flex", gap: 8 }}>
                <button onClick={() => handleEdit(kw)}>Edit</button>
                <button onClick={() => handleRescan(kw.id)}>Rescan</button>
                <button onClick={() => handleDelete(kw.id)}>Delete</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

- [ ] **Step 2: Verify page works**

```bash
# Start backend: cd backend && python -m uvicorn app.main:app --reload --port 8000
# Start frontend: cd frontend && npm run dev
# Visit http://localhost:5173/keywords → add/edit/delete keywords
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/KeywordManage.tsx
git commit -m "feat: keyword management page with CRUD and rescan"
```

---

### Task 14: Source management page

**Files:**
- Modify: `frontend/src/pages/SourceManage.tsx`

- [ ] **Step 1: Implement source management page**

Replace `frontend/src/pages/SourceManage.tsx`:

```tsx
import { useEffect, useState } from "react";
import { sourcesApi, crawlApi, DataSource } from "../api/client";

export default function SourceManage() {
  const [sources, setSources] = useState<DataSource[]>([]);
  const [name, setName] = useState("");
  const [type, setType] = useState("rss");
  const [url, setUrl] = useState("");
  const [weight, setWeight] = useState("1.0");
  const [crawlStatus, setCrawlStatus] = useState("idle");

  const load = () => sourcesApi.list().then(setSources);
  useEffect(() => { load(); }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    await sourcesApi.create({ name, type, url, weight: parseFloat(weight) });
    setName(""); setUrl(""); setWeight("1.0");
    load();
  };

  const handleDelete = async (id: number) => {
    if (confirm("Delete this source?")) {
      await sourcesApi.delete(id);
      load();
    }
  };

  const handleCrawl = async () => {
    try {
      await crawlApi.trigger();
      setCrawlStatus("running");
      const poll = setInterval(async () => {
        const s = await crawlApi.status();
        setCrawlStatus(s.status);
        if (s.status === "idle") {
          clearInterval(poll);
          load();
        }
      }, 2000);
    } catch {
      alert("Crawl already running");
    }
  };

  const statusColor = (s: string) =>
    s === "normal" ? "#2ecc71" : s === "error" ? "#e74c3c" : "#95a5a6";

  return (
    <div>
      <h1>Source Management</h1>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 16 }}>
        <form onSubmit={handleSubmit} style={{ display: "flex", gap: 8 }}>
          <input placeholder="Name" value={name} onChange={(e) => setName(e.target.value)} required />
          <select value={type} onChange={(e) => setType(e.target.value)}>
            <option value="rss">RSS</option>
            <option value="web_scraper">Web Scraper</option>
            <option value="api">API</option>
          </select>
          <input placeholder="URL" value={url} onChange={(e) => setUrl(e.target.value)} required style={{ width: 300 }} />
          <input placeholder="Weight" value={weight} onChange={(e) => setWeight(e.target.value)} style={{ width: 60 }} />
          <button type="submit">Add Source</button>
        </form>
        <button onClick={handleCrawl} disabled={crawlStatus === "running"}>
          {crawlStatus === "running" ? "Crawling..." : "Trigger Crawl"}
        </button>
      </div>

      <table style={{ width: "100%", borderCollapse: "collapse" }}>
        <thead>
          <tr>
            <th style={{ textAlign: "left", padding: 8 }}>Status</th>
            <th style={{ textAlign: "left", padding: 8 }}>Name</th>
            <th style={{ textAlign: "left", padding: 8 }}>Type</th>
            <th style={{ textAlign: "left", padding: 8 }}>URL</th>
            <th style={{ textAlign: "left", padding: 8 }}>Weight</th>
            <th style={{ textAlign: "left", padding: 8 }}>Last Fetched</th>
            <th style={{ textAlign: "left", padding: 8 }}>Failures</th>
            <th style={{ textAlign: "left", padding: 8 }}>Actions</th>
          </tr>
        </thead>
        <tbody>
          {sources.map((s) => (
            <tr key={s.id} style={{ borderTop: "1px solid #ddd" }}>
              <td style={{ padding: 8 }}>
                <span style={{ color: statusColor(s.status), fontWeight: "bold" }}>{s.status}</span>
              </td>
              <td style={{ padding: 8 }}>{s.name}</td>
              <td style={{ padding: 8 }}>{s.type}</td>
              <td style={{ padding: 8, maxWidth: 200, overflow: "hidden", textOverflow: "ellipsis" }}>{s.url}</td>
              <td style={{ padding: 8 }}>{s.weight}</td>
              <td style={{ padding: 8 }}>{s.last_fetched_at || "Never"}</td>
              <td style={{ padding: 8 }}>{s.consecutive_failures}</td>
              <td style={{ padding: 8 }}>
                <button onClick={() => handleDelete(s.id)}>Delete</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

- [ ] **Step 2: Verify and commit**

```bash
# Visit http://localhost:5173/sources → add sources, trigger crawl
git add frontend/src/pages/SourceManage.tsx
git commit -m "feat: source management page with crawl trigger"
```

---

### Task 15: Heatmap and trend line chart components

**Files:**
- Create: `frontend/src/components/HeatmapChart.tsx`
- Create: `frontend/src/components/TrendLineChart.tsx`
- Create: `frontend/src/components/KeywordSelector.tsx`

- [ ] **Step 1: Implement HeatmapChart component**

Create `frontend/src/components/HeatmapChart.tsx`:

```tsx
import ReactECharts from "echarts-for-react";
import { HeatmapSeries } from "../api/client";

interface Props {
  data: HeatmapSeries[];
}

export default function HeatmapChart({ data }: Props) {
  if (!data.length) return <p>No data yet. Add keywords and trigger a crawl.</p>;

  // Collect all unique dates
  const allDates = [...new Set(data.flatMap((s) => s.data.map((d) => d.date)))].sort();
  const keywords = data.map((s) => s.keyword.name);

  // Build heatmap data: [dateIndex, keywordIndex, score]
  const heatmapData: number[][] = [];
  let maxScore = 0;
  data.forEach((series, kwIdx) => {
    series.data.forEach((point) => {
      const dateIdx = allDates.indexOf(point.date);
      heatmapData.push([dateIdx, kwIdx, point.score]);
      if (point.score > maxScore) maxScore = point.score;
    });
  });

  const option = {
    tooltip: {
      position: "top",
      formatter: (params: any) => {
        const [dateIdx, kwIdx, score] = params.data;
        const series = data[kwIdx];
        const point = series.data.find((d) => d.date === allDates[dateIdx]);
        return `${series.keyword.name}<br/>${allDates[dateIdx]}<br/>Score: ${score.toFixed(2)}<br/>Mentions: ${point?.mention_count || 0}`;
      },
    },
    grid: { top: 30, bottom: 60, left: 120, right: 30 },
    xAxis: { type: "category", data: allDates, splitArea: { show: true } },
    yAxis: { type: "category", data: keywords, splitArea: { show: true } },
    visualMap: {
      min: 0,
      max: maxScore || 1,
      calculable: true,
      orient: "horizontal",
      left: "center",
      bottom: 0,
      inRange: { color: ["#ebedf0", "#9be9a8", "#40c463", "#30a14e", "#216e39"] },
    },
    series: [{
      type: "heatmap",
      data: heatmapData,
      label: { show: false },
      emphasis: { itemStyle: { shadowBlur: 10, shadowColor: "rgba(0,0,0,0.5)" } },
    }],
  };

  return <ReactECharts option={option} style={{ height: 200 + keywords.length * 40 }} />;
}
```

- [ ] **Step 2: Implement TrendLineChart component**

Create `frontend/src/components/TrendLineChart.tsx`:

```tsx
import ReactECharts from "echarts-for-react";
import { HeatmapSeries } from "../api/client";

interface Props {
  data: HeatmapSeries[];
}

export default function TrendLineChart({ data }: Props) {
  if (!data.length) return <p>No data yet.</p>;

  const allDates = [...new Set(data.flatMap((s) => s.data.map((d) => d.date)))].sort();

  const series = data.map((s) => {
    const dateMap = new Map(s.data.map((d) => [d.date, d.score]));
    return {
      name: s.keyword.name,
      type: "line" as const,
      smooth: true,
      data: allDates.map((d) => dateMap.get(d) ?? 0),
      itemStyle: { color: s.keyword.color || undefined },
      lineStyle: { color: s.keyword.color || undefined },
    };
  });

  const option = {
    tooltip: { trigger: "axis" },
    legend: { data: data.map((s) => s.keyword.name) },
    grid: { top: 40, bottom: 30, left: 50, right: 30 },
    xAxis: { type: "category", data: allDates },
    yAxis: { type: "value", name: "Score" },
    series,
  };

  return <ReactECharts option={option} style={{ height: 400 }} />;
}
```

- [ ] **Step 3: Implement KeywordSelector component**

Create `frontend/src/components/KeywordSelector.tsx`:

```tsx
import { Keyword } from "../api/client";

interface Props {
  keywords: Keyword[];
  selected: number[];
  onChange: (ids: number[]) => void;
}

export default function KeywordSelector({ keywords, selected, onChange }: Props) {
  const toggle = (id: number) => {
    if (selected.includes(id)) {
      onChange(selected.filter((x) => x !== id));
    } else {
      onChange([...selected, id]);
    }
  };

  return (
    <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 16 }}>
      {keywords.map((kw) => (
        <label key={kw.id} style={{ display: "flex", alignItems: "center", gap: 4, cursor: "pointer" }}>
          <input type="checkbox" checked={selected.includes(kw.id)} onChange={() => toggle(kw.id)} />
          <span style={{ width: 12, height: 12, borderRadius: "50%", background: kw.color || "#ccc", display: "inline-block" }} />
          {kw.name}
        </label>
      ))}
    </div>
  );
}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/
git commit -m "feat: add HeatmapChart, TrendLineChart, and KeywordSelector components"
```

---

### Task 16: Dashboard page

**Files:**
- Modify: `frontend/src/pages/Dashboard.tsx`

- [ ] **Step 1: Implement Dashboard**

Replace `frontend/src/pages/Dashboard.tsx`:

```tsx
import { useEffect, useState } from "react";
import { trendsApi, keywordsApi, HeatmapSeries, Keyword } from "../api/client";
import HeatmapChart from "../components/HeatmapChart";

export default function Dashboard() {
  const [heatmapData, setHeatmapData] = useState<HeatmapSeries[]>([]);
  const [hotKeywords, setHotKeywords] = useState<any[]>([]);
  const [keywords, setKeywords] = useState<Keyword[]>([]);

  useEffect(() => {
    trendsApi.heatmap("7d").then(setHeatmapData);
    trendsApi.hot().then(setHotKeywords);
    keywordsApi.list().then(setKeywords);
  }, []);

  const trendArrow = (trend: string) =>
    trend === "rising" ? "↑" : trend === "falling" ? "↓" : "→";

  return (
    <div>
      <h1>Dashboard</h1>

      {/* Keyword overview cards */}
      <div style={{ display: "flex", gap: 12, marginBottom: 24, flexWrap: "wrap" }}>
        {heatmapData.map((series) => (
          <div key={series.keyword.id} style={{
            background: "white", padding: 16, borderRadius: 8, minWidth: 150,
            borderLeft: `4px solid ${series.keyword.color || "#ccc"}`,
          }}>
            <div style={{ fontWeight: "bold" }}>{series.keyword.name}</div>
            <div style={{ fontSize: 24 }}>
              {trendArrow(series.trend)}
              <span style={{ fontSize: 14, marginLeft: 8, color: "#666" }}>{series.trend}</span>
            </div>
          </div>
        ))}
      </div>

      {/* Hot topics */}
      {hotKeywords.length > 0 && (
        <div style={{ marginBottom: 24, padding: 12, background: "#fff3e0", borderRadius: 8 }}>
          <strong>Hot Topics: </strong>
          {hotKeywords.map((h: any) => (
            <span key={h.keyword.id} style={{ marginRight: 12, color: h.keyword.color }}>
              {h.keyword.name} ↑
            </span>
          ))}
        </div>
      )}

      {/* 7-day heatmap */}
      <div style={{ background: "white", padding: 16, borderRadius: 8 }}>
        <h3>Last 7 Days</h3>
        <HeatmapChart data={heatmapData} />
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify and commit**

```bash
git add frontend/src/pages/Dashboard.tsx
git commit -m "feat: dashboard with keyword cards, hot topics, and 7-day heatmap"
```

---

### Task 17: Trend analysis page

**Files:**
- Modify: `frontend/src/pages/TrendAnalysis.tsx`

- [ ] **Step 1: Implement trend analysis page**

Replace `frontend/src/pages/TrendAnalysis.tsx`:

```tsx
import { useEffect, useState } from "react";
import { trendsApi, keywordsApi, HeatmapSeries, Keyword } from "../api/client";
import HeatmapChart from "../components/HeatmapChart";
import TrendLineChart from "../components/TrendLineChart";
import KeywordSelector from "../components/KeywordSelector";

type ViewMode = "heatmap" | "line";

export default function TrendAnalysis() {
  const [keywords, setKeywords] = useState<Keyword[]>([]);
  const [selected, setSelected] = useState<number[]>([]);
  const [period, setPeriod] = useState("7d");
  const [viewMode, setViewMode] = useState<ViewMode>("heatmap");
  const [data, setData] = useState<HeatmapSeries[]>([]);

  useEffect(() => {
    keywordsApi.list().then((kws) => {
      setKeywords(kws);
      setSelected(kws.map((k) => k.id));
    });
  }, []);

  useEffect(() => {
    trendsApi.heatmap(period).then((all) => {
      const filtered = selected.length
        ? all.filter((s) => selected.includes(s.keyword.id))
        : all;
      setData(filtered);
    });
  }, [period, selected]);

  return (
    <div>
      <h1>Trend Analysis</h1>

      <KeywordSelector keywords={keywords} selected={selected} onChange={setSelected} />

      <div style={{ display: "flex", gap: 12, marginBottom: 16 }}>
        {/* Period selector */}
        {["7d", "30d", "90d"].map((p) => (
          <button key={p} onClick={() => setPeriod(p)}
            style={{ fontWeight: period === p ? "bold" : "normal", background: period === p ? "#3498db" : "#eee", color: period === p ? "white" : "black", border: "none", padding: "6px 16px", borderRadius: 4, cursor: "pointer" }}>
            {p}
          </button>
        ))}

        <span style={{ margin: "0 8px", color: "#ccc" }}>|</span>

        {/* View mode toggle */}
        <button onClick={() => setViewMode("heatmap")}
          style={{ fontWeight: viewMode === "heatmap" ? "bold" : "normal", background: viewMode === "heatmap" ? "#2ecc71" : "#eee", color: viewMode === "heatmap" ? "white" : "black", border: "none", padding: "6px 16px", borderRadius: 4, cursor: "pointer" }}>
          Heatmap
        </button>
        <button onClick={() => setViewMode("line")}
          style={{ fontWeight: viewMode === "line" ? "bold" : "normal", background: viewMode === "line" ? "#2ecc71" : "#eee", color: viewMode === "line" ? "white" : "black", border: "none", padding: "6px 16px", borderRadius: 4, cursor: "pointer" }}>
          Trend Lines
        </button>
      </div>

      <div style={{ background: "white", padding: 16, borderRadius: 8 }}>
        {viewMode === "heatmap" ? (
          <HeatmapChart data={data} />
        ) : (
          <TrendLineChart data={data} />
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify and commit**

```bash
git add frontend/src/pages/TrendAnalysis.tsx
git commit -m "feat: trend analysis page with heatmap/line toggle and period selector"
```

---

## Chunk 6: Weekly Summary API + End-to-End Verification

### Task 18: Weekly summary API

**Files:**
- Create: `backend/app/routers/summary.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Implement summary router**

Create `backend/app/routers/summary.py`:

```python
from datetime import date, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import select, func
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
            .where(
                TrendSnapshot.keyword_id == kw.id,
                TrendSnapshot.date >= start,
                TrendSnapshot.date <= end,
            )
            .order_by(TrendSnapshot.date)
        )
        snaps = snaps_result.scalars().all()
        scores = [s.score for s in snaps]
        total_mentions = sum(s.mention_count for s in snaps)
        trend = detect_trend_direction(scores)

        # Top articles (most recent mentions)
        mentions_result = await db.execute(
            select(KeywordMention, Article)
            .join(Article, KeywordMention.article_id == Article.id)
            .where(KeywordMention.keyword_id == kw.id)
            .order_by(Article.published_at.desc())
            .limit(3)
        )
        top_articles = [
            {"title": article.title, "url": article.url}
            for mention, article in mentions_result.all()
        ]

        result_keywords.append({
            "name": kw.name,
            "trend": trend,
            "mention_count": total_mentions,
            "top_articles": top_articles,
        })

    return {
        "keywords": result_keywords,
        "period": "last_7_days",
    }
```

- [ ] **Step 2: Register in main.py**

Add to `backend/app/main.py`:

```python
from app.routers import summary

app.include_router(summary.router)
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/routers/summary.py backend/app/main.py
git commit -m "feat: add weekly summary API endpoint"
```

---

### Task 19: End-to-end verification

- [ ] **Step 1: Run all backend tests**

```bash
cd backend
python -m pytest tests/ -v
# Expected: all tests PASS
```

- [ ] **Step 2: Start backend and frontend**

```bash
# Terminal 1:
cd backend
python -m uvicorn app.main:app --reload --port 8000

# Terminal 2:
cd frontend
npm run dev
```

- [ ] **Step 3: Manual end-to-end test**

1. Open http://localhost:5173
2. Go to **Keywords** → Add "AI Agent" with alias "AI助手", color red
3. Add "MCP" with color blue
4. Go to **Sources** → Add "Hacker News RSS" with URL `https://hnrss.org/newest` type RSS weight 2.0
5. Click **Trigger Crawl** → wait for completion
6. Go to **Dashboard** → verify heatmap shows data
7. Go to **Trends** → switch between heatmap/line view, change 7d/30d/90d
8. Verify keyword cards show trend arrows (↑↓→)

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "feat: complete trend tracker MVP — backend + frontend"
```

---

## Deferred (Post-MVP)

- `GET /api/crawl/history` — requires a new `CrawlRun` model to log each crawl execution. Not critical for MVP; can be added when crawl observability becomes important.

## Verification Checklist

After all tasks are complete, verify:

- [ ] `cd backend && python -m pytest tests/ -v` — all tests pass
- [ ] Backend starts: `python -m uvicorn app.main:app --port 8000`
- [ ] Frontend starts: `cd frontend && npm run dev`
- [ ] Can add keywords with aliases and colors
- [ ] Can add data sources (RSS)
- [ ] Can trigger crawl and see status
- [ ] Dashboard shows heatmap with keyword data
- [ ] Trend analysis page toggles heatmap/line views
- [ ] Period selector (7d/30d/90d) works
- [ ] Keyword rescan generates historical data
- [ ] `/api/articles?keyword_id=1` returns filtered article list
- [ ] `/api/keywords/1/mentions` returns keyword mention records
- [ ] `/api/summary/weekly` returns aggregated trend data
- [ ] `/api/crawl/trigger` returns 409 when crawl is already running
- [ ] Exponential backoff skips repeatedly failing sources
