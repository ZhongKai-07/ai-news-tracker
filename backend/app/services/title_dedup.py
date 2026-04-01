import re

_TRUST_RANK = {"high": 3, "medium": 2, "low": 1}


def _tokenize(title: str) -> set[str]:
    """Tokenize title for Jaccard comparison. Chinese uses bigrams, English uses words."""
    chinese_chars = re.findall(r"[\u4e00-\u9fff]", title)
    if len(chinese_chars) > len(title) * 0.3:
        # Chinese: character bigrams
        return {title[i: i + 2] for i in range(len(title) - 1) if not title[i].isspace()}
    else:
        # English: lowercase word tokens
        return set(title.lower().split())


def jaccard_similarity(title_a: str, title_b: str) -> float:
    """Calculate Jaccard similarity between two titles."""
    tokens_a = _tokenize(title_a)
    tokens_b = _tokenize(title_b)
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b
    return len(intersection) / len(union)


def find_duplicates(articles: list[dict], threshold: float = 0.9) -> set[int]:
    """Find duplicate article IDs to filter out.

    Returns set of article IDs that should be marked as filtered.
    Keeps the article with highest trust_level in each duplicate group.
    """
    to_filter = set()
    n = len(articles)

    for i in range(n):
        if articles[i]["id"] in to_filter:
            continue
        for j in range(i + 1, n):
            if articles[j]["id"] in to_filter:
                continue

            # Length pre-filter: skip if length difference > 50%
            len_i = len(articles[i]["title"])
            len_j = len(articles[j]["title"])
            if max(len_i, len_j) > 0 and min(len_i, len_j) / max(len_i, len_j) < 0.5:
                continue

            sim = jaccard_similarity(articles[i]["title"], articles[j]["title"])
            if sim >= threshold:
                # Keep higher trust, filter lower trust
                rank_i = _TRUST_RANK.get(articles[i].get("trust_level", "low"), 1)
                rank_j = _TRUST_RANK.get(articles[j].get("trust_level", "low"), 1)
                if rank_i >= rank_j:
                    to_filter.add(articles[j]["id"])
                else:
                    to_filter.add(articles[i]["id"])

    return to_filter
