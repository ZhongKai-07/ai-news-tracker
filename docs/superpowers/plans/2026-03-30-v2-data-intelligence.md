# V2 Data Intelligence Upgrade — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the AI News Trend Tracker with data cleaning, LLM-powered semantic keyword matching, and deep analysis (trend reports, alerts, correlations).

**Architecture:** Three-module upgrade built on the existing FastAPI + SQLAlchemy async stack. Module 1 (data cleaning) inserts rule-based processing into the existing crawl pipeline. Module 2 (semantic matching) adds LLM-backed keyword matching via a decoupled APScheduler job. Module 3 (deep analysis) adds trend reports, alerts, and correlations as new services and API endpoints. A unified LLM service layer handles tiered model routing, retries, and circuit breaking.

**Tech Stack:** FastAPI, SQLAlchemy 2.0 (async), aiosqlite, Alembic, APScheduler, BeautifulSoup4, OpenAI-compatible API (Qwen/Kimi), ECharts, React/TypeScript

**Spec:** `docs/superpowers/specs/2026-03-30-v2-data-intelligence-design.md`

---

## Chunk 1: Foundation — DB Models, Config, LLM Service, Alembic Migration

This chunk establishes all new database models, config fields, the LLM service layer, and the Alembic migration. Everything else builds on this.

### Task 1: Add LLM config fields to Settings

**Files:**
- Modify: `backend/app/config.py:3-12`
- Test: `backend/tests/test_config.py` (create)

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_config.py
from app.config import Settings

def test_llm_config_defaults():
    s = Settings()
    assert s.llm_provider == "openai_compatible"
    assert s.llm_tier1_model == "qwen-turbo"
    assert s.llm_tier2_model == "qwen-plus"
    assert s.llm_tier3_model == "qwen-max"
    assert s.llm_timeout_seconds == 30
    assert s.llm_max_retries == 2
    assert s.llm_batch_size == 20
    assert s.llm_circuit_breaker_threshold == 5
    assert s.llm_base_url == ""
    assert s.llm_api_key == ""
    assert s.llm_process_interval_minutes == 10
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_config.py -v`
Expected: FAIL — `Settings` has no `llm_provider` attribute

- [ ] **Step 3: Write minimal implementation**

Add to `backend/app/config.py` Settings class (after existing fields at line 9):

```python
    # LLM service
    llm_provider: str = "openai_compatible"
    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_tier1_model: str = "qwen-turbo"
    llm_tier2_model: str = "qwen-plus"
    llm_tier3_model: str = "qwen-max"
    llm_timeout_seconds: int = 30
    llm_max_retries: int = 2
    llm_batch_size: int = 20
    llm_circuit_breaker_threshold: int = 5
    llm_process_interval_minutes: int = 10
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_config.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/config.py backend/tests/test_config.py
git commit -m "feat: add LLM config fields to Settings"
```

---

### Task 1.5: Create shared test fixtures (conftest.py)

**Files:**
- Create: `backend/tests/conftest.py`

The existing `db_session` and `db_engine` fixtures live only in `test_models.py`. Many new test files will need them. Extract to a shared `conftest.py`.

- [ ] **Step 1: Read current test_models.py to find the fixture definitions**

Read `backend/tests/test_models.py` and identify the `db_engine` and `db_session` fixtures.

- [ ] **Step 2: Create conftest.py with shared fixtures**

```python
# backend/tests/conftest.py
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.database import Base

# Import all models so metadata is populated
from app.models.article import Article  # noqa: F401
from app.models.data_source import DataSource  # noqa: F401
from app.models.keyword import Keyword  # noqa: F401
from app.models.keyword_mention import KeywordMention  # noqa: F401
from app.models.trend_snapshot import TrendSnapshot  # noqa: F401
# Note: Add these imports after Task 3 creates the new model files:
# from app.models.trend_report import TrendReport  # noqa: F401
# from app.models.keyword_correlation import KeywordCorrelation  # noqa: F401
# from app.models.alert import Alert  # noqa: F401

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
```

- [ ] **Step 3: Remove duplicate fixtures from test_models.py**

Remove the `db_engine` and `db_session` fixture definitions from `backend/tests/test_models.py` (pytest will auto-discover them from `conftest.py`).

- [ ] **Step 4: Run existing tests to verify fixtures work**

Run: `cd backend && python -m pytest tests/test_models.py -v`
Expected: All existing tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/tests/conftest.py backend/tests/test_models.py
git commit -m "refactor: extract shared test fixtures to conftest.py"
```

---

### Task 2: Add new fields to existing models (Article, DataSource, KeywordMention)

**Files:**
- Modify: `backend/app/models/article.py:10-18`
- Modify: `backend/app/models/data_source.py:10-25`
- Modify: `backend/app/models/keyword_mention.py:9-15`
- Test: `backend/tests/test_models.py` (add new tests)

- [ ] **Step 1: Read current test_models.py to understand existing test patterns**

Run: `cd backend && cat tests/test_models.py`

- [ ] **Step 2: Write failing tests for new fields**

Add to `backend/tests/test_models.py`:

```python
@pytest.mark.asyncio
async def test_article_new_fields(db_session):
    """Test V2 Article fields: cleaned_content, quality_score, quality_tag, summary, needs_llm_matching."""
    source = DataSource(name="test", type="rss", url="http://test.com")
    db_session.add(source)
    await db_session.flush()
    article = Article(
        source_id=source.id,
        title="Test Article",
        url="http://test.com/1",
        cleaned_content="Clean text here",
        quality_score=75,
        quality_tag="passed",
        summary="A test summary.",
        needs_llm_matching=False,
    )
    db_session.add(article)
    await db_session.flush()
    assert article.cleaned_content == "Clean text here"
    assert article.quality_score == 75
    assert article.quality_tag == "passed"
    assert article.summary == "A test summary."
    assert article.needs_llm_matching is False

@pytest.mark.asyncio
async def test_article_new_fields_defaults(db_session):
    """V2 fields should have sensible defaults for backward compatibility."""
    source = DataSource(name="test", type="rss", url="http://test.com")
    db_session.add(source)
    await db_session.flush()
    article = Article(source_id=source.id, title="Test", url="http://test.com/2")
    db_session.add(article)
    await db_session.flush()
    assert article.cleaned_content is None
    assert article.quality_score is None
    assert article.quality_tag == "passed"
    assert article.summary is None
    assert article.needs_llm_matching is False

@pytest.mark.asyncio
async def test_datasource_trust_level(db_session):
    source = DataSource(name="test", type="rss", url="http://test.com")
    db_session.add(source)
    await db_session.flush()
    assert source.trust_level == "low"  # New sources default to low per spec

@pytest.mark.asyncio
async def test_keyword_mention_match_method(db_session):
    source = DataSource(name="test", type="rss", url="http://test.com")
    db_session.add(source)
    await db_session.flush()
    kw = Keyword(name="test_kw")
    db_session.add(kw)
    await db_session.flush()
    article = Article(source_id=source.id, title="Test", url="http://test.com/3")
    db_session.add(article)
    await db_session.flush()
    mention = KeywordMention(
        keyword_id=kw.id, article_id=article.id,
        match_location="title", match_method="llm", match_reason="Semantic match"
    )
    db_session.add(mention)
    await db_session.flush()
    assert mention.match_method == "llm"
    assert mention.match_reason == "Semantic match"
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_models.py -v -k "new_fields or trust_level or match_method"`
Expected: FAIL — fields don't exist yet

- [ ] **Step 4: Add fields to Article model**

In `backend/app/models/article.py`, add after existing fields (after `fetched_at`, before relationships):

```python
    cleaned_content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    quality_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    quality_tag: Mapped[str] = mapped_column(String(20), default="passed")
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    needs_llm_matching: Mapped[bool] = mapped_column(Boolean, default=False)
```

Add imports: `Integer, Boolean` to the SQLAlchemy imports at top of file.

- [ ] **Step 5: Add trust_level to DataSource model**

In `backend/app/models/data_source.py`, add after `custom_headers` field:

```python
    trust_level: Mapped[str] = mapped_column(String(10), default="low")
```

Note: Model default is `"low"` per spec (new sources start as low trust). The Alembic migration (Task 4) will set `server_default="medium"` for existing rows.

- [ ] **Step 6: Add match_method and match_reason to KeywordMention model**

In `backend/app/models/keyword_mention.py`, add after `context_snippet` field:

```python
    match_method: Mapped[str] = mapped_column(String(20), default="rule")
    match_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_models.py -v`
Expected: ALL PASS

- [ ] **Step 8: Run full test suite to check nothing is broken**

Run: `cd backend && python -m pytest tests/ -v`
Expected: All 25+ existing tests PASS

- [ ] **Step 9: Commit**

```bash
git add backend/app/models/article.py backend/app/models/data_source.py backend/app/models/keyword_mention.py backend/tests/test_models.py
git commit -m "feat: add V2 fields to Article, DataSource, KeywordMention models"
```

---

### Task 3: Create new models (TrendReport, KeywordCorrelation, Alert)

**Files:**
- Create: `backend/app/models/trend_report.py`
- Create: `backend/app/models/keyword_correlation.py`
- Create: `backend/app/models/alert.py`
- Modify: `backend/app/models/__init__.py` (add exports)
- Test: `backend/tests/test_models.py` (add tests)

- [ ] **Step 1: Write failing tests for new models**

Add to `backend/tests/test_models.py`:

```python
from app.models.trend_report import TrendReport
from app.models.keyword_correlation import KeywordCorrelation
from app.models.alert import Alert
from datetime import date

@pytest.mark.asyncio
async def test_trend_report_creation(db_session):
    kw = Keyword(name="test_report_kw")
    db_session.add(kw)
    await db_session.flush()
    report = TrendReport(
        keyword_id=kw.id, report_date=date.today(), period="daily",
        summary="Test summary", key_drivers=["driver1"], outlook="Rising"
    )
    db_session.add(report)
    await db_session.flush()
    assert report.id is not None
    assert report.period == "daily"

@pytest.mark.asyncio
async def test_keyword_correlation_creation(db_session):
    kw1 = Keyword(name="kw_corr_a")
    kw2 = Keyword(name="kw_corr_b")
    db_session.add_all([kw1, kw2])
    await db_session.flush()
    corr = KeywordCorrelation(
        keyword_id_a=min(kw1.id, kw2.id), keyword_id_b=max(kw1.id, kw2.id),
        co_occurrence_count=10, period_start=date.today(), period_end=date.today()
    )
    db_session.add(corr)
    await db_session.flush()
    assert corr.id is not None

@pytest.mark.asyncio
async def test_alert_creation(db_session):
    kw = Keyword(name="alert_kw")
    db_session.add(kw)
    await db_session.flush()
    alert = Alert(
        keyword_id=kw.id, alert_type="spike",
        trigger_value=15.0, baseline_value=5.0, analysis_status="pending"
    )
    db_session.add(alert)
    await db_session.flush()
    assert alert.id is not None
    assert alert.is_read is False
    assert alert.analysis_status == "pending"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_models.py -v -k "trend_report or correlation or alert"`
