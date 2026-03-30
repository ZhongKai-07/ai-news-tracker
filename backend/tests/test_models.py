import pytest
from datetime import date
from sqlalchemy import inspect
from app.database import Base
from app.models import DataSource, Article, Keyword, KeywordMention, TrendSnapshot
from app.models.trend_report import TrendReport
from app.models.keyword_correlation import KeywordCorrelation
from app.models.alert import Alert

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

@pytest.mark.asyncio
async def test_article_new_fields(db_session):
    source = DataSource(name="test", type="rss", url="http://test.com")
    db_session.add(source)
    await db_session.flush()
    article = Article(
        source_id=source.id, title="Test Article", url="http://test.com/1",
        cleaned_content="Clean text here", quality_score=75,
        quality_tag="passed", summary="A test summary.", needs_llm_matching=False,
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
    assert source.trust_level == "low"

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
