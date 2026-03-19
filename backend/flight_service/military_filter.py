"""
Military aircraft detection using ICAO hex ranges, callsign patterns,
and known military type designators.
"""

import re

# ICAO 24-bit address ranges allocated to military
# Source: https://www.icao.int/publications/doc8643
MILITARY_ICAO_RANGES = [
    # US Military
    ("ADF7C0", "AFF FFF"),  # US DoD
    # UK Military
    ("43C000", "43CFFF"),
    # France Military
    ("3E0000", "3EFFFF"),
    # Germany Military
    ("3F0000", "3FFFFF"),
    # Russia Military
    ("140000", "15FFFF"),
    # China Military
    ("780000", "78FFFF"),
    # NATO
    ("450000", "45FFFF"),
]

# Compiled ICAO ranges as integer tuples for fast lookup
_ICAO_RANGES_INT = []
for start, end in MILITARY_ICAO_RANGES:
    _ICAO_RANGES_INT.append(
        (int(start.replace(" ", ""), 16), int(end.replace(" ", ""), 16))
    )

# Callsign prefixes associated with military operations
MILITARY_CALLSIGN_PREFIXES = [
    "RCH",      # US Air Mobility Command (Reach)
    "USAF",     # US Air Force
    "NAVY",     # US Navy
    "ARMY",     # US Army
    "DUKE",     # US Air Force
    "EVAC",     # Aeromedical evacuation
    "JAKE",     # US Marine Corps
    "TOPCAT",   # US special operations
    "IRON",     # US military
    "BOLT",     # US military
    "DOOM",     # US military
    "KNIFE",    # US special ops
    "KING",     # US CSAR
    "JOLLY",    # US CSAR
    "PEDRO",    # US CSAR
    "TORCH",    # US military
    "VIPER",    # US military
    "COBRA",    # US military
    "HAWK",     # Various military
    "EAGLE",    # Various military
    "WOLF",     # Various military
    "BAF",      # Belgian Air Force
    "GAF",      # German Air Force
    "IAF",      # Israeli Air Force
    "RAF",      # Royal Air Force
    "RRR",      # Royal Air Force
    "SHF",      # Swedish Air Force
    "FAF",      # French Air Force
    "CTM",      # French Air Force (Cotam)
    "IAM",      # Italian Air Force
    "MMF",      # Turkish Air Force
    "PLF",      # Polish Air Force
    "CNV",      # US Navy (Convoy)
    "PAT",      # NATO patrol
    "NATO",     # NATO
    "FORTE",    # US RQ-4 Global Hawk
    "HOMER",    # US military
    "LAGR",     # US military refueling
]

# Known military aircraft type codes (ICAO Doc 8643)
MILITARY_AIRCRAFT_TYPES = {
    "C17",   # C-17 Globemaster
    "C130",  # C-130 Hercules
    "C5",    # C-5 Galaxy
    "KC10",  # KC-10 Extender
    "KC46",  # KC-46 Pegasus
    "KC135", # KC-135 Stratotanker
    "B52",   # B-52 Stratofortress
    "B1",    # B-1 Lancer
    "B2",    # B-2 Spirit
    "F15",   # F-15 Eagle
    "F16",   # F-16 Fighting Falcon
    "F18",   # F/A-18
    "F22",   # F-22 Raptor
    "F35",   # F-35 Lightning II
    "A10",   # A-10 Thunderbolt
    "E3",    # E-3 Sentry (AWACS)
    "E8",    # E-8 JSTARS
    "P8",    # P-8 Poseidon
    "RC135", # RC-135 Rivet Joint
    "U2",    # U-2 Dragon Lady
    "RQ4",   # RQ-4 Global Hawk
    "MQ9",   # MQ-9 Reaper
    "V22",   # V-22 Osprey
    "H60",   # UH-60 Black Hawk
    "H47",   # CH-47 Chinook
    "E6",    # E-6 Mercury
    "C2",    # C-2 Greyhound
    "C40",   # C-40 Clipper
    "EUFI",  # Eurofighter Typhoon
    "RFAL",  # Rafale
    "TORNA", # Tornado
    "A400",  # A400M Atlas
    "HAWK",  # BAE Hawk
    "K35R",  # KC-135
    "C30J",  # C-130J
    "GLF5",  # Gulfstream V (mil variants)
}

_callsign_pattern = re.compile(
    r"^(" + "|".join(re.escape(p) for p in MILITARY_CALLSIGN_PREFIXES) + r")",
    re.IGNORECASE,
)


def is_military_icao(icao24: str) -> bool:
    """Check if ICAO24 hex address falls in a military range."""
    try:
        addr = int(icao24.strip(), 16)
    except (ValueError, AttributeError):
        return False
    return any(start <= addr <= end for start, end in _ICAO_RANGES_INT)


def is_military_callsign(callsign: str | None) -> bool:
    """Check if callsign matches known military patterns."""
    if not callsign:
        return False
    cs = callsign.strip().upper()
    return bool(_callsign_pattern.match(cs))


def is_military_type(type_code: str | None) -> bool:
    """Check if aircraft type code is a known military type."""
    if not type_code:
        return False
    return type_code.strip().upper() in MILITARY_AIRCRAFT_TYPES


def is_military_aircraft(
    icao24: str,
    callsign: str | None = None,
    type_code: str | None = None,
) -> bool:
    """
    Determine if an aircraft is likely military based on any available signal.
    Returns True if ANY indicator matches.
    """
    return (
        is_military_icao(icao24)
        or is_military_callsign(callsign)
        or is_military_type(type_code)
    )
