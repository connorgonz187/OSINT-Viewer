"""
APScheduler jobs for periodic data refresh.
"""

import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import settings
from database.connection import async_session
from flight_service.router import refresh_military_flights
from scraping_service.router import run_scraping_pipeline

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


async def flight_refresh_job():
    """Periodic job to refresh military flight data."""
    async with async_session() as db:
        try:
            await refresh_military_flights(db)
        except Exception:
            logger.exception("Flight refresh job failed")


async def scraping_refresh_job():
    """Periodic job to run scraping pipeline."""
    async with async_session() as db:
        try:
            await run_scraping_pipeline(db)
        except Exception:
            logger.exception("Scraping refresh job failed")


def start_scheduler():
    """Start background scheduler with configured intervals."""
    scheduler.add_job(
        flight_refresh_job,
        "interval",
        seconds=settings.FLIGHT_REFRESH_INTERVAL,
        id="flight_refresh",
        replace_existing=True,
        max_instances=1,
    )
    scheduler.add_job(
        scraping_refresh_job,
        "interval",
        seconds=settings.SCRAPING_REFRESH_INTERVAL,
        id="scraping_refresh",
        replace_existing=True,
        max_instances=1,
    )

    # Run initial fetch on startup (after short delay)
    scheduler.add_job(flight_refresh_job, "date", id="flight_initial")
    scheduler.add_job(scraping_refresh_job, "date", id="scraping_initial")

    scheduler.start()
    logger.info(
        "Scheduler started: flights every %ds, scraping every %ds",
        settings.FLIGHT_REFRESH_INTERVAL,
        settings.SCRAPING_REFRESH_INTERVAL,
    )


def shutdown_scheduler():
    """Gracefully shut down scheduler."""
    scheduler.shutdown(wait=False)
    logger.info("Scheduler stopped")
