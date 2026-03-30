import re
from bs4 import BeautifulSoup

_NOISE_TAGS = {"script", "style", "nav", "footer", "aside", "iframe", "form"}
_AD_PATTERNS = re.compile(r"(ad|sponsor|promo|sidebar|comment)", re.IGNORECASE)
_URL_PATTERN = re.compile(r"^https?://")
_EN_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z])")
_ZH_SENTENCE_SPLIT = re.compile(r"(?<=[。！？])")


def clean_html(html: str | None) -> str:
    if not html:
        return ""
    soup = BeautifulSoup(html, "html.parser")

    # Remove noise tags
    for tag in soup.find_all(_NOISE_TAGS):
        tag.decompose()

    # Remove ad-related divs
    for tag in soup.find_all("div"):
        classes = " ".join(tag.get("class", []))
        tag_id = tag.get("id", "")
        if _AD_PATTERNS.search(classes) or _AD_PATTERNS.search(tag_id):
            tag.decompose()

    # Prefer <article> or <main> content
    article = soup.find("article") or soup.find("main")
    target = article if article else soup

    # Extract text preserving paragraph breaks
    paragraphs = []
    for p in target.find_all(["p", "h1", "h2", "h3", "h4", "li"]):
        text = p.get_text(strip=True)
        if text:
            paragraphs.append(text)

    if not paragraphs:
        return target.get_text(separator="\n", strip=True)

    return "\n".join(paragraphs)


def complete_data(data: dict) -> dict:
    result = {**data}

    # Title fallback
    title = (result.get("title") or "").strip()
    if not title or _URL_PATTERN.match(title) or len(title) < 5:
        content = result.get("content") or ""
        result["title"] = content[:80].strip()

    # published_at fallback
    if not result.get("published_at"):
        result["published_at"] = result.get("fetched_at")

    return result


def extract_summary(text: str | None) -> str:
    if not text:
        return ""

    lines = text.strip().split("\n")
    # Filter out short lines (bylines, dates, captions)
    lines = [line.strip() for line in lines if len(line.strip()) >= 20]
    if not lines:
        return text[:100].strip() if text else ""

    joined = " ".join(lines)

    # Try Chinese sentence splitting first (only if Chinese punctuation present)
    if re.search(r"[。！？]", joined):
        zh_sentences = _ZH_SENTENCE_SPLIT.split(joined)
        zh_sentences = [s.strip() for s in zh_sentences if len(s.strip()) >= 20]
        for s in zh_sentences:
            if 20 <= len(s) <= 200:
                return s

    # Try English sentence splitting
    en_sentences = _EN_SENTENCE_SPLIT.split(joined)
    en_sentences = [s.strip() for s in en_sentences if len(s.strip()) >= 20]
    if en_sentences:
        for s in en_sentences:
            if 20 <= len(s) <= 200:
                return s

    # Fallback: truncate to last punctuation within 150 chars
    excerpt = joined[:150]
    for punct in ["。", ".", "！", "!", "？", "?"]:
        idx = excerpt.rfind(punct)
        if idx > 20:
            return excerpt[: idx + 1]

    return joined[:100].strip()
