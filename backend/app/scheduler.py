import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.database import async_session
from app.services.crawler import crawler_service

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler()


async def scheduled_crawl():
    async with async_session() as db:
        try:
            await crawler_service.run(db)
        except RuntimeError:
            logger.info("Skipping scheduled crawl — already running")


def setup_scheduler():
    scheduler.add_job(scheduled_crawl, "interval", hours=6, id="default_crawl", replace_existing=True)
    scheduler.start()
