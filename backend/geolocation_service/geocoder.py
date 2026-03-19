"""
Geocoding service using Nominatim (OpenStreetMap).
Converts place names to lat/lon coordinates.
"""

import logging
from functools import lru_cache

from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError

from config import settings

logger = logging.getLogger(__name__)

_geocoder = Nominatim(user_agent=settings.NOMINATIM_USER_AGENT, timeout=10)

# Cache to avoid repeated lookups for same location
_cache: dict[str, tuple[float, float] | None] = {}


async def geocode_location(place_name: str) -> tuple[float, float] | None:
    """
    Convert a place name to (latitude, longitude).
    Returns None if geocoding fails.
    Uses in-memory cache to respect Nominatim rate limits.
    """
    if not place_name or len(place_name.strip()) < 2:
        return None

    normalized = place_name.strip().lower()
    if normalized in _cache:
        return _cache[normalized]

    try:
        location = _geocoder.geocode(place_name, language="en")
        if location:
            coords = (location.latitude, location.longitude)
            _cache[normalized] = coords
            logger.debug("Geocoded '%s' -> %s", place_name, coords)
            return coords
        else:
            _cache[normalized] = None
            logger.debug("Could not geocode '%s'", place_name)
            return None
    except (GeocoderTimedOut, GeocoderServiceError) as e:
        logger.warning("Geocoding error for '%s': %s", place_name, e)
        return None
