"""
RSS feed scraper for conflict/incident news sources.
Fetches articles, cleans HTML, and passes to NLP extraction.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import feedparser
import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Default OSINT-relevant RSS feeds
DEFAULT_FEEDS = [
    "https://feeds.bbci.co.uk/news/world/rss.xml",
    "https://www.aljazeera.com/xml/rss/all.xml",
    "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
    "https://feeds.washingtonpost.com/rss/world",
]


@dataclass
class Article:
    title: str
    summary: str
    url: str
    source: str
    published: datetime | None
    full_text: str | None = None


async def fetch_rss_feed(feed_url: str) -> list[Article]:
    """Fetch and parse a single RSS feed."""
    articles = []
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(feed_url, follow_redirects=True)
            resp.raise_for_status()
    except httpx.HTTPError as e:
        logger.warning("Failed to fetch RSS %s: %s", feed_url, e)
        return []

    feed = feedparser.parse(resp.text)
    source_name = feed.feed.get("title", feed_url)

    for entry in feed.entries[:30]:  # limit per feed
        pub_date = None
        if hasattr(entry, "published"):
            try:
                pub_date = parsedate_to_datetime(entry.published)
                if pub_date.tzinfo is None:
                    pub_date = pub_date.replace(tzinfo=timezone.utc)
            except (ValueError, TypeError):
                pass

        summary = ""
        if hasattr(entry, "summary"):
            summary = BeautifulSoup(entry.summary, "html.parser").get_text(
                separator=" ", strip=True
            )

        articles.append(
            Article(
                title=entry.get("title", ""),
                summary=summary,
                url=entry.get("link", ""),
                source=source_name,
                published=pub_date,
            )
        )

    logger.info("Fetched %d articles from %s", len(articles), source_name)
    return articles


async def fetch_all_feeds(
    feed_urls: list[str] | None = None,
) -> list[Article]:
    """Fetch articles from all configured feeds."""
    urls = feed_urls or DEFAULT_FEEDS
    all_articles = []
    for url in urls:
        articles = await fetch_rss_feed(url)
        all_articles.extend(articles)
    return all_articles


async def fetch_article_text(url: str) -> str | None:
    """Fetch full article text from URL (best-effort extraction)."""
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, follow_redirects=True)
            resp.raise_for_status()
    except httpx.HTTPError:
        return None

    soup = BeautifulSoup(resp.text, "html.parser")

    # Remove script/style tags
    for tag in soup(["script", "style", "nav", "header", "footer", "aside"]):
        tag.decompose()

    # Try article body first, fallback to paragraphs
    article = soup.find("article")
    if article:
        return article.get_text(separator=" ", strip=True)

    paragraphs = soup.find_all("p")
    text = " ".join(p.get_text(strip=True) for p in paragraphs)
    return text if len(text) > 100 else None
