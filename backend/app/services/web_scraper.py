from urllib.parse import urljoin
import aiohttp
from bs4 import BeautifulSoup

def extract_articles_from_html(html, config):
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    items = soup.select(config.get("item_selector", ""))
    if not items:
        return []
    base_url = config.get("base_url", "")
    articles = []
    for item in items:
        title_el = item.select_one(config.get("title_selector", "")) if config.get("title_selector") else None
        url_el = item.select_one(config.get("url_selector", "")) if config.get("url_selector") else None
        content_el = item.select_one(config.get("content_selector", "")) if config.get("content_selector") else None
        title = title_el.get_text(strip=True) if title_el else ""
        if not title:
            continue
        raw_url = ""
        if url_el:
            attr = config.get("url_attribute", "href")
            raw_url = url_el.get(attr, "")
        url = raw_url if raw_url.startswith("http") else urljoin(base_url, raw_url)
        content = content_el.get_text(strip=True) if content_el else None
        articles.append({"title": title, "url": url, "content": content, "published_at": None})
    return articles

async def scrape_web_page(page_url, config, proxy_url=None, custom_headers=None):
    headers = {"User-Agent": "AI-News-Tracker/1.0"}
    if custom_headers:
        headers.update(custom_headers)
    async with aiohttp.ClientSession() as session:
        async with session.get(page_url, headers=headers, proxy=proxy_url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
            html = await resp.text()
    config["base_url"] = config.get("base_url", page_url.rsplit("/", 1)[0])
    return extract_articles_from_html(html, config)
