import re

_TRUST_BASE = {"high": 80, "medium": 50, "low": 20}
_AD_URL_PATTERNS = re.compile(r"/(ad|sponsor|redirect|campaign)/", re.IGNORECASE)
_SPAM_TITLE_PATTERNS = re.compile(r"(广告|赞助|sponsored|^AD\b)", re.IGNORECASE)


def calculate_quality_score(
    title: str, content: str | None, url: str, trust_level: str,
) -> int:
    content = content or ""
    content_len = len(content)
    title_len = len(title) if title else 0

    # Signal 1: source trust
    score = _TRUST_BASE.get(trust_level, 20)

    # Signal 2: content completeness
    if content_len > 500:
        score += 15
    elif content_len >= 100:
        score += 5
    else:
        score -= 20

    if 10 <= title_len <= 100:
        score += 5
    elif title_len < 10 or title_len > 200:
        score -= 10

    # Signal 3: URL/content spam signals
    if _AD_URL_PATTERNS.search(url):
        score -= 30

    if title and _SPAM_TITLE_PATTERNS.search(title):
        score -= 30

    return max(0, min(100, score))
