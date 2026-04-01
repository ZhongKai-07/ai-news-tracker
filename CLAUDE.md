# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI News Trend Tracker — a full-stack system that crawls tech news via RSS/web scraping, matches keywords, and visualizes trends as heatmaps with multi-keyword color comparison. FastAPI backend + React/TypeScript frontend with SQLite.

## Commands

### Backend

```bash
# Activate venv (required — system Python doesn't work, exits code 49)
cd backend
source ../.venv/Scripts/activate   # Windows Git Bash
# source ../.venv/bin/activate     # macOS / Linux

# Run server
python -m uvicorn app.main:app --reload --port 8001

# Run all tests
python -m pytest tests/ -v

# Run single test file
python -m pytest tests/test_keyword_matcher.py -v
```

### Frontend

```bash
cd frontend
npm run dev       # Dev server on :5173
npm run build     # Production build (tsc + vite build)
npm run lint      # ESLint
npx tsc --noEmit  # Type check only
```

## Architecture

### Backend (`backend/app/`)

- `main.py` — FastAPI app with lifespan (creates tables on startup, starts APScheduler). Registers 6 routers. CORS allows `localhost:5173`.
- `config.py` — pydantic-settings, reads `.env`, defaults to SQLite at `./ai_news.db`
- `database.py` — async SQLAlchemy engine + session factory (`async_session` and `get_db` dependency)
- `scheduler.py` — APScheduler runs crawl every 6 hours

**Models** (`models/`):
- `DataSource` — RSS/scraper/API sources with status tracking, proxy, auth_config, exponential backoff fields. Delete is soft (status=disabled).
- `Article` — url has UNIQUE constraint for dedup
- `Keyword` — aliases stored as JSON array, soft-delete via `is_active` flag
- `KeywordMention` — links keyword to article with match_location (title/content) and context_snippet
- `TrendSnapshot` — one row per (keyword_id, date) pair (UniqueConstraint)

**Services** (`services/`):
- `crawler.py` — `CrawlerService` singleton. `asyncio.Lock` prevents concurrent runs. `Semaphore` limits per-source concurrency. Each source gets its own DB session via `async_session()`. Exponential backoff after `failure_backoff_threshold` (default 3) consecutive failures. On error: rollback first, then re-fetch source and update error state.
- `keyword_matcher.py` — case-insensitive substring match, title priority over content, one match per keyword per article
- `trend_calculator.py` — score = `log(1 + raw)` where title=2x weight, content=1x, multiplied by source weight. Trend direction by comparing first/second half averages (threshold 0.3)
- `rss_parser.py` / `web_scraper.py` — data fetching via aiohttp

**Routers** (`routers/`):
- `keywords.py` — CRUD + soft delete + rescan (background task with own session)
- `sources.py` — CRUD, delete is soft (sets status=disabled), list filters out disabled by default (`?include_disabled=true` to show all)
- `trends.py` — heatmap/hot/trends endpoints. `PERIOD_DAYS` supports 7d/30d/90d/120d.
- `crawl.py` — trigger (409 if running, background task with own session) + status
- `articles.py` — article list + keyword mentions with source_name (joins DataSource)
- `summary.py` — weekly summary (pure data aggregation, no LLM)

### Frontend (`frontend/src/`)

**CSS Design System** (`App.css`):
- Reusable classes: `.card`, `.btn` / `.btn-primary` / `.btn-danger` / `.btn-sm`, `.btn-group`, `.table`, `.badge` / `.badge-success` / `.badge-error`, `.form-row`, `.input`, `.empty-state`, `.loading-pulse`
- Sidebar: fixed position, gradient background, `nav-icon` + text labels

**Pages** (`pages/`):
- `Dashboard.tsx` — keyword trend cards + hot topics + 7-day heatmap. Shows onboarding empty state when no data.
- `TrendAnalysis.tsx` — keyword selector (with Select All/Clear), period toggle (7d/30d/90d/120d), heatmap/line view toggle. Loading state.
- `KeywordManage.tsx` — CRUD form in card + table with expandable article mentions per keyword. Help text for aliases and rescan.
- `SourceManage.tsx` — CRUD form + crawl trigger with pulsing animation. Empty state suggests popular RSS feeds with one-click "Use" button.

**Components** (`components/`):
- `HeatmapChart.tsx` / `TrendLineChart.tsx` — ECharts wrappers
- `KeywordSelector.tsx` — checkbox list in card with Select All / Clear

**API Client** (`api/client.ts`):
- Axios instance → `localhost:8001/api`
- Typed interfaces: `Keyword`, `DataSource`, `HeatmapSeries`, `TrendDataPoint`, `MentionItem`
- API groups: `keywordsApi`, `sourcesApi`, `trendsApi`, `articlesApi`, `crawlApi`

