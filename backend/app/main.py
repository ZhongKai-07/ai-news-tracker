from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import engine, Base
from app.scheduler import setup_scheduler, scheduler
# Import V2 models so Base.metadata.create_all creates their tables
from app.models.trend_report import TrendReport  # noqa: F401
from app.models.keyword_correlation import KeywordCorrelation  # noqa: F401
from app.models.alert import Alert  # noqa: F401


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    setup_scheduler()
    yield
    scheduler.shutdown()
    await engine.dispose()


app = FastAPI(title="AI News Trend Tracker", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.routers import keywords, sources, trends, crawl, articles, summary

app.include_router(keywords.router)
app.include_router(sources.router)
app.include_router(trends.router)
app.include_router(crawl.router)
app.include_router(articles.router)
app.include_router(summary.router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
