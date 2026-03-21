"""
Geocoding service using Nominatim (OpenStreetMap).
Converts place names to lat/lon coordinates.
Biased toward international conflict regions to avoid US small-town false matches.
"""

import asyncio
import logging
import time
from collections import OrderedDict

from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError

from config import settings

logger = logging.getLogger(__name__)

_geocoder = Nominatim(user_agent=settings.NOMINATIM_USER_AGENT, timeout=10)

# LRU-style cache with max size to prevent unbounded memory growth
_MAX_CACHE_SIZE = 5000
_cache: OrderedDict[str, tuple[float, float] | None] = OrderedDict()
_last_request_time: float = 0.0


def _cache_put(key: str, value: tuple[float, float] | None):
    """Add to cache with size eviction."""
    _cache[key] = value
    if len(_cache) > _MAX_CACHE_SIZE:
        _cache.popitem(last=False)


# Known locations that Nominatim gets wrong (US small towns vs actual countries/regions)
_KNOWN_OVERRIDES: dict[str, tuple[float, float]] = {
    "palestine": (31.9, 35.2),
    "palestinian territories": (31.9, 35.2),
    "gaza": (31.5, 34.47),
    "gaza strip": (31.5, 34.47),
    "west bank": (31.95, 35.3),
    "crimea": (45.3, 34.4),
    "donbas": (48.0, 37.8),
    "donetsk": (48.0, 37.8),
    "luhansk": (48.57, 39.33),
    "taiwan": (23.7, 120.96),
    "kashmir": (34.08, 74.8),
    "kurdistan": (36.4, 44.4),
    "south ossetia": (42.34, 43.97),
    "abkhazia": (43.0, 41.0),
    "transnistria": (46.84, 29.63),
    "nagorno-karabakh": (39.82, 46.77),
    "somaliland": (9.56, 44.06),
    "yemen": (15.55, 48.52),
    "syria": (35.0, 38.0),
    "libya": (26.34, 17.23),
    "sudan": (15.5, 32.56),
    "myanmar": (19.76, 96.07),
    "lebanon": (33.85, 35.86),
    "iran": (32.43, 53.69),
    "iraq": (33.22, 43.68),
    "afghanistan": (33.94, 67.71),
    "ukraine": (48.38, 31.17),
    "russia": (61.52, 105.32),
    "israel": (31.05, 34.85),
    "north korea": (40.34, 127.51),
    "somalia": (5.15, 46.2),
    "ethiopia": (9.15, 40.49),
    "sahel": (14.5, 2.1),
    "mali": (17.57, -4.0),
    "burkina faso": (12.36, -1.52),
    "niger": (17.61, 8.08),
    "chad": (15.45, 18.73),
    "congo": (-4.04, 21.76),
    "mosul": (36.34, 43.14),
    "aleppo": (36.2, 37.16),
    "idlib": (35.93, 36.63),
    "kharkiv": (49.99, 36.23),
    "kherson": (46.64, 32.62),
    "zaporizhzhia": (47.84, 35.14),
    "mariupol": (47.1, 37.55),
    "bakhmut": (48.6, 38.0),
    "rafah": (31.3, 34.25),
    "khan younis": (31.35, 34.3),
    "jenin": (32.46, 35.3),
    "nablus": (32.22, 35.25),
    "ramallah": (31.9, 35.21),
    "tripoli": (32.9, 13.18),
    "benghazi": (32.12, 20.09),
    "khartoum": (15.5, 32.56),
    "aden": (12.8, 45.03),
    "sanaa": (15.37, 44.19),
    "hodeida": (14.8, 42.95),
    "mogadishu": (2.05, 45.32),
}

# Reject results that land in the US for ambiguous geopolitical terms
_CONFLICT_TERMS = {
    "palestine", "gaza", "tripoli", "lebanon", "syria", "jordan",
    "moscow", "georgia", "cuba", "panama", "peru", "colombia",
    "troy", "carthage", "alexandria", "memphis", "cairo",
}


def _sync_geocode(place_name: str) -> tuple:
    """Synchronous geocode call (runs in thread executor)."""
    return _geocoder.geocode(
        place_name,
        language="en",
        exactly_one=True,
        addressdetails=True,
    )


async def geocode_location(place_name: str) -> tuple[float, float] | None:
    """
    Convert a place name to (latitude, longitude).
    Returns None if geocoding fails.
    Uses in-memory cache and conflict-region overrides.
    """
    if not place_name or len(place_name.strip()) < 2:
        return None

    normalized = place_name.strip().lower()
    if normalized in _cache:
        return _cache[normalized]

    # Check known overrides first
    if normalized in _KNOWN_OVERRIDES:
        coords = _KNOWN_OVERRIDES[normalized]
        _cache_put(normalized, coords)
        logger.debug("Override geocoded '%s' -> %s", place_name, coords)
        return coords

    try:
        # Rate limit: Nominatim requires max 1 request per second
        # Only sleep the remaining delta since last request
        global _last_request_time
        elapsed = time.monotonic() - _last_request_time
        if elapsed < 1.1:
            await asyncio.sleep(1.1 - elapsed)
        _last_request_time = time.monotonic()

        # Run synchronous geopy call in thread executor
        location = await asyncio.get_running_loop().run_in_executor(
            None, lambda: _sync_geocode(place_name)
        )
        if location:
            coords = (location.latitude, location.longitude)

            # If this is a known conflict term and it resolved to the US, reject it
            if normalized in _CONFLICT_TERMS:
                raw = location.raw or {}
                address = raw.get("address", {})
                country_code = address.get("country_code", "")
                if country_code == "us":
                    logger.info(
                        "Rejected US geocode for conflict term '%s' (%s)",
                        place_name, coords
                    )
                    _cache_put(normalized, None)
                    return None

            _cache_put(normalized, coords)
            logger.debug("Geocoded '%s' -> %s", place_name, coords)
            return coords
        else:
            _cache_put(normalized, None)
            logger.debug("Could not geocode '%s'", place_name)
            return None
    except (GeocoderTimedOut, GeocoderServiceError) as e:
        logger.warning("Geocoding error for '%s': %s", place_name, e)
        return None
