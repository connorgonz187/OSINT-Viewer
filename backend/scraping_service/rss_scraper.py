"""
RSS feed scraper for conflict/incident news sources.
Fetches articles, cleans HTML, and passes to NLP extraction.
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import feedparser
import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Expanded OSINT-relevant RSS feeds
DEFAULT_FEEDS = [
    # Major international news
    "https://feeds.bbci.co.uk/news/world/rss.xml",
    "https://www.aljazeera.com/xml/rss/all.xml",
    "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
    "https://feeds.washingtonpost.com/rss/world",
    # Defense / military focused
    "https://www.defense.gov/DesktopModules/ArticleCS/RSS.ashx?ContentType=1&Site=945",
    "https://news.un.org/feed/subscribe/en/news/region/middle-east/feed/rss.xml",
    "https://news.un.org/feed/subscribe/en/news/region/africa/feed/rss.xml",
    "https://news.un.org/feed/subscribe/en/news/region/europe/feed/rss.xml",
    "https://news.un.org/feed/subscribe/en/news/region/asia-pacific/feed/rss.xml",
    # Conflict / regional
    "https://www.france24.com/en/rss",
    "https://feeds.skynews.com/feeds/rss/world.xml",
    "https://www.theguardian.com/world/rss",
    "https://rss.app/feeds/v1.1/dWc8IiHF4osSjX60.xml",  # Reuters world
    "https://www.middleeasteye.net/rss",
    "https://english.alarabiya.net/tools/rss",
    "https://www.jpost.com/rss/rssfeedsfrontpage.aspx",
    "https://www.timesofisrael.com/feed/",
    # Asia / Pacific
    "https://www.scmp.com/rss/91/feed",
    "https://www3.nhk.or.jp/nhkworld/en/news/feeds/",
]


@dataclass
class Article:
    title: str
    summary: str
    url: str
    source: str
    published: datetime | None
    full_text: str | None = None


async def fetch_rss_feed(
    feed_url: str, client: httpx.AsyncClient | None = None,
) -> list[Article]:
    """Fetch and parse a single RSS feed."""
    articles = []
    try:
        _client = client or httpx.AsyncClient(timeout=20.0)
        try:
            resp = await _client.get(
                feed_url,
                follow_redirects=True,
                headers={"User-Agent": "OSINT-Viewer/1.0 (news aggregator)"},
            )
            resp.raise_for_status()
        finally:
            if client is None:
                await _client.aclose()
    except httpx.HTTPError as e:
        logger.warning("Failed to fetch RSS %s: %s", feed_url, e)
        return []

    feed = feedparser.parse(resp.text)
    source_name = feed.feed.get("title", feed_url)

    for entry in feed.entries[:50]:  # increased per-feed limit
        pub_date = None
        if hasattr(entry, "published"):
            try:
                pub_date = parsedate_to_datetime(entry.published)
                if pub_date.tzinfo is None:
                    pub_date = pub_date.replace(tzinfo=timezone.utc)
            except (ValueError, TypeError):
                pass
        elif hasattr(entry, "updated"):
            try:
                pub_date = parsedate_to_datetime(entry.updated)
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
    """Fetch articles from all configured feeds concurrently using a shared client."""
    urls = feed_urls or DEFAULT_FEEDS
    async with httpx.AsyncClient(timeout=20.0) as client:
        tasks = [fetch_rss_feed(url, client=client) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    all_articles = []
    for result in results:
        if isinstance(result, list):
            all_articles.extend(result)
        elif isinstance(result, Exception):
            logger.warning("Feed fetch failed: %s", result)

    logger.info("Total articles fetched: %d from %d feeds", len(all_articles), len(urls))
    return all_articles


async def fetch_article_text(url: str) -> str | None:
    """Fetch full article text from URL (best-effort extraction)."""
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                url,
                follow_redirects=True,
                headers={"User-Agent": "OSINT-Viewer/1.0 (news aggregator)"},
            )
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
