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

# Event type classification keywords
EVENT_PATTERNS: dict[str, list[str]] = {
    "missile_strike": [
        r"missile\s+strike",
        r"missile\s+attack",
        r"ballistic\s+missile",
        r"cruise\s+missile",
        r"rocket\s+attack",
        r"rocket\s+strike",
    ],
    "airstrike": [
        r"air\s*strike",
        r"aerial\s+bombing",
        r"air\s+raid",
        r"bombing\s+raid",
        r"drone\s+strike",
        r"UAV\s+strike",
    ],
    "explosion": [
        r"explosion",
        r"blast",
        r"detonation",
        r"bomb\s+blast",
        r"car\s+bomb",
        r"IED",
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
    ],
    "troop_movement": [
        r"troop\s+movement",
        r"troop\s+deploy",
        r"military\s+buildup",
        r"military\s+convoy",
        r"reinforcement",
        r"mobilization",
    ],
    "naval_incident": [
        r"naval\s+incident",
        r"ship\s+attack",
        r"maritime\s+attack",
        r"vessel\s+seized",
        r"blockade",
    ],
    "shelling": [
        r"shelling",
        r"artillery\s+strike",
        r"artillery\s+fire",
        r"mortar\s+attack",
        r"bombardment",
    ],
}

# Pre-compile patterns
_compiled_patterns: dict[str, list[re.Pattern]] = {
    event_type: [re.compile(p, re.IGNORECASE) for p in patterns]
    for event_type, patterns in EVENT_PATTERNS.items()
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
            if name.lower() not in seen and len(name) > 1:
                seen.add(name.lower())
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