Expected: FAIL — modules don't exist

- [ ] **Step 3: Create TrendReport model**

```python
# backend/app/models/trend_report.py
from datetime import date, datetime, timezone
from typing import Optional
from sqlalchemy import Integer, String, Text, Date, DateTime, ForeignKey, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

class TrendReport(Base):
    __tablename__ = "trend_reports"
    __table_args__ = (UniqueConstraint("keyword_id", "report_date", "period"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    keyword_id: Mapped[int] = mapped_column(Integer, ForeignKey("keywords.id"))
    report_date: Mapped[date] = mapped_column(Date)
    period: Mapped[str] = mapped_column(String(10))  # "daily" or "weekly"
    summary: Mapped[str] = mapped_column(Text)
    key_drivers: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    outlook: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    keyword = relationship("Keyword")
```

- [ ] **Step 4: Create KeywordCorrelation model**

```python
# backend/app/models/keyword_correlation.py
from datetime import date
from typing import Optional
from sqlalchemy import Integer, Text, Date, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

class KeywordCorrelation(Base):
    __tablename__ = "keyword_correlations"
    __table_args__ = (
        UniqueConstraint("keyword_id_a", "keyword_id_b", "period_start", "period_end"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    keyword_id_a: Mapped[int] = mapped_column(Integer, ForeignKey("keywords.id"))
    keyword_id_b: Mapped[int] = mapped_column(Integer, ForeignKey("keywords.id"))
    co_occurrence_count: Mapped[int] = mapped_column(Integer, default=0)
    relationship_desc: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)

    keyword_a = relationship("Keyword", foreign_keys=[keyword_id_a])
    keyword_b = relationship("Keyword", foreign_keys=[keyword_id_b])
```

- [ ] **Step 5: Create Alert model**

```python
# backend/app/models/alert.py
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import Integer, String, Float, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    keyword_id: Mapped[int] = mapped_column(Integer, ForeignKey("keywords.id"))
    alert_type: Mapped[str] = mapped_column(String(20))  # "spike" or "sustained_rise"
    trigger_value: Mapped[float] = mapped_column(Float)
    baseline_value: Mapped[float] = mapped_column(Float)
    analysis: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    analysis_status: Mapped[str] = mapped_column(String(20), default="pending")
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    keyword = relationship("Keyword")
```

- [ ] **Step 6: Update models __init__.py to export new models**

Add imports to `backend/app/models/__init__.py`:

```python
from app.models.trend_report import TrendReport
from app.models.keyword_correlation import KeywordCorrelation
from app.models.alert import Alert
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_models.py -v`
Expected: ALL PASS

- [ ] **Step 8: Commit**

```bash
git add backend/app/models/trend_report.py backend/app/models/keyword_correlation.py backend/app/models/alert.py backend/app/models/__init__.py backend/tests/test_models.py
git commit -m "feat: add TrendReport, KeywordCorrelation, Alert models"
```

---

### Task 4: Set up Alembic and create initial migration

**Files:**
- Modify: `backend/alembic.ini` (if exists, else create via `alembic init`)
- Modify: `backend/alembic/env.py`
- Create: migration script (auto-generated)

- [ ] **Step 1: Check if Alembic is already initialized**

Run: `ls backend/alembic/ 2>/dev/null && echo "EXISTS" || echo "NEEDS_INIT"`

- [ ] **Step 2: Initialize Alembic (if needed)**

Run: `cd backend && python -m alembic init alembic`

- [ ] **Step 3: Configure alembic env.py for async SQLAlchemy**

Edit `backend/alembic/env.py` to:
- Import `Base` from `app.database`
- Import all models (so metadata is populated)
- Set `target_metadata = Base.metadata`
- Configure async engine using `run_async_migrations`
- Use `render_as_batch=True` for SQLite compatibility (required for ALTER TABLE)

- [ ] **Step 4: Configure alembic.ini**

Set `sqlalchemy.url = sqlite+aiosqlite:///./ai_news.db` in `backend/alembic.ini`

- [ ] **Step 5: Generate migration**

Run: `cd backend && python -m alembic revision --autogenerate -m "v2_data_intelligence_fields"`

- [ ] **Step 6: Review generated migration**

Check the generated migration file. It should:
- Add columns to `articles`: cleaned_content, quality_score, quality_tag, summary, needs_llm_matching
- Add column to `data_sources`: trust_level
- Add columns to `keyword_mentions`: match_method, match_reason
- Create tables: trend_reports, keyword_correlations, alerts
- Use `batch_alter_table` context for SQLite compatibility

- [ ] **Step 7: Apply migration**

Run: `cd backend && python -m alembic upgrade head`
Expected: Migration applies successfully

- [ ] **Step 8: Commit**

```bash
git add backend/alembic/ backend/alembic.ini
git commit -m "feat: Alembic setup and V2 migration for new models/fields"
```

---

### Task 5: LLM Service — unified calling layer with tiered routing

**Files:**
- Create: `backend/app/services/llm_service.py`
- Test: `backend/tests/test_llm_service.py` (create)

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_llm_service.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.llm_service import LLMService

@pytest.fixture
def llm_service():
    return LLMService(
        base_url="http://fake.api/v1",
        api_key="test-key",
        tier1_model="tier1",
        tier2_model="tier2",
        tier3_model="tier3",
        timeout=5,
        max_retries=1,
        circuit_breaker_threshold=3,
    )

def test_tier_to_model_mapping(llm_service):
    assert llm_service._get_model("tier1") == "tier1"
    assert llm_service._get_model("tier2") == "tier2"
    assert llm_service._get_model("tier3") == "tier3"

def test_circuit_breaker_initial_state(llm_service):
    assert llm_service._circuit_open is False
    assert llm_service._consecutive_failures == 0

@pytest.mark.asyncio
async def test_call_success(llm_service):
    mock_response = {"choices": [{"message": {"content": '{"result": "ok"}'}}]}
    with patch.object(llm_service, '_raw_call', new_callable=AsyncMock, return_value=mock_response):
        result = await llm_service.call("tier1", "test prompt")
        assert result == '{"result": "ok"}'

@pytest.mark.asyncio
async def test_call_retry_then_succeed(llm_service):
    call_count = 0
    async def fake_call(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise Exception("Timeout")
        return {"choices": [{"message": {"content": "ok"}}]}
    with patch.object(llm_service, '_raw_call', side_effect=fake_call):
        result = await llm_service.call("tier1", "test")
        assert result == "ok"
        assert call_count == 2

@pytest.mark.asyncio
async def test_circuit_breaker_opens(llm_service):
    llm_service._circuit_breaker_threshold = 3
    async def always_fail(*args, **kwargs):
        raise Exception("API down")
    with patch.object(llm_service, '_raw_call', side_effect=always_fail):
        for _ in range(3):
            try:
                await llm_service.call("tier1", "test")
            except Exception:
                pass
    assert llm_service._circuit_open is True

@pytest.mark.asyncio
async def test_tier_degradation(llm_service):
    """Tier 2 failure should degrade to Tier 1."""
    calls = []
    async def track_calls(model, messages, **kwargs):
        calls.append(model)
        if model == "tier2":
            raise Exception("Tier 2 down")
        return {"choices": [{"message": {"content": "degraded"}}]}
    with patch.object(llm_service, '_raw_call', side_effect=track_calls):
        result = await llm_service.call("tier2", "test")
        assert result == "degraded"
        assert "tier1" in calls
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_llm_service.py -v`
Expected: FAIL — module doesn't exist

- [ ] **Step 3: Implement LLMService**

```python
# backend/app/services/llm_service.py
import asyncio
import time
import aiohttp
from app.config import settings

class LLMService:
    def __init__(
        self,
        base_url: str = "",
        api_key: str = "",
        tier1_model: str = "qwen-turbo",
        tier2_model: str = "qwen-plus",
        tier3_model: str = "qwen-max",
        timeout: int = 30,
        max_retries: int = 2,
        circuit_breaker_threshold: int = 5,
    ):
        self.base_url = base_url
        self.api_key = api_key
        self.tier1_model = tier1_model
        self.tier2_model = tier2_model
        self.tier3_model = tier3_model
        self.timeout = timeout
        self.max_retries = max_retries
        self._circuit_breaker_threshold = circuit_breaker_threshold
        self._consecutive_failures = 0
        self._circuit_open = False
        self._circuit_open_time = 0.0
        self._CIRCUIT_PROBE_INTERVAL = 600  # 10 minutes

    def _get_model(self, tier: str) -> str:
        return {"tier1": self.tier1_model, "tier2": self.tier2_model, "tier3": self.tier3_model}[tier]

    def _get_degraded_tier(self, tier: str) -> str | None:
        return {"tier3": "tier2", "tier2": "tier1"}.get(tier)

    async def _raw_call(self, model: str, messages: list[dict], **kwargs) -> dict:
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        payload = {"model": model, "messages": messages, **kwargs}
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/chat/completions",
                json=payload, headers=headers,
                timeout=aiohttp.ClientTimeout(total=self.timeout)
            ) as resp:
                resp.raise_for_status()
                return await resp.json()

    async def call(self, tier: str, prompt: str, system_prompt: str = "") -> str:
        # Circuit breaker check
        if self._circuit_open:
            if time.time() - self._circuit_open_time > self._CIRCUIT_PROBE_INTERVAL:
                self._circuit_open = False  # probe
            else:
                raise Exception("Circuit breaker open")

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        model = self._get_model(tier)
        delays = [2, 5]

        # Try with retries
        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                response = await self._raw_call(model, messages)
                self._consecutive_failures = 0
                self._circuit_open = False
                return response["choices"][0]["message"]["content"]
            except Exception as e:
                last_error = e
                if attempt < self.max_retries:
                    await asyncio.sleep(delays[min(attempt, len(delays) - 1)])

        # Try degraded tier
        degraded = self._get_degraded_tier(tier)
        if degraded:
            degraded_model = self._get_model(degraded)
            try:
                response = await self._raw_call(degraded_model, messages)
                self._consecutive_failures = 0
                return response["choices"][0]["message"]["content"]
            except Exception:
                pass

        # All failed
        self._consecutive_failures += 1
        if self._consecutive_failures >= self._circuit_breaker_threshold:
            self._circuit_open = True
            self._circuit_open_time = time.time()
        raise last_error

    async def call_json(self, tier: str, prompt: str, system_prompt: str = "") -> dict:
        """Call LLM and parse response as JSON."""
        import json
        content = await self.call(tier, prompt, system_prompt)
        # Handle markdown-wrapped JSON
        if content.startswith("```"):
            content = content.split("\n", 1)[1].rsplit("```", 1)[0]
        return json.loads(content)


