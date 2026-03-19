"""
OSINT Viewer - FastAPI Backend
Main application entry point.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from flight_service.router import router as flight_router
from scraping_service.router import router as scraping_router
from agent.reviewer import run_full_review
from scheduler import start_scheduler, shutdown_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    logger.info("Starting OSINT Viewer backend...")
    start_scheduler()
    yield
    shutdown_scheduler()
    logger.info("OSINT Viewer backend stopped.")


app = FastAPI(
    title="OSINT Viewer",
    description="Open-Source Intelligence Dashboard API",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS - allow frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount service routers
app.include_router(flight_router)
app.include_router(scraping_router)


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "osint-viewer"}


@app.get("/api/review")
async def code_review():
    """Run code review agent and return report."""
    report = await run_full_review()
    return report
