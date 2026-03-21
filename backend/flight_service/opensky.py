"""
OpenSky Network API client for fetching live ADS-B flight data.
Docs: https://openskynetwork.github.io/opensky-api/rest.html
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx

from config import settings

logger = logging.getLogger(__name__)

OPENSKY_API = "https://opensky-network.org/api"


@dataclass
class FlightState:
    icao24: str
    callsign: str | None
    origin_country: str
    longitude: float | None
    latitude: float | None
    altitude: float | None  # barometric altitude in meters
    velocity: float | None  # ground speed m/s
    heading: float | None   # true track in degrees
    on_ground: bool
    last_contact: datetime


async def fetch_all_states(
    bbox: tuple[float, float, float, float] | None = None,
) -> list[FlightState]:
    """
    Fetch current aircraft states from OpenSky.
    bbox: (lamin, lomin, lamax, lomax) optional bounding box filter.
    """
    params: dict = {}
    if bbox:
        params["lamin"] = bbox[0]
        params["lomin"] = bbox[1]
        params["lamax"] = bbox[2]
        params["lomax"] = bbox[3]

    auth = None
    if settings.OPENSKY_USERNAME and settings.OPENSKY_PASSWORD:
        auth = (settings.OPENSKY_USERNAME, settings.OPENSKY_PASSWORD)

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.get(
                f"{OPENSKY_API}/states/all",
                params=params,
                auth=auth,
            )
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPStatusError as e:
            logger.error("OpenSky API error: %s", e.response.status_code)
            return []
        except httpx.RequestError as e:
            logger.error("OpenSky request failed: %s", e)
            return []
        except ValueError:
            logger.error("OpenSky returned invalid JSON")
            return []

    states = data.get("states") or []

    flights = []
    for s in states:
        if s[5] is None or s[6] is None:
            continue  # skip aircraft with no position
        flights.append(
            FlightState(
                icao24=s[0],
                callsign=(s[1] or "").strip() or None,
                origin_country=s[2],
                longitude=s[5],
                latitude=s[6],
                altitude=s[7],       # baro_altitude
                velocity=s[9],
                heading=s[10],
                on_ground=s[8],
                last_contact=datetime.fromtimestamp(s[4], tz=timezone.utc),
            )
        )
    logger.info("Fetched %d aircraft states from OpenSky", len(flights))
    return flights