## Key Design Decisions

- Background tasks (crawl trigger, keyword rescan) create their own DB sessions via `async_session()` — never pass request-scoped sessions to `asyncio.create_task`
- Each source is crawled in its own DB session within `_crawl_source` — errors rollback that session, re-fetch the source, then update error state
- SQLite doesn't preserve timezone info — naive datetimes from DB must be made aware (`.replace(tzinfo=timezone.utc)`) before comparing with `datetime.now(timezone.utc)`
- All timestamps stored in UTC; frontend converts to local timezone
- TrendSnapshot stores one row per (keyword, date). Frontend queries date ranges; no period column
- Score accumulation is incremental: reverse log to get raw, add new mention's contribution, re-log
- Source deletion is soft (status=disabled) to avoid foreign key issues with existing articles

## V2 Data Intelligence Upgrade (In Progress)

**Branch:** `v2-data-intelligence` | **Safety tags:** `v2-before-chunk-1`, `v2-before-chunk-2`

Chunk 1 (Foundation) completed — adds:
- LLM config fields in `config.py` (11 new settings: `llm_provider`, `llm_base_url`, `llm_api_key`, tier models, timeout, retries, batch size, circuit breaker threshold, process interval)
- V2 fields on existing models: `Article` (cleaned_content, quality_score, quality_tag, summary, needs_llm_matching), `DataSource` (trust_level), `KeywordMention` (match_method, match_reason)
- New models: `TrendReport`, `KeywordCorrelation`, `Alert` in `models/`
- `services/llm_service.py` — LLMService with tiered model routing (tier1/2/3), retry with backoff, circuit breaker, tier degradation. Factory `create_llm_service()` and module-level `llm_service` singleton.
- Alembic migration infrastructure (`backend/alembic/`) configured for async SQLite with `render_as_batch=True`
- Shared test fixtures in `tests/conftest.py`

Chunk 2 (Data Cleaning Pipeline) completed — adds:
- `services/content_cleaner.py` — `clean_html()` (BeautifulSoup HTML sanitization: removes script/style/nav/footer/aside/iframe/form + ad divs, extracts article/main content), `complete_data()` (title/published_at fallbacks), `extract_summary()` (extractive summary with Chinese/English sentence splitting)
- `services/quality_scorer.py` — `calculate_quality_score()` multi-signal rule-based scoring: trust_level base + content completeness + URL/title spam detection, clamped to 0-100, three-tier quality_tag (passed ≥60 / pending_review 30-59 / filtered <30)
- Crawler `_process_article` integrated with cleaning pipeline: HTML sanitize → data complete → quality score → summary extract → quality-gated keyword matching. Filtered articles skip matching; pending_review articles marked `needs_llm_matching=True`; passed articles do rule matching with `match_method="rule"`, content-only hits also marked for LLM

Chunk 3 (Semantic Matching + LLM Job) completed — adds:
- `services/semantic_matcher.py` — `classify_rule_matches()` splits matches into strong (title) and weak (content-only). `SemanticMatcher` class does hybrid rule + LLM matching: strong hits skip LLM, weak/miss articles batched for Tier 2 LLM semantic matching. Falls back to rule matches if LLM fails.
- `services/title_dedup.py` — `jaccard_similarity()` with Chinese bigram / English word tokenization. `find_duplicates()` flags lower-trust duplicates when Jaccard ≥ 0.9, with length pre-filter.
- `services/llm_process_job.py` — `run_llm_process()` independent APScheduler job (every 10min): title dedup → Tier 1 quality review of pending_review articles → Tier 2 semantic matching for needs_llm_matching articles. Creates KeywordMentions and updates TrendSnapshots.
- `scheduler.py` updated to register `llm_process` job with `max_instances=1`
- `main.py` imports V2 models (TrendReport, KeywordCorrelation, Alert) for table creation

Remaining: Chunk 4 (deep analysis), Chunk 5 (API + frontend), Chunk 6 (integration tests).

## Dev reference specification and implementation plans
- specs: `ai-news-tracker\docs\superpowers\specs\2026-03-30-v2-data-intelligence-design.md`
- implementation plans: `ai-news-tracker\docs\superpowers\plans\2026-03-30-v2-data-intelligence.md`
- dev log: `ai-news-tracker\docs\dev-log\2026-03-30-v2-execution-strategy.md`

## Test Setup

pytest with `asyncio_mode = auto` in `backend/pytest.ini`. Tests use in-memory SQLite. Currently 93 backend tests (25 original + 14 Chunk1 + 26 Chunk2 + 28 Chunk3); no frontend tests.
