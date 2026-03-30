import pytest
from app.services.web_scraper import extract_articles_from_html

def test_extract_with_css_selectors():
    html = """
    <html><body>
      <div class="post">
        <h2><a href="/article/1">First Post</a></h2>
        <p class="summary">Summary of first post</p>
      </div>
      <div class="post">
        <h2><a href="/article/2">Second Post</a></h2>
        <p class="summary">Summary of second post</p>
      </div>
    </body></html>
    """
    config = {"item_selector": "div.post", "title_selector": "h2 a", "url_selector": "h2 a", "url_attribute": "href", "content_selector": "p.summary", "base_url": "http://example.com"}
    articles = extract_articles_from_html(html, config)
    assert len(articles) == 2
    assert articles[0]["title"] == "First Post"
    assert articles[0]["url"] == "http://example.com/article/1"
    assert articles[0]["content"] == "Summary of first post"

def test_extract_handles_absolute_urls():
    html = '<div class="item"><a href="http://full-url.com/post">Full URL Post</a></div>'
    config = {"item_selector": "div.item", "title_selector": "a", "url_selector": "a", "url_attribute": "href", "base_url": "http://example.com"}
    articles = extract_articles_from_html(html, config)
    assert articles[0]["url"] == "http://full-url.com/post"

def test_extract_empty_html():
    articles = extract_articles_from_html("", {"item_selector": "div.post", "base_url": ""})
    assert articles == []
