import pytest
from app.services.keyword_matcher import match_keywords_in_article

def test_match_in_title():
    keywords = [{"id": 1, "name": "AI Agent", "aliases": ["AI助手"]}]
    matches = match_keywords_in_article(title="Building an AI Agent from scratch", content="Some unrelated content.", keywords=keywords)
    assert len(matches) == 1
    assert matches[0]["keyword_id"] == 1
    assert matches[0]["match_location"] == "title"

def test_match_alias_case_insensitive():
    keywords = [{"id": 1, "name": "Spec-driven Design", "aliases": ["规约驱动设计", "specification-driven"]}]
    matches = match_keywords_in_article(title="A new approach", content="We used SPECIFICATION-DRIVEN methodology in our project.", keywords=keywords)
    assert len(matches) == 1
    assert matches[0]["match_location"] == "content"
    assert "SPECIFICATION-DRIVEN" in matches[0]["context_snippet"]

def test_match_both_title_and_content():
    keywords = [{"id": 1, "name": "MCP", "aliases": []}]
    matches = match_keywords_in_article(title="MCP Protocol Overview", content="The MCP standard defines a new way to connect.", keywords=keywords)
    assert len(matches) == 1
    assert matches[0]["match_location"] == "title"

def test_no_match():
    keywords = [{"id": 1, "name": "Blockchain", "aliases": ["区块链"]}]
    matches = match_keywords_in_article(title="Python tips", content="How to write better code.", keywords=keywords)
    assert len(matches) == 0

def test_multiple_keywords_match():
    keywords = [{"id": 1, "name": "AI Agent", "aliases": []}, {"id": 2, "name": "MCP", "aliases": []}]
    matches = match_keywords_in_article(title="AI Agent meets MCP", content="Content here.", keywords=keywords)
    assert len(matches) == 2

def test_context_snippet_extraction():
    keywords = [{"id": 1, "name": "LLM", "aliases": []}]
    content = "A" * 100 + " LLM is powerful " + "B" * 100
    matches = match_keywords_in_article(title="Title", content=content, keywords=keywords)
    assert len(matches) == 1
    snippet = matches[0]["context_snippet"]
    assert "LLM" in snippet
    assert len(snippet) <= 200
