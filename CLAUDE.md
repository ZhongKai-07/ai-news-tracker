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

## Test Setup

pytest with `asyncio_mode = auto` in `backend/pytest.ini`. Tests use in-memory SQLite. Currently 25 backend tests; no frontend tests.
