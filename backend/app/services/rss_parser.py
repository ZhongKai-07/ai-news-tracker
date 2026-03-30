from datetime import datetime, timezone
from time import mktime
import aiohttp
import feedparser
from bs4 import BeautifulSoup

def parse_feed_entry(entry):
    title = entry.get("title", "")
    url = entry.get("link", "")
    content = None
    if "content" in entry and entry["content"]:
        raw_html = entry["content"][0].get("value", "")
        content = BeautifulSoup(raw_html, "html.parser").get_text(strip=True)
    elif "summary" in entry:
        content = BeautifulSoup(entry["summary"], "html.parser").get_text(strip=True)
    published_at = None
    if "published_parsed" in entry and entry["published_parsed"]:
        try:
            published_at = datetime.fromtimestamp(mktime(entry["published_parsed"]), tz=timezone.utc)
        except (ValueError, OverflowError):
            pass
    return {"title": title, "url": url, "content": content if content else None, "published_at": published_at}

async def parse_rss_feed(feed_url, proxy_url=None, custom_headers=None):
    headers = {"User-Agent": "AI-News-Tracker/1.0"}
    if custom_headers:
        headers.update(custom_headers)
    async with aiohttp.ClientSession() as session:
        async with session.get(feed_url, headers=headers, proxy=proxy_url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
            text = await resp.text()
    feed = feedparser.parse(text)
    return [parse_feed_entry(e) for e in feed.entries]
