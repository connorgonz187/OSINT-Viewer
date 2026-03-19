"""
NLP extraction pipeline for conflict event detection.
Uses spaCy NER for location extraction and keyword matching for event classification.
"""

import logging
import re
from dataclasses import dataclass

import spacy

logger = logging.getLogger(__name__)

# Load spaCy model (downloaded in Docker build)
try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    logger.warning("spaCy model not found, NER will be unavailable")
    nlp = None

# Expanded event type classification keywords
EVENT_PATTERNS: dict[str, list[str]] = {
    "missile_strike": [
        r"missile\s+strike",
        r"missile\s+attack",
        r"ballistic\s+missile",
        r"cruise\s+missile",
        r"rocket\s+attack",
        r"rocket\s+strike",
        r"rocket\s+fire",
        r"rockets?\s+launched",
        r"intercept\w*\s+missile",
        r"iron\s+dome",
        r"missile\s+defense",
        r"missile\s+launch",
        r"ICBM",
        r"hypersonic",
    ],
    "airstrike": [
        r"air\s*strike",
        r"aerial\s+bombing",
        r"air\s+raid",
        r"bombing\s+raid",
        r"drone\s+strike",
        r"UAV\s+strike",
        r"drone\s+attack",
        r"warplane",
        r"fighter\s+jet",
        r"sorties",
        r"bombing\s+campaign",
        r"air\s+campaign",
        r"targeted\s+killing",
        r"precision\s+strike",
    ],
    "explosion": [
        r"explosion",
        r"blast",
        r"detonation",
        r"bomb\s+blast",
        r"car\s+bomb",
        r"IED",
        r"suicide\s+bomb",
        r"truck\s+bomb",
        r"improvised\s+explosive",
        r"booby\s+trap",
        r"mine\s+explo",
        r"landmine",
        r"unexploded\s+ordnance",
    ],
    "conflict": [
        r"armed\s+conflict",
        r"clashes?\b",
        r"firefight",
        r"battle\b",
        r"combat\b",
        r"offensive\b",
        r"ground\s+assault",
        r"military\s+operation",
        r"incursion",
        r"invaded?",
        r"invasion",
        r"counter.?offensive",
        r"frontline",
        r"front\s+line",
        r"war\s+zone",
        r"ceasefire\b",
        r"truce\b",
        r"peace\s+deal",
        r"peace\s+talks?",
        r"hostilities",
        r"escalat\w+",
        r"retaliat\w+",
        r"siege\b",
        r"besieg\w+",
        r"insurgent",
        r"insurgency",
        r"guerrilla",
        r"militia\b",
        r"rebel\b",
        r"uprising",
        r"coup\b",
        r"military\s+junta",
        r"martial\s+law",
        r"civil\s+war",
        r"ethnic\s+cleansing",
        r"genocide\b",
        r"war\s+crime",
        r"atrocit",
        r"massacre",
        r"killed\s+in\s+\w+\s+attack",
        r"casualties",
        r"death\s+toll",
        r"civilian\s+deaths?",
        r"soldiers?\s+killed",
        r"troops?\s+killed",
        r"military\s+strikes?",
    ],
    "troop_movement": [
        r"troop\s+movement",
        r"troop\s+deploy",
        r"military\s+buildup",
        r"military\s+convoy",
        r"reinforcement",
        r"mobilization",
        r"troops?\s+amass",
        r"military\s+exercise",
        r"war\s+games",
        r"naval\s+exercise",
        r"military\s+drills?",
        r"deployed\s+troops",
        r"sending\s+troops",
        r"boots\s+on\s+the\s+ground",
        r"military\s+aid",
        r"arms\s+shipment",
        r"weapons?\s+deliver",
    ],
    "naval_incident": [
        r"naval\s+incident",
        r"ship\s+attack",
        r"maritime\s+attack",
        r"vessel\s+seized",
        r"blockade",
        r"naval\s+blockade",
        r"shipping\s+attack",
        r"tanker\s+attack",
        r"cargo\s+ship\s+\w*\s*attack",
        r"houthi\s+\w*\s*ship",
        r"red\s+sea\s+attack",
        r"strait\s+of\s+hormuz",
        r"piracy",
        r"pirates?",
        r"naval\s+confrontation",
        r"warship",
        r"destroyer",
        r"aircraft\s+carrier",
        r"submarine",
    ],
    "shelling": [
        r"shelling",
        r"artillery\s+strike",
        r"artillery\s+fire",
        r"mortar\s+attack",
        r"bombardment",
        r"artillery\s+barrage",
        r"mortar\s+fire",
        r"tank\s+fire",
        r"heavy\s+weapons?",
        r"indiscriminate\s+fire",
        r"cross.?border\s+shelling",
        r"HIMARS",
        r"MLRS",
        r"grad\s+rocket",
    ],
}

# Pre-compile patterns
_compiled_patterns: dict[str, list[re.Pattern]] = {
    event_type: [re.compile(p, re.IGNORECASE) for p in patterns]
    for event_type, patterns in EVENT_PATTERNS.items()
}

# Locations that are NOT real places (common NER false positives)
_LOCATION_BLACKLIST = {
    "the", "us", "eu", "un", "nato", "who", "bbc", "cnn", "reuters",
    "associated press", "ap", "afp", "nyt", "hamas", "hezbollah",
    "isis", "isil", "al-qaeda", "al qaeda", "taliban",
    "pentagon", "white house", "kremlin", "downing street",
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
    "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december",
}


@dataclass
class ExtractedEvent:
    event_type: str
    title: str
    summary: str
    locations: list[str]
    confidence: float  # 0.0-1.0


def classify_event(text: str) -> tuple[str, float] | None:
    """Classify text into event type with confidence."""
    if not text:
        return None

    best_type = None
    best_score = 0.0

    for event_type, patterns in _compiled_patterns.items():
        matches = sum(1 for p in patterns if p.search(text))
        if matches > 0:
            score = min(matches / 2.0, 1.0)  # normalize
            if score > best_score:
                best_score = score
                best_type = event_type

    if best_type:
        return (best_type, best_score)
    return None


def extract_locations(text: str) -> list[str]:
    """Extract location names from text using spaCy NER."""
    if not nlp or not text:
        return []

    doc = nlp(text[:10000])  # limit text length for performance
    locations = []
    seen = set()

    for ent in doc.ents:
        if ent.label_ in ("GPE", "LOC", "FAC"):
            name = ent.text.strip()
            lower = name.lower()
            if (
                lower not in seen
                and len(name) > 1
                and lower not in _LOCATION_BLACKLIST
            ):
                seen.add(lower)
                locations.append(name)

    return locations


def extract_event(title: str, text: str) -> ExtractedEvent | None:
    """
    Full extraction pipeline: classify event type and extract locations.
    Returns None if text is not conflict-related.
    """
    combined = f"{title} {text}"
    classification = classify_event(combined)

    if not classification:
        return None

    event_type, confidence = classification

    # Only proceed if we have minimum confidence
    if confidence < 0.3:
        return None

    locations = extract_locations(combined)

    # Build summary from first 300 chars of text
    summary = text[:300].strip()
    if len(text) > 300:
        summary += "..."

    return ExtractedEvent(
        event_type=event_type,
        title=title,
        summary=summary,
        locations=locations,
        confidence=confidence,
    )
