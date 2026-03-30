import pytest
from unittest.mock import patch, AsyncMock
from app.services.rss_parser import parse_rss_feed, parse_feed_entry

def test_parse_feed_entry_basic():
    entry = {"title": "Test Article", "link": "http://example.com/article1", "summary": "This is the summary.", "published_parsed": (2026, 3, 30, 12, 0, 0, 0, 89, 0)}
    result = parse_feed_entry(entry)
    assert result["title"] == "Test Article"
    assert result["url"] == "http://example.com/article1"
    assert result["content"] == "This is the summary."
    assert result["published_at"] is not None

def test_parse_feed_entry_with_content_detail():
    entry = {"title": "Test", "link": "http://example.com/2", "content": [{"value": "<p>Full content here</p>"}]}
    result = parse_feed_entry(entry)
    assert "Full content here" in result["content"]

def test_parse_feed_entry_missing_fields():
    entry = {"title": "Only Title", "link": "http://example.com/3"}
    result = parse_feed_entry(entry)
    assert result["title"] == "Only Title"
    assert result["content"] is None
    assert result["published_at"] is None
