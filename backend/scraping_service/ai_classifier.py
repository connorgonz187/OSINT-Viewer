"""
AI-powered event classification using Claude API.
Batches articles into a single API call for cost efficiency.
Falls back to regex if no API key is configured.
"""

import json
import logging

import anthropic

from config import settings

logger = logging.getLogger(__name__)

VALID_EVENT_TYPES = {
    "missile_strike", "airstrike", "explosion", "conflict",
    "troop_movement", "naval_incident", "shelling",
}

SYSTEM_PROMPT = """You are an OSINT (Open Source Intelligence) analyst. Your job is to classify news articles into conflict/military event categories and identify the most relevant geographic location.

For each article, determine:
1. Whether it describes a real conflict/military event (not opinion pieces, diplomacy-only, or unrelated news)
2. The event type (one of: missile_strike, airstrike, explosion, conflict, troop_movement, naval_incident, shelling)
3. The single most specific geographic location where the event occurred
4. A confidence score from 0.0 to 1.0

Event type definitions:
- missile_strike: Missile or rocket attacks, missile interceptions, ballistic/cruise missile launches
- airstrike: Air strikes, drone strikes, aerial bombing, fighter jet attacks
- explosion: Bombings, IEDs, car bombs, detonations, blasts
- conflict: Armed clashes, battles, ground assaults, military operations, sieges, invasions, casualties from fighting
- troop_movement: Military deployments, buildups, exercises, arms shipments, mobilizations
- naval_incident: Ship attacks, maritime incidents, blockades, naval confrontations, piracy
- shelling: Artillery fire, mortar attacks, bombardment, heavy weapons fire

Rules:
- Only classify articles about ACTUAL events, not predictions, opinions, or diplomatic meetings
- Location should be a specific place name (city, region, or country where the event happened)
- If the article is not about a conflict/military event, set skip=true
- Be precise with locations: prefer cities over countries when mentioned"""

USER_PROMPT_TEMPLATE = """Classify these news articles. Return a JSON array with one object per article.

Each object must have:
- "index": the article index number
- "skip": true if not a real conflict event, false if it is
- "event_type": one of [missile_strike, airstrike, explosion, conflict, troop_movement, naval_incident, shelling] (null if skip=true)
- "location": most specific location name (null if skip=true)
- "confidence": 0.0-1.0 (0 if skip=true)

Articles:
{articles}

Respond with ONLY the JSON array, no other text."""


async def classify_with_ai(articles: list[dict]) -> list[dict] | None:
    """
    Classify a batch of articles using Claude Haiku.

    Args:
        articles: List of dicts with 'title' and 'summary' keys.

    Returns:
        List of classification dicts, or None if API unavailable.
    """
    if not settings.ANTHROPIC_API_KEY:
        logger.warning("No ANTHROPIC_API_KEY set, AI classification unavailable")
        return None

    if not articles:
        return []

    # Format articles for the prompt
    article_text = ""
    for i, a in enumerate(articles):
        title = a.get("title", "").strip()
        summary = a.get("summary", "").strip()[:500]
        article_text += f"\n[{i}] Title: {title}\nSummary: {summary}\n"

    try:
        client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

        response = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=[{
                "role": "user",
                "content": USER_PROMPT_TEMPLATE.format(articles=article_text),
            }],
        )

        text = response.content[0].text.strip()

        # Extract JSON array from response
        if text.startswith("```"):
            text = text.split("\n", 1)[1]
            text = text.rsplit("```", 1)[0]

        results = json.loads(text)

        if not isinstance(results, list):
            logger.error("AI response is not a list: %s", type(results))
            return None

        # Validate and clean results
        cleaned = []
        for r in results:
            if not isinstance(r, dict):
                continue
            if r.get("skip", True):
                cleaned.append({"index": r.get("index", -1), "skip": True})
                continue

            event_type = r.get("event_type", "")
            if event_type not in VALID_EVENT_TYPES:
                event_type = "conflict"  # safe fallback

            cleaned.append({
                "index": r.get("index", -1),
                "skip": False,
                "event_type": event_type,
                "location": r.get("location"),
                "confidence": min(max(float(r.get("confidence", 0.5)), 0.0), 1.0),
            })

        logger.info(
            "AI classified %d articles: %d events, %d skipped",
            len(articles),
            sum(1 for c in cleaned if not c.get("skip")),
            sum(1 for c in cleaned if c.get("skip")),
        )
        return cleaned

    except json.JSONDecodeError as e:
        logger.error("Failed to parse AI response as JSON: %s", e)
        return None
    except anthropic.APIError as e:
        logger.error("Anthropic API error: %s", e)
        return None
    except Exception as e:
        logger.exception("Unexpected error in AI classification: %s", e)
        return None