def create_llm_service() -> LLMService:
    return LLMService(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        tier1_model=settings.llm_tier1_model,
        tier2_model=settings.llm_tier2_model,
        tier3_model=settings.llm_tier3_model,
        timeout=settings.llm_timeout_seconds,
        max_retries=settings.llm_max_retries,
        circuit_breaker_threshold=settings.llm_circuit_breaker_threshold,
    )

llm_service = create_llm_service()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_llm_service.py -v`
Expected: ALL PASS

- [ ] **Step 5: Run full test suite**

Run: `cd backend && python -m pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/llm_service.py backend/tests/test_llm_service.py
git commit -m "feat: add LLMService with tiered routing, retry, and circuit breaker"
```

---

## Chunk 2: Module 1 — Data Cleaning Pipeline (content_cleaner, quality_scorer, summary extractor)

This chunk implements the rule-based cleaning that runs synchronously inside the crawl pipeline (Phase 1).

### Task 6: Content cleaner service (HTML sanitization + data completion)

**Files:**
- Create: `backend/app/services/content_cleaner.py`
- Test: `backend/tests/test_content_cleaner.py` (create)

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_content_cleaner.py
import pytest
from app.services.content_cleaner import clean_html, complete_data, extract_summary

class TestCleanHtml:
    def test_removes_script_tags(self):
        html = '<p>Hello</p><script>alert("xss")</script><p>World</p>'
        assert "alert" not in clean_html(html)
        assert "Hello" in clean_html(html)
        assert "World" in clean_html(html)

    def test_removes_nav_footer_aside(self):
        html = '<nav>Menu</nav><article><p>Content</p></article><footer>Footer</footer>'
        result = clean_html(html)
        assert "Menu" not in result
        assert "Footer" not in result
        assert "Content" in result

    def test_removes_ad_divs(self):
        html = '<div class="ad-banner">Ad</div><p>Real content</p><div id="sponsor-box">Sponsor</div>'
        result = clean_html(html)
        assert "Ad" not in result
        assert "Sponsor" not in result
        assert "Real content" in result

    def test_extracts_article_tag_priority(self):
        html = '<div>Noise</div><article><p>Main article text</p></article><div>More noise</div>'
        result = clean_html(html)
        assert "Main article text" in result

    def test_preserves_paragraph_breaks(self):
        html = '<p>Paragraph one.</p><p>Paragraph two.</p>'
        result = clean_html(html)
        assert "Paragraph one." in result
        assert "Paragraph two." in result

    def test_empty_input(self):
        assert clean_html("") == ""
        assert clean_html(None) == ""

class TestCompleteData:
    def test_title_fallback_from_content(self):
        data = {"title": "", "content": "This is a long content that should serve as title fallback for the article", "published_at": None, "fetched_at": "2026-03-30T10:00:00Z"}
        result = complete_data(data)
        assert len(result["title"]) > 0
        assert len(result["title"]) <= 80

    def test_title_fallback_from_url_title(self):
        data = {"title": "http://example.com/article", "content": "Some content here about technology", "published_at": None, "fetched_at": "2026-03-30T10:00:00Z"}
        result = complete_data(data)
        # URL-only title should be replaced with content excerpt
        assert not result["title"].startswith("http")

    def test_published_at_kept_if_present(self):
        data = {"title": "Test", "content": "Content", "published_at": "2026-03-30", "fetched_at": "2026-03-31"}
        result = complete_data(data)
        assert result["published_at"] == "2026-03-30"

    def test_published_at_fallback_to_fetched_at(self):
        data = {"title": "Test", "content": "Content", "published_at": None, "fetched_at": "2026-03-31"}
        result = complete_data(data)
        assert result["published_at"] == "2026-03-31"

class TestExtractSummary:
    def test_chinese_sentence_extraction(self):
        text = "这是第一段很短。这是一篇关于人工智能技术发展趋势的深度分析文章，探讨了大语言模型在各个领域的应用前景。第三句话。"
        result = extract_summary(text)
        assert "人工智能技术" in result
        assert len(result) <= 200

    def test_english_sentence_extraction(self):
        text = "By John Smith. This is a comprehensive analysis of the latest trends in artificial intelligence and machine learning technology. More text follows."
        result = extract_summary(text)
        assert "comprehensive analysis" in result
        # Should skip the short "By John Smith." line
        assert not result.startswith("By John")

    def test_skips_short_lines(self):
        text = "Photo credit.\nUpdated 2024.\nThis is the actual article content that discusses important technology trends in depth."
        result = extract_summary(text)
        assert "actual article content" in result

    def test_fallback_to_truncation(self):
        text = "a " * 100  # No clear sentence boundary
        result = extract_summary(text)
        assert len(result) <= 200

    def test_empty_input(self):
        assert extract_summary("") == ""
        assert extract_summary(None) == ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_content_cleaner.py -v`
Expected: FAIL — module doesn't exist

- [ ] **Step 3: Implement content_cleaner.py**

```python
# backend/app/services/content_cleaner.py
import re
from bs4 import BeautifulSoup

_NOISE_TAGS = {"script", "style", "nav", "footer", "aside", "iframe", "form"}
_AD_PATTERNS = re.compile(r"(ad|sponsor|promo|sidebar|comment)", re.IGNORECASE)
_URL_PATTERN = re.compile(r"^https?://")
_EN_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z])")
_ZH_SENTENCE_SPLIT = re.compile(r"(?<=[。！？])")


def clean_html(html: str | None) -> str:
    if not html:
        return ""
    soup = BeautifulSoup(html, "html.parser")

    # Remove noise tags
    for tag in soup.find_all(_NOISE_TAGS):
        tag.decompose()

    # Remove ad-related divs
    for tag in soup.find_all("div"):
        classes = " ".join(tag.get("class", []))
        tag_id = tag.get("id", "")
        if _AD_PATTERNS.search(classes) or _AD_PATTERNS.search(tag_id):
            tag.decompose()

    # Prefer <article> or <main> content
    article = soup.find("article") or soup.find("main")
    target = article if article else soup

    # Extract text preserving paragraph breaks
    paragraphs = []
    for p in target.find_all(["p", "h1", "h2", "h3", "h4", "li"]):
        text = p.get_text(strip=True)
        if text:
            paragraphs.append(text)

    if not paragraphs:
        return target.get_text(separator="\n", strip=True)

    return "\n".join(paragraphs)


def complete_data(data: dict) -> dict:
    result = {**data}

    # Title fallback
    title = (result.get("title") or "").strip()
    if not title or _URL_PATTERN.match(title) or len(title) < 5:
        content = result.get("content") or ""
        result["title"] = content[:80].strip()

    # published_at fallback
    if not result.get("published_at"):
        result["published_at"] = result.get("fetched_at")

    return result


def extract_summary(text: str | None) -> str:
    if not text:
        return ""

    lines = text.strip().split("\n")
    # Filter out short lines (bylines, dates, captions)
    lines = [line.strip() for line in lines if len(line.strip()) >= 20]
    if not lines:
        return text[:100].strip() if text else ""

    joined = " ".join(lines)

    # Try Chinese sentence splitting first
    zh_sentences = _ZH_SENTENCE_SPLIT.split(joined)
    zh_sentences = [s.strip() for s in zh_sentences if len(s.strip()) >= 20]
    if zh_sentences:
        for s in zh_sentences:
            if 20 <= len(s) <= 200:
                return s

    # Try English sentence splitting
    en_sentences = _EN_SENTENCE_SPLIT.split(joined)
    en_sentences = [s.strip() for s in en_sentences if len(s.strip()) >= 20]
    if en_sentences:
        for s in en_sentences:
            if 20 <= len(s) <= 200:
                return s

    # Fallback: truncate to last punctuation within 100 chars
    excerpt = joined[:150]
    for punct in ["。", ".", "！", "!", "？", "?"]:
        idx = excerpt.rfind(punct)
        if idx > 20:
            return excerpt[: idx + 1]

    return joined[:100].strip()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_content_cleaner.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/content_cleaner.py backend/tests/test_content_cleaner.py
git commit -m "feat: add content cleaner (HTML sanitize, data complete, summary extract)"
```

---

### Task 7: Quality scorer service (multi-signal rule scoring)

**Files:**
- Create: `backend/app/services/quality_scorer.py`
- Test: `backend/tests/test_quality_scorer.py` (create)

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_quality_scorer.py
import pytest
from app.services.quality_scorer import calculate_quality_score

