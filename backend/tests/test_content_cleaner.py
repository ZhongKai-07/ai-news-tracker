import pytest
from app.services.content_cleaner import clean_html, complete_data, extract_summary

class TestCleanHtml:
    def test_removes_script_tags(self):
        html = '<p>Hello</p><script>alert("xss")</script><p>World</p>'
        assert "alert" not in clean_html(html)
        assert "Hello" in clean_html(html)
        assert "World" in clean_html(html)

    def test_removes_nav_footer_aside(self):
        html = '<nav>Menu</nav><article><p>Content</p></article><footer>Footer</footer>'
        result = clean_html(html)
        assert "Menu" not in result
        assert "Footer" not in result
        assert "Content" in result

    def test_removes_ad_divs(self):
        html = '<div class="ad-banner">Ad</div><p>Real content</p><div id="sponsor-box">Sponsor</div>'
        result = clean_html(html)
        assert "Ad" not in result
        assert "Sponsor" not in result
        assert "Real content" in result

    def test_extracts_article_tag_priority(self):
        html = '<div>Noise</div><article><p>Main article text</p></article><div>More noise</div>'
        result = clean_html(html)
        assert "Main article text" in result

    def test_preserves_paragraph_breaks(self):
        html = '<p>Paragraph one.</p><p>Paragraph two.</p>'
        result = clean_html(html)
        assert "Paragraph one." in result
        assert "Paragraph two." in result

    def test_empty_input(self):
        assert clean_html("") == ""
        assert clean_html(None) == ""

class TestCompleteData:
    def test_title_fallback_from_content(self):
        data = {"title": "", "content": "This is a long content that should serve as title fallback for the article", "published_at": None, "fetched_at": "2026-03-30T10:00:00Z"}
        result = complete_data(data)
        assert len(result["title"]) > 0
        assert len(result["title"]) <= 80

    def test_title_fallback_from_url_title(self):
        data = {"title": "http://example.com/article", "content": "Some content here about technology", "published_at": None, "fetched_at": "2026-03-30T10:00:00Z"}
        result = complete_data(data)
        # URL-only title should be replaced with content excerpt
        assert not result["title"].startswith("http")

    def test_published_at_kept_if_present(self):
        data = {"title": "Test", "content": "Content", "published_at": "2026-03-30", "fetched_at": "2026-03-31"}
        result = complete_data(data)
        assert result["published_at"] == "2026-03-30"

    def test_published_at_fallback_to_fetched_at(self):
        data = {"title": "Test", "content": "Content", "published_at": None, "fetched_at": "2026-03-31"}
        result = complete_data(data)
        assert result["published_at"] == "2026-03-31"

class TestExtractSummary:
    def test_chinese_sentence_extraction(self):
        text = "这是第一段很短。这是一篇关于人工智能技术发展趋势的深度分析文章，探讨了大语言模型在各个领域的应用前景。第三句话。"
        result = extract_summary(text)
        assert "人工智能技术" in result
        assert len(result) <= 200

    def test_english_sentence_extraction(self):
        text = "By John Smith. This is a comprehensive analysis of the latest trends in artificial intelligence and machine learning technology. More text follows."
        result = extract_summary(text)
        assert "comprehensive analysis" in result
        # Should skip the short "By John Smith." line
        assert not result.startswith("By John")

    def test_skips_short_lines(self):
        text = "Photo credit.\nUpdated 2024.\nThis is the actual article content that discusses important technology trends in depth."
        result = extract_summary(text)
        assert "actual article content" in result

    def test_fallback_to_truncation(self):
        text = "a " * 100  # No clear sentence boundary
        result = extract_summary(text)
        assert len(result) <= 200

    def test_empty_input(self):
        assert extract_summary("") == ""
        assert extract_summary(None) == ""
