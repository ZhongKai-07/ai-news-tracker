def match_keywords_in_article(title, content, keywords):
    """Match keywords against article title and content.
    Each keyword dict has: id, name, aliases (list[str]).
    Returns list of: {keyword_id, match_location, context_snippet}.
    Title match takes priority over content match (one match per keyword).
    """
    results = []
    title_lower = title.lower() if title else ""
    content_lower = content.lower() if content else ""

    for kw in keywords:
        terms = [kw["name"]] + kw.get("aliases", [])
        title_matched = any(t.lower() in title_lower for t in terms)
        if title_matched:
            results.append({"keyword_id": kw["id"], "match_location": "title", "context_snippet": title[:200]})
            continue
        if not content:
            continue
        for term in terms:
            pos = content_lower.find(term.lower())
            if pos != -1:
                start = max(0, pos - 80)
                end = min(len(content), pos + len(term) + 80)
                snippet = content[start:end]
                results.append({"keyword_id": kw["id"], "match_location": "content", "context_snippet": snippet})
                break
    return results
