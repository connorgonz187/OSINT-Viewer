"""Scraping/events service API routes."""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, text, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db, Event
from .rss_scraper import fetch_all_feeds, fetch_article_text
from .nlp_extractor import extract_event
from .ai_classifier import classify_with_ai
from geolocation_service import geocode_location

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/events", tags=["events"])

# Lock to prevent concurrent AI classification runs (expensive on Pi)
_ai_classify_lock = asyncio.Lock()


async def run_scraping_pipeline(db: AsyncSession):
    """
    Full scraping pipeline (regex-based, runs automatically):
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

    # Phase 3: Pre-fetch existing events to avoid N+1 duplicate checks
    article_keys = [(a.title, a.url) for a, _ in extracted_articles]
    existing_keys: set[tuple[str, str]] = set()
    if article_keys:
        # Batch query: fetch all (title, source_url) pairs that already exist
        BATCH = 200
        for i in range(0, len(article_keys), BATCH):
            batch_keys = article_keys[i:i + BATCH]
            result = await db.execute(
                select(Event.title, Event.source_url).where(
                    tuple_(Event.title, Event.source_url).in_(batch_keys)
                )
            )
            existing_keys.update((row[0], row[1]) for row in result.all())

    # Store events with geocoded locations
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

        # Check for duplicate using pre-fetched set
        if (article.title, article.url) in existing_keys:
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


async def run_ai_classification(db: AsyncSession) -> dict:
    """
    AI-powered pipeline (on-demand, triggered by user):
    1. Fetch fresh RSS articles
    2. Send to Claude for classification
    3. Geocode AI-identified locations
    4. Store/update events
    """
    articles = await fetch_all_feeds()
    if not articles:
        return {"status": "no_articles", "new_events": 0, "reclassified": 0}

    # Build article dicts for AI, tracking original indices
    article_dicts = []
    dict_to_article_idx: list[int] = []
    for idx, a in enumerate(articles):
        if not a.summary or not a.summary.strip():
            continue
        article_dicts.append({
            "title": a.title,
            "summary": a.summary,
        })
        dict_to_article_idx.append(idx)

    # Batch into chunks of 10 for API calls (smaller batches avoid Groq 504 timeouts)
    BATCH_SIZE = 10
    all_classifications = []

    for i in range(0, len(article_dicts), BATCH_SIZE):
        batch = article_dicts[i:i + BATCH_SIZE]
        results = await classify_with_ai(batch)
        if results:
            # Map batch-relative index back to original articles list
            for r in results:
                dict_idx = i + r.get("index", 0)
                if 0 <= dict_idx < len(dict_to_article_idx):
                    r["_original_idx"] = dict_to_article_idx[dict_idx]
                else:
                    r["_original_idx"] = -1
            all_classifications.extend(results)

    if not all_classifications:
        return {"status": "ai_unavailable", "new_events": 0, "reclassified": 0}

    # Geocode unique AI-identified locations
    ai_locations: dict[str, tuple[float, float] | None] = {}
    for c in all_classifications:
        loc = c.get("location")
        if loc and not c.get("skip") and loc not in ai_locations:
            ai_locations[loc] = None

    for loc in ai_locations:
        coords = await geocode_location(loc)
        ai_locations[loc] = coords

    # Pre-fetch existing events for batch duplicate check
    classify_keys = []
    for c in all_classifications:
        if c.get("skip"):
            continue
        idx = c.get("_original_idx", -1)
        if 0 <= idx < len(articles):
            classify_keys.append((articles[idx].title, articles[idx].url))

    existing_events: dict[tuple[str, str], Event] = {}
    if classify_keys:
        BATCH = 200
        for i in range(0, len(classify_keys), BATCH):
            batch_keys = classify_keys[i:i + BATCH]
            result = await db.execute(
                select(Event).where(
                    tuple_(Event.title, Event.source_url).in_(batch_keys)
                )
            )
            for e in result.scalars().all():
                existing_events[(e.title, e.source_url)] = e

    # Store new events and reclassify existing ones
    new_events = 0
    reclassified = 0

    for c in all_classifications:
        if c.get("skip"):
            continue

        idx = c.get("_original_idx", -1)
        if idx < 0 or idx >= len(articles):
            continue

        article = articles[idx]
        event_type = c.get("event_type", "conflict")
        location_name = c.get("location")

        # Get coordinates
        lat, lon = None, None
        if location_name and location_name in ai_locations:
            coords = ai_locations[location_name]
            if coords:
                lat, lon = coords

        if lat is None or lon is None:
            continue

        existing = existing_events.get((article.title, article.url))

        if existing:
            # Reclassify existing event
            if existing.event_type != event_type or existing.location_name != location_name:
                existing.event_type = event_type
                existing.location_name = location_name
                existing.latitude = lat
                existing.longitude = lon
                existing.coordinates = f"SRID=4326;POINT({lon} {lat})"
                reclassified += 1
        else:
            # Create new event
            event = Event(
                event_type=event_type,
                title=article.title[:500],
                summary=(article.summary or "")[:2000],
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

    try:
        await db.commit()
    except Exception:
        await db.rollback()
        logger.exception("Failed to persist AI-classified events")
        return {"status": "error", "new_events": 0, "reclassified": 0}

    logger.info(
        "AI classification complete: %d new events, %d reclassified from %d articles",
        new_events, reclassified, len(articles)
    )
    return {
        "status": "ok",
        "new_events": new_events,
        "reclassified": reclassified,
        "total_articles": len(articles),
        "ai_classified": sum(1 for c in all_classifications if not c.get("skip")),
        "ai_skipped": sum(1 for c in all_classifications if c.get("skip")),
    }


@router.post("/ai-classify")
async def trigger_ai_classification(db: AsyncSession = Depends(get_db)):
    """On-demand AI classification of current news articles."""
    if _ai_classify_lock.locked():
        raise HTTPException(status_code=429, detail="AI classification already in progress")
    async with _ai_classify_lock:
        result = await run_ai_classification(db)
    return result


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
