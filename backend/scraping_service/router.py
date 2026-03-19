"""Scraping/events service API routes."""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db, Event
from .rss_scraper import fetch_all_feeds, fetch_article_text
from .nlp_extractor import extract_event
from geolocation_service import geocode_location

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/events", tags=["events"])


async def run_scraping_pipeline(db: AsyncSession):
    """
    Full scraping pipeline:
    1. Fetch RSS articles
    2. Run NLP extraction
    3. Geocode locations
    4. Store events
    """
    articles = await fetch_all_feeds()
    new_events = 0

    # Phase 1: Extract events from articles (CPU-bound, run in thread)
    extracted_articles = []
    for article in articles:
        text_content = article.summary
        if not text_content or not text_content.strip():
            continue

        # Run spaCy NLP in thread to avoid blocking event loop
        extracted = await asyncio.to_thread(extract_event, article.title, text_content)
        if not extracted:
            continue
        extracted_articles.append((article, extracted))

    logger.info("Extracted %d conflict events from %d articles", len(extracted_articles), len(articles))

    # Phase 2: Collect unique locations and batch geocode
    unique_locations: dict[str, tuple[float, float] | None] = {}
    for _, extracted in extracted_articles:
        for loc in extracted.locations:
            if loc not in unique_locations:
                unique_locations[loc] = None  # placeholder

    # Geocode all unique locations
    for loc in unique_locations:
        coords = await geocode_location(loc)
        unique_locations[loc] = coords

    logger.info("Geocoded %d unique locations", len(unique_locations))

    # Phase 3: Store events with geocoded locations
    for article, extracted in extracted_articles:
        # Find first geocoded location
        lat, lon = None, None
        location_name = None
        for loc in extracted.locations:
            coords = unique_locations.get(loc)
            if coords:
                lat, lon = coords
                location_name = loc
                break

        if lat is None or lon is None:
            continue  # skip events we can't place on the map

        # Check for duplicate
        existing = await db.execute(
            select(Event).where(
                Event.title == article.title,
                Event.source_url == article.url,
            )
        )
        if existing.scalar_one_or_none():
            continue

        event = Event(
            event_type=extracted.event_type,
            title=article.title[:500],
            summary=extracted.summary[:2000],
            location_name=location_name,
            latitude=lat,
            longitude=lon,
            coordinates=f"SRID=4326;POINT({lon} {lat})",
            event_time=article.published or datetime.now(timezone.utc),
            source_url=article.url,
            source_name=article.source,
            raw_text=(article.summary or "")[:2000],
        )
        db.add(event)
        new_events += 1

        # Flush periodically so one bad event doesn't kill the whole batch
        if new_events % 10 == 0:
            try:
                await db.flush()
            except Exception:
                await db.rollback()
                logger.exception("Failed to flush batch at %d events", new_events)
                return new_events

    try:
        await db.commit()
    except Exception:
        await db.rollback()
        logger.exception("Failed to persist events")

    logger.info("Scraping pipeline complete: %d new events from %d articles", new_events, len(articles))
    return new_events


@router.get("")
async def get_events(
    event_type: Optional[str] = Query(None),
    hours: int = Query(168, ge=1, le=720),  # default 7 days
    min_lat: Optional[float] = Query(None),
    min_lon: Optional[float] = Query(None),
    max_lat: Optional[float] = Query(None),
    max_lon: Optional[float] = Query(None),
    limit: int = Query(500, ge=1, le=2000),
    db: AsyncSession = Depends(get_db),
):
    """Query events with filters."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

    q = select(Event).where(Event.event_time >= cutoff)

    if event_type:
        q = q.where(Event.event_type == event_type)

    # Bounding box filter using PostGIS
    if all(v is not None for v in [min_lat, min_lon, max_lat, max_lon]):
        q = q.where(
            text(
                "ST_Within(coordinates, ST_MakeEnvelope(:min_lon, :min_lat, :max_lon, :max_lat, 4326))"
            ).bindparams(
                min_lon=min_lon, min_lat=min_lat, max_lon=max_lon, max_lat=max_lat
            )
        )

    q = q.order_by(Event.event_time.desc()).limit(limit)

    result = await db.execute(q)
    events = result.scalars().all()

    return {
        "count": len(events),
        "events": [
            {
                "id": e.id,
                "event_type": e.event_type,
                "title": e.title,
                "summary": e.summary,
                "location_name": e.location_name,
                "latitude": e.latitude,
                "longitude": e.longitude,
                "event_time": e.event_time.isoformat() if e.event_time else None,
                "source_url": e.source_url,
                "source_name": e.source_name,
            }
            for e in events
        ],
    }


@router.get("/types")
async def get_event_types(db: AsyncSession = Depends(get_db)):
    """Get distinct event types currently in the database."""
    result = await db.execute(
        select(Event.event_type).distinct()
    )
    types = [row[0] for row in result.all()]
    return {"types": types}
