"""Flight service API routes."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db, FlightTrack
from .opensky import fetch_all_states
from .military_filter import is_military_aircraft

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/flights", tags=["flights"])

# In-memory cache for live military flights (refreshed by scheduler)
_cached_military_flights: list[dict] = []


def get_cached_flights() -> list[dict]:
    return _cached_military_flights


async def refresh_military_flights(db: AsyncSession):
    """Fetch live data, filter military, cache and persist."""
    global _cached_military_flights

    states = await fetch_all_states()
    military = []

    for f in states:
        if is_military_aircraft(f.icao24, f.callsign):
            entry = {
                "icao24": f.icao24,
                "callsign": f.callsign,
                "origin_country": f.origin_country,
                "latitude": f.latitude,
                "longitude": f.longitude,
                "altitude": f.altitude,
                "velocity": f.velocity,
                "heading": f.heading,
                "on_ground": f.on_ground,
                "last_contact": f.last_contact.isoformat(),
            }
            military.append(entry)

            # Persist to DB for historical tracking
            track = FlightTrack(
                icao24=f.icao24,
                callsign=f.callsign,
                latitude=f.latitude,
                longitude=f.longitude,
                altitude=f.altitude,
                velocity=f.velocity,
                heading=f.heading,
                on_ground=f.on_ground,
                coordinates=f"SRID=4326;POINT({f.longitude} {f.latitude})",
            )
            db.add(track)

    try:
        await db.commit()
    except Exception:
        await db.rollback()
        logger.exception("Failed to persist flight tracks")

    _cached_military_flights = military
    logger.info("Refreshed: %d military aircraft from %d total", len(military), len(states))


@router.get("/live")
async def get_live_military_flights():
    """Return currently cached live military flights."""
    return {"count": len(_cached_military_flights), "flights": _cached_military_flights}


@router.get("/history")
async def get_flight_history(
    icao24: Optional[str] = Query(None),
    hours: int = Query(24, ge=1, le=168),
    db: AsyncSession = Depends(get_db),
):
    """Get historical flight track data."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    q = select(FlightTrack).where(FlightTrack.seen_at >= cutoff)
    if icao24:
        q = q.where(FlightTrack.icao24 == icao24)
    q = q.order_by(FlightTrack.seen_at.desc()).limit(5000)

    result = await db.execute(q)
    tracks = result.scalars().all()

    return {
        "count": len(tracks),
        "tracks": [
            {
                "icao24": t.icao24,
                "callsign": t.callsign,
                "latitude": t.latitude,
                "longitude": t.longitude,
                "altitude": t.altitude,
                "velocity": t.velocity,
                "heading": t.heading,
                "seen_at": t.seen_at.isoformat() if t.seen_at else None,
            }
            for t in tracks
        ],
    }
