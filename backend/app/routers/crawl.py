import asyncio

from fastapi import APIRouter, HTTPException

from app.database import async_session
from app.services.crawler import crawler_service

router = APIRouter(prefix="/api/crawl", tags=["crawl"])


async def _run_crawl_in_background():
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
