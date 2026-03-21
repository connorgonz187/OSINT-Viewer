"""
AI-powered event classification using Groq (free) or Claude (paid) API.
Batches articles into API calls for cost efficiency.
Prefers Groq (free Llama 3.3 70B) over Anthropic (paid).
"""

import json
import logging

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


async def _classify_with_groq(article_text: str) -> list[dict] | None:
    """Classify using Groq (free tier - Llama 3.3 70B) with retry on rate limit."""
    import asyncio

    try:
        from groq import AsyncGroq

        client = AsyncGroq(
            api_key=settings.GROQ_API_KEY,
            timeout=60.0,
        )

        for attempt in range(3):
            try:
                response = await client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": USER_PROMPT_TEMPLATE.format(articles=article_text)},
                    ],
                    temperature=0.1,
                    max_tokens=2048,
                    response_format={"type": "json_object"},
                )
                text = response.choices[0].message.content.strip()
                return _parse_response(text)
            except Exception as e:
                error_str = str(e)
                if "429" in error_str or "rate" in error_str.lower():
                    wait = (attempt + 1) * 10
                    logger.warning("Groq rate limited, retrying in %ds (attempt %d/3)", wait, attempt + 1)
                    await asyncio.sleep(wait)
                    continue
                raise

    except Exception as e:
        logger.error("Groq API error: %s", e)
        return None


async def _classify_with_anthropic(article_text: str) -> list[dict] | None:
    """Classify using Claude (paid fallback)."""
    try:
        import anthropic

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
        return _parse_response(text)

    except Exception as e:
        logger.error("Anthropic API error: %s", e)
        return None


def _parse_response(text: str) -> list[dict] | None:
    """Parse JSON response from any LLM."""
    try:
        # Strip markdown code blocks if present
        if text.startswith("```"):
            text = text.split("\n", 1)[1]
            text = text.rsplit("```", 1)[0]

        parsed = json.loads(text)

        # Handle Groq json_object mode wrapping in an object
        if isinstance(parsed, dict):
            # Look for an array inside the object
            for key in ("results", "articles", "classifications", "data"):
                if key in parsed and isinstance(parsed[key], list):
                    parsed = parsed[key]
                    break
            else:
                # If it's a single classification wrapped in an object
                if "index" in parsed:
                    parsed = [parsed]
                else:
                    logger.error("AI response is a dict with no array: %s", list(parsed.keys()))
                    return None

        if not isinstance(parsed, list):
            logger.error("AI response is not a list: %s", type(parsed))
            return None

        return parsed

    except json.JSONDecodeError as e:
        logger.error("Failed to parse AI response as JSON: %s", e)
        return None


async def classify_with_ai(articles: list[dict]) -> list[dict] | None:
    """
    Classify a batch of articles using the best available AI provider.
    Priority: Groq (free) > Anthropic (paid) > None.

    Args:
        articles: List of dicts with 'title' and 'summary' keys.

    Returns:
        List of classification dicts, or None if no AI available.
    """
    if not articles:
        return []

    # Format articles for the prompt
    article_text = ""
    for i, a in enumerate(articles):
        title = a.get("title", "").strip()
        summary = a.get("summary", "").strip()[:300]
        article_text += f"\n[{i}] Title: {title}\nSummary: {summary}\n"

    # Try Groq first (free), then Anthropic (paid)
    raw_results = None
    provider = None

    if settings.GROQ_API_KEY:
        logger.info("Using Groq (free) for AI classification")
        raw_results = await _classify_with_groq(article_text)
        provider = "groq"

    if raw_results is None and settings.ANTHROPIC_API_KEY:
        logger.info("Using Anthropic (paid) for AI classification")
        raw_results = await _classify_with_anthropic(article_text)
        provider = "anthropic"

    if raw_results is None:
        logger.warning("No AI provider available for classification")
        return None

    # Validate and clean results
    cleaned = []
    for r in raw_results:
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
        "AI classified %d articles via %s: %d events, %d skipped",
        len(articles),
        provider,
        sum(1 for c in cleaned if not c.get("skip")),
        sum(1 for c in cleaned if c.get("skip")),
    )
    return cleaned
