import pytest
from unittest.mock import patch
from src import categorizer, config

@pytest.fixture
def mock_rules():
    """Mock the user rules."""
    rules = config.UserRules()
    rules.productive_processes = {"blender.exe", "unity.exe"}
    rules.distraction_processes = {"notepad.exe"} # Usually "Other" or "Dev" depending on config
    rules.productive_keywords = ["coursera", "graph visualization"]
    rules.distraction_keywords = ["funny cat videos"]
    return rules

def test_custom_process_rules(mock_rules):
    """Test that custom process rules override defaults."""
    with patch.object(categorizer, 'USER_RULES', mock_rules):
        # blender.exe should be productive
        assert categorizer.categorize("blender.exe", "Blender Project") == categorizer.CATEGORIES["PRODUCTIVITY"]
        
        # notepad.exe should be distraction (user override)
        assert categorizer.categorize("notepad.exe", "Notes") == categorizer.CATEGORIES["DISTRACTION"]

def test_custom_keyword_rules(mock_rules):
    """Test that custom keyword rules override defaults."""
    with patch.object(categorizer, 'USER_RULES', mock_rules):
        # "coursera" in title -> productive
        assert categorizer.categorize("chrome.exe", "Learning Python on Coursera - Chrome") == categorizer.CATEGORIES["PRODUCTIVITY"]
        
        # "funny cat videos" in title -> distraction
        assert categorizer.categorize("chrome.exe", "Funny Cat Videos - YouTube") == categorizer.CATEGORIES["DISTRACTION"]

def test_default_fallback(mock_rules):
    """Test that defaults still work when no user rule matches."""
    with patch.object(categorizer, 'USER_RULES', mock_rules):
        # chrome.exe without keywords -> Browsing (default)
        assert categorizer.categorize("chrome.exe", "Random Page - Chrome") == categorizer.CATEGORIES["BROWSING"]
        
        # code.exe -> Development (default)
        assert categorizer.categorize("code.exe", "main.py - VS Code") == categorizer.CATEGORIES["DEVELOPMENT"]
