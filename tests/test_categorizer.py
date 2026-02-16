"""Tests for the productivity categorizer."""

import pytest
from src.categorizer import categorize, is_productive, CATEGORIES


class TestProcessBasedCategorization:
    """Test categorization by process name."""

    @pytest.mark.parametrize("process", [
        "code.exe", "pycharm64.exe", "idea64.exe", "devenv.exe",
        "sublime_text.exe", "notepad++.exe", "wt.exe",
        "powershell.exe", "cmd.exe", "postman.exe",
    ])
    def test_dev_tools(self, process):
        result = categorize(process, "Some window title")
        assert result == CATEGORIES["DEVELOPMENT"]

    @pytest.mark.parametrize("process", [
        "slack.exe", "discord.exe", "teams.exe", "zoom.exe",
        "telegram.exe", "outlook.exe",
    ])
    def test_communication_apps(self, process):
        result = categorize(process, "Some window title")
        assert result == CATEGORIES["COMMUNICATION"]

    @pytest.mark.parametrize("process", [
        "winword.exe", "excel.exe", "notion.exe", "obsidian.exe",
        "figma.exe",
    ])
    def test_productivity_apps(self, process):
        result = categorize(process, "Some window title")
        assert result == CATEGORIES["PRODUCTIVITY"]

    @pytest.mark.parametrize("process", [
        "spotify.exe", "vlc.exe",
    ])
    def test_distraction_apps(self, process):
        result = categorize(process, "Some window title")
        assert result == CATEGORIES["DISTRACTION"]


class TestBrowserCategorization:
    """Test browser window categorization by title."""

    def test_browser_stackoverflow(self):
        result = categorize("chrome.exe", "python list comprehension - Stack Overflow - Google Chrome")
        assert result == CATEGORIES["RESEARCH"]

    def test_browser_github(self):
        result = categorize("msedge.exe", "myrepo - github.com - Edge")
        assert result == CATEGORIES["RESEARCH"]

    def test_browser_youtube_distraction(self):
        result = categorize("chrome.exe", "Funny Cat Videos - YouTube - Google Chrome")
        assert result == CATEGORIES["DISTRACTION"]

    def test_browser_reddit_distraction(self):
        result = categorize("firefox.exe", "r/gaming - Reddit")
        assert result == CATEGORIES["DISTRACTION"]

    def test_browser_gmail_communication(self):
        result = categorize("chrome.exe", "Inbox - Gmail")
        assert result == CATEGORIES["COMMUNICATION"]

    def test_browser_google_docs_productivity(self):
        result = categorize("chrome.exe", "Project Plan - Google Docs")
        assert result == CATEGORIES["PRODUCTIVITY"]

    def test_browser_generic(self):
        result = categorize("chrome.exe", "My Random Website")
        assert result == CATEGORIES["BROWSING"]

    def test_browser_documentation(self):
        result = categorize("chrome.exe", "React Documentation - Getting Started")
        assert result == CATEGORIES["RESEARCH"]


class TestIsProductive:
    def test_development_is_productive(self):
        assert is_productive(CATEGORIES["DEVELOPMENT"]) is True

    def test_research_is_productive(self):
        assert is_productive(CATEGORIES["RESEARCH"]) is True

    def test_productivity_is_productive(self):
        assert is_productive(CATEGORIES["PRODUCTIVITY"]) is True

    def test_distraction_is_not_productive(self):
        assert is_productive(CATEGORIES["DISTRACTION"]) is False

    def test_browsing_is_not_productive(self):
        assert is_productive(CATEGORIES["BROWSING"]) is False

    def test_communication_is_not_productive(self):
        assert is_productive(CATEGORIES["COMMUNICATION"]) is False


class TestEdgeCases:
    def test_unknown_process(self):
        result = categorize("randomapp.exe", "Some window")
        assert result == CATEGORIES["OTHER"]

    def test_case_insensitive_process(self):
        result = categorize("Code.exe", "test.py")
        assert result == CATEGORIES["DEVELOPMENT"]

    def test_empty_title(self):
        result = categorize("chrome.exe", "")
        assert result == CATEGORIES["BROWSING"]