class TestQualityScorer:
    def test_high_trust_long_content(self):
        score = calculate_quality_score(
            title="A detailed analysis of AI trends in 2026",
            content="x" * 600,
            url="https://blog.anthropic.com/ai-trends",
            trust_level="high",
        )
        assert score >= 60  # should pass
        assert score <= 100

    def test_low_trust_short_content(self):
        score = calculate_quality_score(
            title="Hi",
            content="short",
            url="https://unknown.xyz/post",
            trust_level="low",
        )
        assert score < 30  # should be filtered

    def test_medium_trust_normal_content(self):
        score = calculate_quality_score(
            title="New developments in machine learning research",
            content="x" * 300,
            url="https://techcrunch.com/article",
            trust_level="medium",
        )
        assert 30 <= score <= 100

    def test_ad_url_penalty(self):
        score_normal = calculate_quality_score(
            title="Good article", content="x" * 300,
            url="https://example.com/article", trust_level="medium",
        )
        score_ad = calculate_quality_score(
            title="Good article", content="x" * 300,
            url="https://example.com/ad/sponsored-post", trust_level="medium",
        )
        assert score_ad < score_normal

    def test_spam_title_penalty(self):
        score = calculate_quality_score(
            title="Sponsored: Buy this product now",
            content="x" * 300,
            url="https://example.com/post",
            trust_level="medium",
        )
        # "Sponsored" in title triggers -30
        assert score < 30

    def test_score_clamped_to_0_100(self):
        # Low trust + empty content + bad URL + spam title = deeply negative raw score
        score = calculate_quality_score(
            title="AD sponsored", content="",
            url="https://x.com/ad/redirect/campaign", trust_level="low",
        )
        assert score >= 0

        # High trust + long content + good title
        score = calculate_quality_score(
            title="A perfectly normal technology article title",
            content="x" * 1000, url="https://good.com/post", trust_level="high",
        )
        assert score <= 100

    def test_empty_content_penalty(self):
        score = calculate_quality_score(
            title="Normal article title here",
            content="", url="https://example.com/post", trust_level="high",
        )
        # high(80) + good title(+5) + empty content(-20) = 65
        assert score >= 60
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_quality_scorer.py -v`
Expected: FAIL — module doesn't exist

- [ ] **Step 3: Implement quality_scorer.py**

```python
# backend/app/services/quality_scorer.py
import re

_TRUST_BASE = {"high": 80, "medium": 50, "low": 20}
_AD_URL_PATTERNS = re.compile(r"/(ad|sponsor|redirect|campaign)/", re.IGNORECASE)
_SPAM_TITLE_PATTERNS = re.compile(r"(广告|赞助|sponsored|^AD\b)", re.IGNORECASE)


def calculate_quality_score(
    title: str, content: str | None, url: str, trust_level: str,
) -> int:
    content = content or ""
    content_len = len(content)
    title_len = len(title) if title else 0

    # Signal 1: source trust
    score = _TRUST_BASE.get(trust_level, 20)

    # Signal 2: content completeness
    if content_len > 500:
        score += 15
    elif content_len >= 100:
        score += 5
    else:
        score -= 20

    if 10 <= title_len <= 100:
        score += 5
    elif title_len < 10 or title_len > 200:
        score -= 10

    # Signal 3: URL/content spam signals
    if _AD_URL_PATTERNS.search(url):
        score -= 30

    if title and _SPAM_TITLE_PATTERNS.search(title):
        score -= 30

    return max(0, min(100, score))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_quality_scorer.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/quality_scorer.py backend/tests/test_quality_scorer.py
git commit -m "feat: add quality scorer with multi-signal rule-based scoring"
```

---

### Task 8: Integrate cleaning pipeline into crawler (Phase 1)

**Files:**
- Modify: `backend/app/services/crawler.py:130-186` (`_process_article`)
- Test: `backend/tests/test_crawler.py` (add integration tests)

- [ ] **Step 1: Read current crawler.py and test_crawler.py**

Read both files in full to understand the exact integration point.

- [ ] **Step 2: Write failing tests for the new pipeline behavior**

Add to `backend/tests/test_crawler.py`:

```python
@pytest.mark.asyncio
async def test_process_article_sets_cleaned_content(db_session):
    """Phase 1: _process_article should clean HTML and set cleaned_content."""
    source = DataSource(name="test", type="rss", url="http://test.com", trust_level="high")
    db_session.add(source)
    await db_session.flush()
    kw = Keyword(name="AI", aliases=[])
    db_session.add(kw)
    await db_session.flush()

    article_data = {
        "title": "AI is transforming everything",
        "url": "http://test.com/article1",
        "content": "<p>AI is transforming the world.</p><script>bad</script>",
        "published_at": None,
    }
    from app.services.crawler import crawler_service
    await crawler_service._process_article(db_session, source, article_data, [{"id": kw.id, "name": "AI", "aliases": []}])
    await db_session.flush()

    from app.models.article import Article
    result = await db_session.execute(select(Article).where(Article.url == "http://test.com/article1"))
    article = result.scalar_one()
    assert article.cleaned_content is not None
    assert "bad" not in article.cleaned_content
    assert article.quality_score is not None
    assert article.quality_tag in ("passed", "pending_review", "filtered")

@pytest.mark.asyncio
async def test_filtered_article_skips_matching(db_session):
    """Articles with quality_score < 30 should not create KeywordMention."""
    source = DataSource(name="lowq", type="rss", url="http://spam.com", trust_level="low")
    db_session.add(source)
    await db_session.flush()
    kw = Keyword(name="AI", aliases=[])
    db_session.add(kw)
    await db_session.flush()

    article_data = {
        "title": "AD",
        "url": "http://spam.com/ad/redirect/buy",
        "content": "",
        "published_at": None,
    }
    from app.services.crawler import crawler_service
    await crawler_service._process_article(db_session, source, article_data, [{"id": kw.id, "name": "AI", "aliases": []}])
    await db_session.flush()

    from app.models.keyword_mention import KeywordMention
    result = await db_session.execute(select(KeywordMention))
    mentions = result.scalars().all()
    assert len(mentions) == 0
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_crawler.py -v -k "cleaned_content or filtered_article"`
Expected: FAIL

- [ ] **Step 4: Modify `_process_article` to integrate cleaning pipeline**

In `backend/app/services/crawler.py`, modify `_process_article` (lines 130-186):

1. After URL dedup check, before keyword matching:
   - Call `clean_html(article_data["content"])` → set `cleaned_content`
   - Call `complete_data(article_data)` → apply fallbacks
   - Call `calculate_quality_score(title, cleaned_content, url, source.trust_level)` → set `quality_score`
   - Call `extract_summary(cleaned_content)` → set `summary`
   - Determine `quality_tag` based on score thresholds
   - If `quality_tag == "filtered"`: create Article record but skip keyword matching
   - If `quality_tag == "pending_review"`: create Article with `needs_llm_matching=True`, skip matching
   - If `quality_tag == "passed"`: proceed to keyword matching as before

2. For keyword matching on "passed" articles:
   - Title strong hits → create KeywordMention with `match_method="rule"` + update TrendSnapshot
   - Weak/no hits → set `needs_llm_matching=True`

Add imports at top of crawler.py:
```python
from app.services.content_cleaner import clean_html, complete_data, extract_summary
from app.services.quality_scorer import calculate_quality_score
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_crawler.py -v`
Expected: ALL PASS

- [ ] **Step 6: Run full test suite**

Run: `cd backend && python -m pytest tests/ -v`
Expected: All tests PASS (may need to adjust some existing crawler tests that don't set trust_level)

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/crawler.py backend/tests/test_crawler.py
git commit -m "feat: integrate data cleaning pipeline into crawler Phase 1"
```

---

## Chunk 3: Module 2 — Semantic Matching + Phase 2 LLM Job

This chunk implements the LLM-powered semantic matcher, title similarity dedup, and the independent APScheduler job that processes pending articles.

### Task 9: Semantic matcher service (rule fast-filter + LLM batch)

**Files:**
- Create: `backend/app/services/semantic_matcher.py`
- Test: `backend/tests/test_semantic_matcher.py` (create)

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_semantic_matcher.py
import pytest
from unittest.mock import AsyncMock, patch
from app.services.semantic_matcher import SemanticMatcher, classify_rule_matches

class TestClassifyRuleMatches:
    def test_title_match_is_strong(self):
        keywords = [{"id": 1, "name": "AI Agent", "aliases": ["智能体"]}]
        result = classify_rule_matches("AI Agent launches today", "Some content about stuff", keywords)
        assert result["strong"] == [{"keyword_id": 1, "match_location": "title", "context_snippet": "AI Agent launches today"}]
        assert result["weak"] == []

    def test_content_only_match_is_weak(self):
        keywords = [{"id": 1, "name": "AI Agent", "aliases": []}]
        result = classify_rule_matches("Breaking news today", "The new AI Agent framework is released", keywords)
        assert len(result["strong"]) == 0
        assert len(result["weak"]) == 1
        assert result["weak"][0]["keyword_id"] == 1

    def test_no_match(self):
        keywords = [{"id": 1, "name": "blockchain", "aliases": []}]
        result = classify_rule_matches("AI is the future", "Machine learning content here", keywords)
        assert result["strong"] == []
        assert result["weak"] == []

    def test_alias_title_match_is_strong(self):
        keywords = [{"id": 1, "name": "AI Agent", "aliases": ["智能体"]}]
        result = classify_rule_matches("智能体框架发布", "一些内容", keywords)
        assert len(result["strong"]) == 1

class TestSemanticMatcher:
    @pytest.mark.asyncio
    async def test_strong_hits_skip_llm(self):
        """Articles with only strong hits should not call LLM."""
        matcher = SemanticMatcher(llm_service=AsyncMock())
        keywords = [{"id": 1, "name": "AI Agent", "aliases": []}]
        articles = [{"id": 100, "title": "AI Agent is here", "cleaned_content": "Content about AI Agent"}]

        results = await matcher.match_batch(articles, keywords)
        matcher.llm_service.call_json.assert_not_called()
        assert len(results) == 1
        assert results[0]["match_method"] == "rule"

    @pytest.mark.asyncio
    async def test_weak_and_miss_trigger_llm(self):
        """Articles without strong hits should be sent to LLM."""
        mock_llm = AsyncMock()
        mock_llm.call_json = AsyncMock(return_value=[
            {"index": 0, "matched_keywords": ["RAG"], "confidence": "high", "reason": "Discusses retrieval augmented generation"}
        ])
        matcher = SemanticMatcher(llm_service=mock_llm)
        keywords = [{"id": 1, "name": "RAG", "aliases": []}]
        articles = [{"id": 100, "title": "New retrieval methods", "cleaned_content": "Discussing retrieval augmented generation approaches"}]

        results = await matcher.match_batch(articles, keywords)
        mock_llm.call_json.assert_called_once()
        assert any(r["match_method"] == "llm" for r in results)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_semantic_matcher.py -v`
Expected: FAIL

- [ ] **Step 3: Implement semantic_matcher.py**

```python
# backend/app/services/semantic_matcher.py
import re
from app.services.keyword_matcher import match_keywords_in_article

