from app.services.keyword_matcher import match_keywords_in_article


def classify_rule_matches(title: str, content: str, keywords: list[dict]) -> dict:
    """Classify rule-based matches into strong (title) and weak (content-only)."""
    all_matches = match_keywords_in_article(title, content, keywords)
    strong = [m for m in all_matches if m["match_location"] == "title"]
    weak = [m for m in all_matches if m["match_location"] == "content"]
    return {"strong": strong, "weak": weak}


class SemanticMatcher:
    def __init__(self, llm_service):
        self.llm_service = llm_service

    async def match_batch(
        self, articles: list[dict], keywords: list[dict], batch_size: int = 20
    ) -> list[dict]:
        """Match a batch of articles against keywords using rule + LLM hybrid.

        Each article dict: {id, title, cleaned_content}
        Each keyword dict: {id, name, aliases}
        Returns: list of {article_id, keyword_id, match_location, context_snippet, match_method, match_reason}
        """
        all_results = []
        needs_llm = []  # (article, remaining_keywords, weak_matches)

        for article in articles:
            classified = classify_rule_matches(
                article["title"], article.get("cleaned_content") or "", keywords
            )
            # Strong hits go directly
            for match in classified["strong"]:
                all_results.append({
                    "article_id": article["id"],
                    "keyword_id": match["keyword_id"],
                    "match_location": match["match_location"],
                    "context_snippet": match["context_snippet"],
                    "match_method": "rule",
                    "match_reason": None,
                })

            # If there are no strong hits, send to LLM for semantic check
            strong_kw_ids = {m["keyword_id"] for m in classified["strong"]}
            remaining_kws = [k for k in keywords if k["id"] not in strong_kw_ids]
            if remaining_kws:
                needs_llm.append((article, remaining_kws, classified["weak"]))

        # Batch LLM calls
        if needs_llm:
            for i in range(0, len(needs_llm), batch_size):
                batch = needs_llm[i: i + batch_size]
                llm_results = await self._llm_match_batch(batch, keywords)
                all_results.extend(llm_results)

        return all_results

    async def _llm_match_batch(self, batch: list[tuple], all_keywords: list[dict]) -> list[dict]:
        """Send a batch of articles to LLM for semantic matching."""
        # Collect all unique remaining keywords across the batch
        all_remaining_kw_names = set()
        for _, remaining_kws, _ in batch:
            for k in remaining_kws:
                all_remaining_kw_names.add(k["name"])

        kw_name_to_id = {k["name"]: k["id"] for k in all_keywords}

        articles_text = []
        for idx, (article, _, _) in enumerate(batch):
            content_preview = (article.get("cleaned_content") or "")[:300]
            articles_text.append(f"{idx + 1}. 标题：{article['title']}\n   摘要：{content_preview}")

        prompt = (
            f"以下是一批技术文章的标题和摘要，以及一组需要追踪的关键词。\n"
            f"请判断每篇文章与哪些关键词真正相关（语义层面，不要求字面出现）。\n\n"
            f"关键词列表：{', '.join(sorted(all_remaining_kw_names))}\n\n"
            f"文章列表：\n" + "\n".join(articles_text) + "\n\n"
            f'返回 JSON 数组：[{{"index": 1, "matched_keywords": ["关键词名"], "confidence": "high/medium", "reason": "原因"}}]\n'
            f"如果某篇文章不匹配任何关键词，不要包含在结果中。"
        )

        try:
            llm_results = await self.llm_service.call_json("tier2", prompt)
        except Exception:
            # LLM failed — return weak rule matches as fallback
            results = []
            for article, _, weak_matches in batch:
                for m in weak_matches:
                    results.append({
                        "article_id": article["id"],
                        "keyword_id": m["keyword_id"],
                        "match_location": m["match_location"],
                        "context_snippet": m["context_snippet"],
                        "match_method": "rule",
                        "match_reason": "LLM unavailable, fell back to rule match",
                    })
            return results

        results = []
        for item in llm_results:
            idx = item.get("index", 0) - 1
            if idx < 0 or idx >= len(batch):
                continue
            article, _, _ = batch[idx]
            confidence = item.get("confidence", "medium")
            method = "llm" if confidence == "high" else "llm_uncertain"
            for kw_name in item.get("matched_keywords", []):
                kw_id = kw_name_to_id.get(kw_name)
                if kw_id:
                    results.append({
                        "article_id": article["id"],
                        "keyword_id": kw_id,
                        "match_location": "content",
                        "context_snippet": (article.get("cleaned_content") or "")[:200],
                        "match_method": method,
                        "match_reason": item.get("reason", ""),
                    })
        return results
