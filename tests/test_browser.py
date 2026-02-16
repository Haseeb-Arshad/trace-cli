"""Tests for browser search extraction."""

import pytest
from src.browser import parse_search_query, extract_searches_from_titles


class TestParseSearchQuery:
    """Test URL-based search query parsing."""

    def test_google_search(self):
        url = "https://www.google.com/search?q=python+sqlite+tutorial&hl=en"
        result = parse_search_query(url)
        assert result is not None
        query, source = result
        assert query == "python sqlite tutorial"
        assert source == "Google"

    def test_bing_search(self):
        url = "https://www.bing.com/search?q=how+to+install+pywin32"
        result = parse_search_query(url)
        assert result is not None
        query, source = result
        assert query == "how to install pywin32"
        assert source == "Bing"

    def test_duckduckgo_search(self):
        url = "https://duckduckgo.com/?q=privacy+focused+apps&t=h_"
        result = parse_search_query(url)
        assert result is not None
        query, source = result
        assert query == "privacy focused apps"
        assert source == "DuckDuckGo"

    def test_youtube_search(self):
        url = "https://www.youtube.com/results?search_query=python+tutorial"
        result = parse_search_query(url)
        assert result is not None
        query, source = result
        assert query == "python tutorial"
        assert source == "YouTube"

    def test_github_search(self):
        url = "https://github.com/search?q=activity+tracker&type=repositories"
        result = parse_search_query(url)
        assert result is not None
        query, source = result
        assert query == "activity tracker"
        assert source == "GitHub"

    def test_stackoverflow_search(self):
        url = "https://stackoverflow.com/search?q=win32gui+python"
        result = parse_search_query(url)
        assert result is not None
        query, source = result
        assert query == "win32gui python"
        assert source == "Stack Overflow"

    def test_non_search_url(self):
        url = "https://www.example.com/page"
        result = parse_search_query(url)
        assert result is None

    def test_google_no_query(self):
        url = "https://www.google.com/search"
        result = parse_search_query(url)
        assert result is None

    def test_encoded_query(self):
        url = "https://www.google.com/search?q=c%2B%2B+tutorial"
        result = parse_search_query(url)
        assert result is not None
        query, _ = result
        # unquote_plus decodes %2B to + and + to space
        assert "c++" in query or "tutorial" in query.lower()


class TestExtractFromTitle:
    """Test window-title-based search extraction."""

    def test_google_search_title(self):
        result = extract_searches_from_titles(
            "python sqlite tutorial - Google Search - Google Chrome",
            "chrome.exe",
        )
        assert result is not None
        assert result.query == "python sqlite tutorial"
        assert result.source == "Google"

    def test_bing_search_title(self):
        result = extract_searches_from_titles(
            "how to use pywin32 - Search - Bing",
            "msedge.exe",
        )
        assert result is not None
        assert result.source == "Bing"

    def test_duckduckgo_title(self):
        result = extract_searches_from_titles(
            "privacy tools at DuckDuckGo",
            "firefox.exe",
        )
        assert result is not None
        assert result.source == "DuckDuckGo"

    def test_non_search_title(self):
        result = extract_searches_from_titles(
            "My Blog - Google Chrome",
            "chrome.exe",
        )
        assert result is None

    def test_non_browser_app(self):
        result = extract_searches_from_titles(
            "python sqlite tutorial - Google Search",
            "notepad.exe",
        )
        assert result is None

    def test_youtube_title(self):
        result = extract_searches_from_titles(
            "How to cook pasta - YouTube",
            "chrome.exe",
        )
        assert result is not None
        assert result.query == "How to cook pasta"
        assert result.source == "YouTube"