def classify_rule_matches(title: str, content: str, keywords: list[dict]) -> dict:
    """Classify rule-based matches into strong (title) and weak (content-only)."""
    all_matches = match_keywords_in_article(title, content, keywords)
    strong = [m for m in all_matches if m["match_location"] == "title"]
    weak = [m for m in all_matches if m["match_location"] == "content"]
    return {"strong": strong, "weak": weak}


class SemanticMatcher:
    def __init__(self, llm_service):
        self.llm_service = llm_service

    async def match_batch(
        self, articles: list[dict], keywords: list[dict], batch_size: int = 20
    ) -> list[dict]:
        """Match a batch of articles against keywords using rule + LLM hybrid.

        Each article dict: {id, title, cleaned_content}
        Each keyword dict: {id, name, aliases}
        Returns: list of {article_id, keyword_id, match_location, context_snippet, match_method, match_reason}
        """
        all_results = []
        needs_llm = []  # (article, unmatched_keyword_ids)

        for article in articles:
            classified = classify_rule_matches(
                article["title"], article.get("cleaned_content") or "", keywords
            )
            # Strong hits go directly
            for match in classified["strong"]:
                all_results.append({
                    "article_id": article["id"],
                    "keyword_id": match["keyword_id"],
                    "match_location": match["match_location"],
                    "context_snippet": match["context_snippet"],
                    "match_method": "rule",
                    "match_reason": None,
                })

            # If there are no strong hits, send to LLM for semantic check
            strong_kw_ids = {m["keyword_id"] for m in classified["strong"]}
            remaining_kws = [k for k in keywords if k["id"] not in strong_kw_ids]
            if remaining_kws:
                needs_llm.append((article, remaining_kws, classified["weak"]))

        # Batch LLM calls
        if needs_llm:
            for i in range(0, len(needs_llm), batch_size):
                batch = needs_llm[i: i + batch_size]
                llm_results = await self._llm_match_batch(batch, keywords)
                all_results.extend(llm_results)

        return all_results

    async def _llm_match_batch(self, batch: list[tuple], all_keywords: list[dict]) -> list[dict]:
        """Send a batch of articles to LLM for semantic matching."""
        # Collect all unique remaining keywords across the batch
        all_remaining_kw_names = set()
        for _, remaining_kws, _ in batch:
            for k in remaining_kws:
                all_remaining_kw_names.add(k["name"])

        kw_name_to_id = {k["name"]: k["id"] for k in all_keywords}

        articles_text = []
        for idx, (article, _, _) in enumerate(batch):
            content_preview = (article.get("cleaned_content") or "")[:300]
            articles_text.append(f"{idx + 1}. 标题：{article['title']}\n   摘要：{content_preview}")

        prompt = (
            f"以下是一批技术文章的标题和摘要，以及一组需要追踪的关键词。\n"
            f"请判断每篇文章与哪些关键词真正相关（语义层面，不要求字面出现）。\n\n"
            f"关键词列表：{', '.join(sorted(all_remaining_kw_names))}\n\n"
            f"文章列表：\n" + "\n".join(articles_text) + "\n\n"
            f'返回 JSON 数组：[{{"index": 1, "matched_keywords": ["关键词名"], "confidence": "high/medium", "reason": "原因"}}]\n'
            f"如果某篇文章不匹配任何关键词，不要包含在结果中。"
        )

        try:
            llm_results = await self.llm_service.call_json("tier2", prompt)
        except Exception:
            # LLM failed — return weak rule matches as fallback
            results = []
            for article, _, weak_matches in batch:
                for m in weak_matches:
                    results.append({
                        "article_id": article["id"],
                        "keyword_id": m["keyword_id"],
                        "match_location": m["match_location"],
                        "context_snippet": m["context_snippet"],
                        "match_method": "rule",
                        "match_reason": "LLM unavailable, fell back to rule match",
                    })
            return results

        results = []
        for item in llm_results:
            idx = item.get("index", 0) - 1
            if idx < 0 or idx >= len(batch):
                continue
            article, _, _ = batch[idx]
            confidence = item.get("confidence", "medium")
            method = "llm" if confidence == "high" else "llm_uncertain"
            for kw_name in item.get("matched_keywords", []):
                kw_id = kw_name_to_id.get(kw_name)
                if kw_id:
                    results.append({
                        "article_id": article["id"],
                        "keyword_id": kw_id,
                        "match_location": "content",
                        "context_snippet": (article.get("cleaned_content") or "")[:200],
                        "match_method": method,
                        "match_reason": item.get("reason", ""),
                    })
        return results
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_semantic_matcher.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/semantic_matcher.py backend/tests/test_semantic_matcher.py
git commit -m "feat: add semantic matcher with rule fast-filter + LLM batch"
```

---

### Task 10: Title similarity dedup service

**Files:**
- Create: `backend/app/services/title_dedup.py`
- Test: `backend/tests/test_title_dedup.py` (create)

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_title_dedup.py
import pytest
from app.services.title_dedup import jaccard_similarity, find_duplicates

class TestJaccardSimilarity:
    def test_identical_titles(self):
        assert jaccard_similarity("Hello World", "Hello World") == 1.0

    def test_completely_different(self):
        assert jaccard_similarity("abc def", "xyz uvw") == 0.0

    def test_partial_overlap(self):
        score = jaccard_similarity("AI Agent Framework Released", "AI Agent Framework Launched")
        assert 0.5 < score < 1.0

    def test_chinese_bigram(self):
        score = jaccard_similarity("人工智能技术发展", "人工智能技术趋势")
        assert score > 0.5

class TestFindDuplicates:
    def test_finds_duplicate_pair(self):
        articles = [
            {"id": 1, "title": "OpenAI releases new AI agent framework", "trust_level": "high"},
            {"id": 2, "title": "OpenAI releases new AI agent framework today", "trust_level": "medium"},
        ]
        dupes = find_duplicates(articles, threshold=0.9)
        assert len(dupes) > 0  # article 2 should be flagged

    def test_no_duplicates(self):
        articles = [
            {"id": 1, "title": "AI Agent developments in 2026", "trust_level": "high"},
            {"id": 2, "title": "Quantum computing breakthrough announced", "trust_level": "medium"},
        ]
        dupes = find_duplicates(articles, threshold=0.9)
        assert len(dupes) == 0

    def test_keeps_higher_trust(self):
        articles = [
            {"id": 1, "title": "Same article title here about AI", "trust_level": "low"},
            {"id": 2, "title": "Same article title here about AI", "trust_level": "high"},
        ]
        dupes = find_duplicates(articles, threshold=0.9)
        # Should flag article 1 (low trust) as duplicate, keep article 2 (high trust)
        assert 1 in dupes
        assert 2 not in dupes

    def test_length_prefilter(self):
        """Titles with >50% length difference should be skipped."""
        articles = [
            {"id": 1, "title": "Short", "trust_level": "high"},
            {"id": 2, "title": "This is a very long title that is completely different in length", "trust_level": "high"},
        ]
        dupes = find_duplicates(articles, threshold=0.9)
        assert len(dupes) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_title_dedup.py -v`
Expected: FAIL

- [ ] **Step 3: Implement title_dedup.py**

```python
# backend/app/services/title_dedup.py
import re

_TRUST_RANK = {"high": 3, "medium": 2, "low": 1}


def _tokenize(title: str) -> set[str]:
    # Detect if primarily Chinese
    chinese_chars = re.findall(r"[\u4e00-\u9fff]", title)
    if len(chinese_chars) > len(title) * 0.3:
        # Chinese: character bigrams
        return {title[i: i + 2] for i in range(len(title) - 1) if not title[i].isspace()}
    else:
        # English: lowercase word tokens
        return set(title.lower().split())


def jaccard_similarity(title_a: str, title_b: str) -> float:
    tokens_a = _tokenize(title_a)
    tokens_b = _tokenize(title_b)
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b
    return len(intersection) / len(union)


def find_duplicates(articles: list[dict], threshold: float = 0.9) -> set[int]:
    """Find duplicate article IDs to filter out.

    Returns set of article IDs that should be marked as filtered.
    Keeps the article with highest trust_level in each duplicate group.
    """
    to_filter = set()
    n = len(articles)

    for i in range(n):
        if articles[i]["id"] in to_filter:
            continue
        for j in range(i + 1, n):
            if articles[j]["id"] in to_filter:
                continue

            # Length pre-filter
            len_i = len(articles[i]["title"])
            len_j = len(articles[j]["title"])
            if max(len_i, len_j) > 0 and min(len_i, len_j) / max(len_i, len_j) < 0.5:
                continue

            sim = jaccard_similarity(articles[i]["title"], articles[j]["title"])
            if sim >= threshold:
                # Keep higher trust, filter lower trust
                rank_i = _TRUST_RANK.get(articles[i].get("trust_level", "low"), 1)
                rank_j = _TRUST_RANK.get(articles[j].get("trust_level", "low"), 1)
                if rank_i >= rank_j:
                    to_filter.add(articles[j]["id"])
                else:
                    to_filter.add(articles[i]["id"])

    return to_filter
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_title_dedup.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/title_dedup.py backend/tests/test_title_dedup.py
git commit -m "feat: add title similarity dedup with Jaccard algorithm"
```

---

### Task 11: LLM process job (Phase 2 — independent APScheduler job)

**Files:**
- Create: `backend/app/services/llm_process_job.py`
- Modify: `backend/app/scheduler.py:18-20` (register new job)
- Modify: `backend/app/main.py:12` (ensure new models are imported for table creation)
- Test: `backend/tests/test_llm_process_job.py` (create)

- [ ] **Step 1: Write failing tests for the job orchestration**

```python
# backend/tests/test_llm_process_job.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import date, datetime, timezone
from app.services.llm_process_job import run_llm_process

@pytest.mark.asyncio
async def test_skips_when_no_pending_articles():
    """Job should return quickly if no articles need processing."""
    with patch("app.services.llm_process_job.async_session") as mock_session_factory:
        mock_session = AsyncMock()
        mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        # Mock: no pending_review articles, no needs_llm_matching articles
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        await run_llm_process()
        # Should not raise, should complete quickly
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_llm_process_job.py -v`
Expected: FAIL — module doesn't exist

- [ ] **Step 3: Implement llm_process_job.py**

```python
# backend/app/services/llm_process_job.py
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
    today = date.today()
    result = await db.execute(
        select(Article).where(
            and_(
                Article.quality_tag != "filtered",
                Article.fetched_at >= datetime(today.year, today.month, today.day, tzinfo=timezone.utc),
            )
        )
    )
    articles = result.scalars().all()
    if len(articles) < 2:
        return

    article_dicts = []
    source_cache = {}
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

            # Update TrendSnapshot
            today = date.today()
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_llm_process_job.py -v`
Expected: PASS

- [ ] **Step 5: Register job in scheduler**

In `backend/app/scheduler.py`, add after the existing crawl job setup:

```python
from app.services.llm_process_job import run_llm_process
from app.config import settings

# In setup_scheduler():
scheduler.add_job(
    run_llm_process, "interval",
    minutes=settings.llm_process_interval_minutes,
    id="llm_process",
    max_instances=1,
)
```

- [ ] **Step 6: Ensure new models are imported in main.py for table creation**

In `backend/app/main.py`, add imports (if not already imported via `__init__.py`):

```python
from app.models.trend_report import TrendReport
from app.models.keyword_correlation import KeywordCorrelation
from app.models.alert import Alert
```

- [ ] **Step 7: Run full test suite**

Run: `cd backend && python -m pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 8: Commit**

```bash
git add backend/app/services/llm_process_job.py backend/tests/test_llm_process_job.py backend/app/scheduler.py backend/app/main.py
git commit -m "feat: add LLM process job as independent APScheduler task"
```

---

## Chunk 4: Module 3 — Deep Analysis Services (Alerts, Trend Reports, Correlations)

### Task 12: Alert service (rule-based detection + LLM analysis)

**Files:**
- Create: `backend/app/services/alert_service.py`
- Test: `backend/tests/test_alert_service.py` (create)

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_alert_service.py
import pytest
from app.services.alert_service import check_spike, check_sustained_rise

class TestCheckSpike:
    def test_spike_detected(self):
        # Average of past 7 days = 5, today = 16 (>= 3x)
        assert check_spike(today_count=16, past_7d_counts=[4, 5, 6, 5, 4, 5, 6]) is True

    def test_no_spike(self):
        assert check_spike(today_count=8, past_7d_counts=[4, 5, 6, 5, 4, 5, 6]) is False

    def test_empty_history(self):
        assert check_spike(today_count=5, past_7d_counts=[]) is False

class TestCheckSustainedRise:
    def test_sustained_rise_detected(self):
        # 3 consecutive days rising with acceleration
        assert check_sustained_rise(recent_counts=[5, 7, 10, 15]) is True

    def test_no_sustained_rise(self):
        assert check_sustained_rise(recent_counts=[5, 4, 6, 5]) is False

    def test_rising_but_decelerating(self):
        # Rising but not accelerating
        assert check_sustained_rise(recent_counts=[5, 8, 10, 11]) is False

    def test_too_few_points(self):
        assert check_sustained_rise(recent_counts=[5, 7]) is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_alert_service.py -v`
Expected: FAIL

- [ ] **Step 3: Implement alert_service.py**

```python
# backend/app/services/alert_service.py
import logging
from datetime import date, datetime, timedelta, timezone
from sqlalchemy import select, and_, func
from app.database import async_session
from app.models.trend_snapshot import TrendSnapshot
from app.models.keyword import Keyword
from app.models.keyword_mention import KeywordMention
from app.models.article import Article
from app.models.alert import Alert
from app.services.llm_service import llm_service

logger = logging.getLogger(__name__)


def check_spike(today_count: int, past_7d_counts: list[int]) -> bool:
    if not past_7d_counts:
        return False
    avg = sum(past_7d_counts) / len(past_7d_counts)
    if avg == 0:
        return today_count >= 3  # arbitrary threshold for zero baseline
    return today_count >= avg * 3


def check_sustained_rise(recent_counts: list[int]) -> bool:
    if len(recent_counts) < 4:
        return False
    last_3 = recent_counts[-3:]
    # Check 3 consecutive rises
    if not (last_3[0] < last_3[1] < last_3[2]):
        return False
    # Check acceleration (second diff > first diff)
    diff1 = last_3[1] - last_3[0]
    diff2 = last_3[2] - last_3[1]
    return diff2 > diff1


async def run_alert_check():
    """Check all active keywords for anomalies and create alerts."""
    async with async_session() as db:
        try:
            keywords = (await db.execute(
                select(Keyword).where(Keyword.is_active == True)  # noqa: E712
            )).scalars().all()

            today = date.today()

            for kw in keywords:
                snapshots = (await db.execute(
                    select(TrendSnapshot).where(
                        and_(
                            TrendSnapshot.keyword_id == kw.id,
                            TrendSnapshot.date >= today - timedelta(days=8),
                            TrendSnapshot.date <= today,
                        )
                    ).order_by(TrendSnapshot.date)
                )).scalars().all()

                if not snapshots:
                    continue

                counts_by_date = {s.date: s.mention_count for s in snapshots}
                today_count = counts_by_date.get(today, 0)
                past_7d = [counts_by_date.get(today - timedelta(days=i), 0) for i in range(1, 8)]
                recent_4d = [counts_by_date.get(today - timedelta(days=i), 0) for i in range(3, -1, -1)]

                if check_spike(today_count, past_7d):
                    avg = sum(past_7d) / len(past_7d) if past_7d else 0
                    await _create_alert(db, kw.id, "spike", today_count, avg, today)

                if check_sustained_rise(recent_4d):
                    await _create_alert(db, kw.id, "sustained_rise", recent_4d[-1], recent_4d[0], today)

            await db.commit()
        except Exception as e:
            await db.rollback()
            logger.error(f"Alert check failed: {e}")


async def _create_alert(db, keyword_id: int, alert_type: str, trigger_val: float, baseline_val: float, today: date):
    """Create alert and attempt LLM analysis."""
    alert = Alert(
        keyword_id=keyword_id,
        alert_type=alert_type,
        trigger_value=trigger_val,
        baseline_value=baseline_val,
        analysis_status="pending",
    )
    db.add(alert)
    await db.flush()

    # Try LLM analysis (Tier 1)
    try:
        mentions = (await db.execute(
            select(Article.title).join(KeywordMention).where(
                and_(
                    KeywordMention.keyword_id == keyword_id,
                    Article.fetched_at >= datetime(today.year, today.month, today.day, tzinfo=timezone.utc) - timedelta(days=2),
                )
            ).limit(10)
        )).scalars().all()

        if mentions:
            kw = (await db.execute(select(Keyword).where(Keyword.id == keyword_id))).scalar_one()
            prompt = (
                f'关键词 "{kw.name}" 在最近出现异常{"飙升" if alert_type == "spike" else "持续上升"}。\n'
                f"相关文章标题：\n" + "\n".join(f"- {t}" for t in mentions) +
                f"\n\n请用一句话总结这个趋势变化的可能原因。"
            )
            analysis = await llm_service.call("tier1", prompt)
            alert.analysis = analysis
            alert.analysis_status = "completed"
    except Exception as e:
        alert.analysis_status = "failed"
        logger.warning(f"Alert LLM analysis failed: {e}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_alert_service.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/alert_service.py backend/tests/test_alert_service.py
git commit -m "feat: add alert service with spike and sustained rise detection"
```

---

### Task 13: Trend report service

**Files:**
- Create: `backend/app/services/trend_reporter.py`
- Test: `backend/tests/test_trend_reporter.py` (create)

- [ ] **Step 1: Write a basic test for daily report generation**

```python
# backend/tests/test_trend_reporter.py
import pytest
from unittest.mock import AsyncMock, patch
from app.services.trend_reporter import build_daily_report_prompt

def test_build_daily_report_prompt():
    prompt = build_daily_report_prompt(
        keyword_name="AI Agent",
        daily_counts=[3, 5, 4, 8, 12, 15, 20],
        trend_direction="rising",
        recent_titles=["OpenAI launches agent framework", "Google A2A protocol"],
    )
    assert "AI Agent" in prompt
    assert "rising" in prompt
    assert "OpenAI" in prompt
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_trend_reporter.py -v`
Expected: FAIL

- [ ] **Step 3: Implement trend_reporter.py**

```python
# backend/app/services/trend_reporter.py
import logging
from datetime import date, timedelta, datetime, timezone
from sqlalchemy import select, and_
from app.database import async_session
from app.models.keyword import Keyword
from app.models.trend_snapshot import TrendSnapshot
from app.models.keyword_mention import KeywordMention
from app.models.article import Article
from app.models.trend_report import TrendReport
from app.services.trend_calculator import detect_trend_direction
from app.services.llm_service import llm_service

logger = logging.getLogger(__name__)


def build_daily_report_prompt(
    keyword_name: str, daily_counts: list[int], trend_direction: str, recent_titles: list[str]
) -> str:
    return (
        f'关键词 "{keyword_name}" 最近 7 天的数据：\n'
        f"- 每日提及次数：{daily_counts}\n"
        f"- 趋势方向：{trend_direction}\n"
        f"- 相关文章标题（最近 5 篇）：\n"
        + "\n".join(f"  {i+1}. {t}" for i, t in enumerate(recent_titles))
        + "\n\n请返回 JSON 格式分析：\n"
        + '{"summary": "一句话趋势总结", "key_drivers": ["驱动因素1", "驱动因素2"], "outlook": "短期展望"}'
    )


async def generate_daily_reports():
    """Generate daily trend reports for all active keywords."""
    async with async_session() as db:
        try:
            keywords = (await db.execute(
                select(Keyword).where(Keyword.is_active == True)  # noqa: E712
            )).scalars().all()

            today = date.today()

            for kw in keywords:
                # Check if report already exists
                existing = (await db.execute(
                    select(TrendReport).where(and_(
                        TrendReport.keyword_id == kw.id,
                        TrendReport.report_date == today,
                        TrendReport.period == "daily",
                    ))
                )).scalar_one_or_none()
                if existing:
                    continue

                # Get 7-day snapshot data
                snapshots = (await db.execute(
                    select(TrendSnapshot).where(and_(
                        TrendSnapshot.keyword_id == kw.id,
                        TrendSnapshot.date >= today - timedelta(days=6),
                        TrendSnapshot.date <= today,
                    )).order_by(TrendSnapshot.date)
                )).scalars().all()

                if not snapshots:
                    continue

                daily_counts = [s.mention_count for s in snapshots]
                daily_scores = [s.score for s in snapshots]
                trend_dir = detect_trend_direction(daily_scores)

                # Get recent article titles
                recent_titles = (await db.execute(
                    select(Article.title).join(KeywordMention).where(
                        KeywordMention.keyword_id == kw.id
                    ).order_by(Article.fetched_at.desc()).limit(5)
                )).scalars().all()

                prompt = build_daily_report_prompt(kw.name, daily_counts, trend_dir, recent_titles)

                try:
                    result = await llm_service.call_json("tier2", prompt)
                    report = TrendReport(
                        keyword_id=kw.id,
                        report_date=today,
                        period="daily",
                        summary=result.get("summary", ""),
                        key_drivers=result.get("key_drivers", []),
                        outlook=result.get("outlook", ""),
                    )
                    db.add(report)
                except Exception as e:
                    logger.warning(f"Daily report for '{kw.name}' failed: {e}")

            await db.commit()
        except Exception as e:
            await db.rollback()
            logger.error(f"Daily report generation failed: {e}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_trend_reporter.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/trend_reporter.py backend/tests/test_trend_reporter.py
git commit -m "feat: add trend report service with daily LLM generation"
```

> **Note:** Weekly reports (Tier 3) are deferred to a follow-up task. This plan implements daily reports only. The `TrendReport` model already supports `period="weekly"`, so adding weekly generation later requires only a new function + scheduler job.

---

### Task 14: Correlation service (pure statistics)

**Files:**
- Create: `backend/app/services/correlation_service.py`
- Test: `backend/tests/test_correlation_service.py` (create)

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_correlation_service.py
import pytest
from app.services.correlation_service import compute_co_occurrence_matrix

def test_co_occurrence_matrix():
    # article 1 matches keywords [1, 2], article 2 matches [2, 3], article 3 matches [1, 2, 3]
    mentions = [
        {"article_id": 1, "keyword_id": 1},
        {"article_id": 1, "keyword_id": 2},
        {"article_id": 2, "keyword_id": 2},
        {"article_id": 2, "keyword_id": 3},
        {"article_id": 3, "keyword_id": 1},
        {"article_id": 3, "keyword_id": 2},
        {"article_id": 3, "keyword_id": 3},
    ]
    matrix = compute_co_occurrence_matrix(mentions)
    assert matrix[(1, 2)] == 2  # articles 1 and 3
    assert matrix[(2, 3)] == 2  # articles 2 and 3
    assert matrix[(1, 3)] == 1  # article 3 only

def test_empty_mentions():
    assert compute_co_occurrence_matrix([]) == {}

def test_single_keyword_per_article():
    mentions = [
        {"article_id": 1, "keyword_id": 1},
        {"article_id": 2, "keyword_id": 2},
    ]
    assert compute_co_occurrence_matrix(mentions) == {}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_correlation_service.py -v`
Expected: FAIL

- [ ] **Step 3: Implement correlation_service.py**

```python
# backend/app/services/correlation_service.py
import logging
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from itertools import combinations
from sqlalchemy import select, and_
from app.database import async_session
from app.models.keyword import Keyword
from app.models.keyword_mention import KeywordMention
from app.models.keyword_correlation import KeywordCorrelation
from app.models.article import Article

logger = logging.getLogger(__name__)


def compute_co_occurrence_matrix(mentions: list[dict]) -> dict[tuple[int, int], int]:
    """Compute keyword co-occurrence counts from mention data.

    Returns dict of {(keyword_id_a, keyword_id_b): count} where a < b.
    """
    # Group keywords by article
    article_keywords = defaultdict(set)
    for m in mentions:
        article_keywords[m["article_id"]].add(m["keyword_id"])

    # Count co-occurrences
    matrix = defaultdict(int)
    for keywords in article_keywords.values():
        if len(keywords) < 2:
            continue
        for a, b in combinations(sorted(keywords), 2):
            matrix[(a, b)] += 1

    return dict(matrix)


async def compute_weekly_correlations():
    """Compute and store keyword correlations for the past week."""
    async with async_session() as db:
        try:
            today = date.today()
            week_ago = today - timedelta(days=7)

            # Get all mentions from the past week
            result = await db.execute(
                select(KeywordMention.article_id, KeywordMention.keyword_id).join(Article).where(
                    Article.fetched_at >= datetime(week_ago.year, week_ago.month, week_ago.day, tzinfo=timezone.utc)
                )
            )
            mentions = [{"article_id": r[0], "keyword_id": r[1]} for r in result.all()]

            matrix = compute_co_occurrence_matrix(mentions)

            for (kw_a, kw_b), count in matrix.items():
                # Upsert
                existing = (await db.execute(
                    select(KeywordCorrelation).where(and_(
                        KeywordCorrelation.keyword_id_a == kw_a,
                        KeywordCorrelation.keyword_id_b == kw_b,
                        KeywordCorrelation.period_start == week_ago,
                        KeywordCorrelation.period_end == today,
                    ))
                )).scalar_one_or_none()

                if existing:
                    existing.co_occurrence_count = count
                else:
                    corr = KeywordCorrelation(
                        keyword_id_a=kw_a, keyword_id_b=kw_b,
                        co_occurrence_count=count,
                        period_start=week_ago, period_end=today,
                    )
                    db.add(corr)

            await db.commit()
            logger.info(f"Computed {len(matrix)} keyword correlations")
        except Exception as e:
            await db.rollback()
            logger.error(f"Correlation computation failed: {e}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_correlation_service.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/correlation_service.py backend/tests/test_correlation_service.py
git commit -m "feat: add keyword correlation service with co-occurrence matrix"
```

---

### Task 15: Wire alert check and daily reports into llm_process_job

**Files:**
- Modify: `backend/app/services/llm_process_job.py`
- Modify: `backend/app/scheduler.py` (add weekly correlation job)

- [ ] **Step 1: Add alert check and daily report to llm_process_job**

In `backend/app/services/llm_process_job.py`, update `run_llm_process()`:

```python
from app.services.alert_service import run_alert_check
from app.services.trend_reporter import generate_daily_reports

async def run_llm_process():
    async with async_session() as db:
        try:
            await _run_title_dedup(db)
            await _run_quality_review(db)
            await _run_semantic_matching(db)
            await db.commit()
        except Exception as e:
            await db.rollback()
            logger.error(f"LLM process job failed: {e}")

    # These run with their own sessions
    await run_alert_check()
    await generate_daily_reports()
```

- [ ] **Step 2: Add weekly correlation job to scheduler**

In `backend/app/scheduler.py`, add:

```python
from app.services.correlation_service import compute_weekly_correlations

# In setup_scheduler():
scheduler.add_job(
    compute_weekly_correlations, "cron",
    day_of_week="mon", hour=2, minute=0,
    id="weekly_correlations",
    max_instances=1,
)
```

- [ ] **Step 3: Run full test suite**

Run: `cd backend && python -m pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/llm_process_job.py backend/app/scheduler.py
git commit -m "feat: wire alerts and daily reports into LLM process job"
```

---

## Chunk 5: API Endpoints + Frontend

### Task 16: Alerts API router

**Files:**
- Create: `backend/app/routers/alerts.py`
- Modify: `backend/app/main.py` (register router)
- Test: manual testing via API

- [ ] **Step 1: Create alerts router**

```python
# backend/app/routers/alerts.py
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.alert import Alert
from app.models.keyword import Keyword
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

router = APIRouter(prefix="/api/alerts", tags=["alerts"])

class AlertResponse(BaseModel):
    id: int
    keyword_id: int
    keyword_name: str
    alert_type: str
    trigger_value: float
    baseline_value: float
    analysis: Optional[str]
    analysis_status: str
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True

@router.get("")
async def list_alerts(unread_only: bool = False, db: AsyncSession = Depends(get_db)):
    query = select(Alert, Keyword.name).join(Keyword).order_by(Alert.created_at.desc())
    if unread_only:
        query = query.where(Alert.is_read == False)  # noqa: E712
    result = await db.execute(query)
    alerts = []
    for alert, kw_name in result.all():
        alerts.append(AlertResponse(
            id=alert.id, keyword_id=alert.keyword_id, keyword_name=kw_name,
            alert_type=alert.alert_type, trigger_value=alert.trigger_value,
            baseline_value=alert.baseline_value, analysis=alert.analysis,
            analysis_status=alert.analysis_status, is_read=alert.is_read,
            created_at=alert.created_at,
        ))
    return alerts

@router.put("/{alert_id}/read")
async def mark_alert_read(alert_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Alert).where(Alert.id == alert_id))
    alert = result.scalar_one_or_none()
    if not alert:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Alert not found")
    alert.is_read = True
    await db.commit()
    return {"status": "ok"}
```

- [ ] **Step 2: Register router in main.py**

Add to `backend/app/main.py`:

```python
from app.routers import alerts
app.include_router(alerts.router)
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/routers/alerts.py backend/app/main.py
git commit -m "feat: add alerts API endpoints"
```

---

### Task 17: Trend report and correlation API endpoints

**Files:**
- Modify: `backend/app/routers/trends.py`
- Modify: `backend/app/routers/sources.py` (add trust_level to CRUD + stats endpoint)

- [ ] **Step 1: Add report and correlation endpoints to trends router**

Add imports to `backend/app/routers/trends.py` (add `and_` to existing sqlalchemy imports if not present):

```python
from sqlalchemy import and_
from app.models.trend_report import TrendReport
from app.models.keyword_correlation import KeywordCorrelation

@router.get("/report")
async def get_trend_report(keyword_id: int, period: str = "daily", db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(TrendReport).where(
            and_(TrendReport.keyword_id == keyword_id, TrendReport.period == period)
        ).order_by(TrendReport.report_date.desc()).limit(7)
    )
    return result.scalars().all()

@router.get("/correlations")
async def get_correlations(keyword_id: int, db: AsyncSession = Depends(get_db)):
    from sqlalchemy import or_
    result = await db.execute(
        select(KeywordCorrelation, Keyword.name).join(
            Keyword,
            or_(
                KeywordCorrelation.keyword_id_b == Keyword.id,
                KeywordCorrelation.keyword_id_a == Keyword.id,
            )
        ).where(
            or_(KeywordCorrelation.keyword_id_a == keyword_id, KeywordCorrelation.keyword_id_b == keyword_id)
        ).where(Keyword.id != keyword_id).order_by(KeywordCorrelation.co_occurrence_count.desc())
    )
    correlations = []
    for corr, kw_name in result.all():
        correlations.append({
            "related_keyword": kw_name,
            "co_occurrence_count": corr.co_occurrence_count,
            "period_start": str(corr.period_start),
            "period_end": str(corr.period_end),
        })
    return correlations
```

- [ ] **Step 2: Add trust_level to source CRUD and stats endpoint**

In `backend/app/routers/sources.py`:
- Update `SourceCreate` to include `trust_level: str = "low"`
- Update `SourceUpdate` to include `trust_level: Optional[str] = None`
- Update `SourceResponse` to include `trust_level: str = "low"` (so frontend can display it)
- Add stats endpoint:

```python
@router.get("/{source_id}/stats")
async def source_stats(source_id: int, db: AsyncSession = Depends(get_db)):
    from app.models.article import Article
    total = (await db.execute(
        select(func.count(Article.id)).where(Article.source_id == source_id)
    )).scalar() or 0
    passed = (await db.execute(
        select(func.count(Article.id)).where(
            and_(Article.source_id == source_id, Article.quality_tag == "passed")
        )
    )).scalar() or 0
    return {
        "total_articles": total,
        "passed_articles": passed,
        "pass_rate": round(passed / total * 100, 1) if total > 0 else 0,
    }
```

- [ ] **Step 3: Run full backend test suite**

Run: `cd backend && python -m pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
git add backend/app/routers/trends.py backend/app/routers/sources.py
git commit -m "feat: add trend report, correlation, and source stats API endpoints"
```

---

### Task 18: Frontend — update API client with new interfaces and endpoints

**Files:**
- Modify: `frontend/src/api/client.ts`

- [ ] **Step 1: Add new TypeScript interfaces and API methods**

Add to `frontend/src/api/client.ts`:

```typescript
// New interfaces
export interface AlertItem {
  id: number;
  keyword_id: number;
  keyword_name: string;
  alert_type: 'spike' | 'sustained_rise';
  trigger_value: number;
  baseline_value: number;
  analysis: string | null;
  analysis_status: 'pending' | 'completed' | 'failed';
  is_read: boolean;
  created_at: string;
}

export interface TrendReportItem {
  id: number;
  keyword_id: number;
  report_date: string;
  period: string;
  summary: string;
  key_drivers: string[];
  outlook: string;
  generated_at: string;
}

export interface CorrelationItem {
  related_keyword: string;
  co_occurrence_count: number;
  period_start: string;
  period_end: string;
}

export interface SourceStats {
  total_articles: number;
  passed_articles: number;
  pass_rate: number;
}

// New API modules
export const alertsApi = {
  list: (unreadOnly = false) =>
    api.get<AlertItem[]>(`/alerts`, { params: { unread_only: unreadOnly } }).then(r => r.data),
  markRead: (id: number) =>
    api.put(`/alerts/${id}/read`).then(r => r.data),
};

// Add to trendsApi:
//   reports: (keywordId: number, period = 'daily') =>
//     api.get<TrendReportItem[]>('/trends/report', { params: { keyword_id: keywordId, period } }).then(r => r.data),
//   correlations: (keywordId: number) =>
//     api.get<CorrelationItem[]>('/trends/correlations', { params: { keyword_id: keywordId } }).then(r => r.data),

// Add to sourcesApi:
//   stats: (id: number) =>
//     api.get<SourceStats>(`/sources/${id}/stats`).then(r => r.data),
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api/client.ts
git commit -m "feat: add alerts, trend reports, correlations to frontend API client"
```

---

### Task 19: Frontend — Dashboard alerts and trend insights

**Files:**
- Modify: `frontend/src/pages/Dashboard.tsx`

- [ ] **Step 1: Read current Dashboard.tsx**

Read `frontend/src/pages/Dashboard.tsx` to understand current structure.

- [ ] **Step 2: Add alert notification bar and trend insights**

Add to Dashboard.tsx:
- Import `alertsApi, AlertItem` from API client
- Add `alerts` state, fetch unread alerts in useEffect
- Render alert bar at top of page (before keyword cards):
  - Red/amber badges for unread alerts
  - Expand to show analysis text
  - "Mark as read" button
- Add trend summary text below each keyword card (from heatmap data's trend field)

- [ ] **Step 3: Verify build**

Run: `cd frontend && npm run build`
Expected: Build succeeds

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/Dashboard.tsx
git commit -m "feat: add alert notifications and trend insights to Dashboard"
```

---

### Task 20: Frontend — Trend Analysis page enhancements

**Files:**
- Modify: `frontend/src/pages/TrendAnalysis.tsx`

- [ ] **Step 1: Read current TrendAnalysis.tsx**

- [ ] **Step 2: Add trend report card and correlation sidebar**

When a keyword is selected:
- Fetch trend report via `trendsApi.reports(keywordId)`
- Display below chart: summary, key drivers (as tags), outlook
- Fetch correlations via `trendsApi.correlations(keywordId)`
- Display "Related Topics" list with co-occurrence count

- [ ] **Step 3: Verify build**

Run: `cd frontend && npm run build`
Expected: Build succeeds

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/TrendAnalysis.tsx
git commit -m "feat: add trend reports and correlations to TrendAnalysis page"
```

---

### Task 21: Frontend — Source management trust_level + stats

**Files:**
- Modify: `frontend/src/pages/SourceManage.tsx`

- [ ] **Step 1: Read current SourceManage.tsx**

- [ ] **Step 2: Add trust_level dropdown and pass_rate display**

- Add `trust_level` dropdown (high/medium/low) to source create/edit form
- Add "Trust Level" column to source table with dropdown for inline editing
- Add "Pass Rate" column showing quality stats from `/sources/{id}/stats`

- [ ] **Step 3: Verify build**

Run: `cd frontend && npm run build`
Expected: Build succeeds

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/SourceManage.tsx
git commit -m "feat: add trust level and quality stats to source management"
```

---

### Task 22: Frontend — Keyword mentions enhanced display

**Files:**
- Modify: `frontend/src/pages/KeywordManage.tsx`

- [ ] **Step 1: Read current KeywordManage.tsx**

- [ ] **Step 2: Enhance article mentions display**

In the expandable mentions list:
- Show article summary (if available)
- Show quality tag as a small badge (passed/filtered)
- Show match method badge (rule/llm/llm_uncertain)

- [ ] **Step 3: Verify build**

Run: `cd frontend && npm run build`
Expected: Build succeeds

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/KeywordManage.tsx
git commit -m "feat: enhance keyword mentions with summary, quality, and match method"
```

---

## Chunk 6: Integration Testing + Final Verification

### Task 23: End-to-end integration test

**Files:**
- Create: `backend/tests/test_integration_v2.py`

- [ ] **Step 1: Write integration test covering the full V2 pipeline**

```python
# backend/tests/test_integration_v2.py
import pytest
from unittest.mock import AsyncMock, patch
from datetime import date
from sqlalchemy import select
from app.models.data_source import DataSource
from app.models.keyword import Keyword
from app.models.article import Article
from app.models.keyword_mention import KeywordMention
from app.models.trend_snapshot import TrendSnapshot

@pytest.mark.asyncio
async def test_full_pipeline_high_trust_source(db_session):
    """High trust source article should be cleaned, scored, and matched via rules."""
    source = DataSource(name="Anthropic Blog", type="rss", url="http://blog.anthropic.com", trust_level="high")
    db_session.add(source)
    kw = Keyword(name="Claude", aliases=["claude model"])
    db_session.add(kw)
    await db_session.flush()

    from app.services.crawler import crawler_service
    article_data = {
        "title": "Introducing Claude 4: A new era for AI",
        "url": "http://blog.anthropic.com/claude-4",
        "content": "<p>We are excited to announce Claude 4.</p><script>tracking()</script><div class='ad-banner'>Sponsored</div>",
        "published_at": None,
    }
    await crawler_service._process_article(db_session, source, article_data, [{"id": kw.id, "name": "Claude", "aliases": ["claude model"]}])
    await db_session.flush()

    article = (await db_session.execute(
        select(Article).where(Article.url == "http://blog.anthropic.com/claude-4")
    )).scalar_one()

    # Cleaned
    assert article.cleaned_content is not None
    assert "tracking" not in article.cleaned_content
    assert "Sponsored" not in article.cleaned_content

    # Quality: high trust (80) + good title (+5) + short content (+5 or -20) = ~65-90
    assert article.quality_tag == "passed"

    # Summary generated
    assert article.summary is not None

    # Rule match: "Claude" in title = strong hit
    mentions = (await db_session.execute(
        select(KeywordMention).where(KeywordMention.article_id == article.id)
    )).scalars().all()
    assert len(mentions) >= 1
    assert mentions[0].match_method == "rule"

@pytest.mark.asyncio
async def test_low_quality_article_filtered(db_session):
    """Low trust + spam signals should filter article."""
    source = DataSource(name="Spam Site", type="rss", url="http://spam.xyz", trust_level="low")
    db_session.add(source)
    kw = Keyword(name="AI", aliases=[])
    db_session.add(kw)
    await db_session.flush()

    from app.services.crawler import crawler_service
    article_data = {
        "title": "AD",
        "url": "http://spam.xyz/ad/redirect/buy-now",
        "content": "",
        "published_at": None,
    }
    await crawler_service._process_article(db_session, source, article_data, [{"id": kw.id, "name": "AI", "aliases": []}])
    await db_session.flush()

    article = (await db_session.execute(
        select(Article).where(Article.url == "http://spam.xyz/ad/redirect/buy-now")
    )).scalar_one()
    assert article.quality_tag == "filtered"

    # No keyword mentions should be created
    mentions = (await db_session.execute(
        select(KeywordMention).where(KeywordMention.article_id == article.id)
    )).scalars().all()
    assert len(mentions) == 0
```

- [ ] **Step 2: Run integration tests**

Run: `cd backend && python -m pytest tests/test_integration_v2.py -v`
Expected: ALL PASS

- [ ] **Step 3: Run full test suite**

Run: `cd backend && python -m pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 4: Commit**

```bash
git add backend/tests/test_integration_v2.py
git commit -m "test: add V2 end-to-end integration tests"
```

---

### Task 24: Frontend build verification + full type check

- [ ] **Step 1: TypeScript type check**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 2: ESLint**

Run: `cd frontend && npm run lint`
Expected: No errors (or only pre-existing warnings)

- [ ] **Step 3: Production build**

Run: `cd frontend && npm run build`
Expected: Build succeeds

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "chore: V2 data intelligence upgrade complete"
```
