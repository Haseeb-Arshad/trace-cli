"""
Tests for Heatmap logic.
"""
import pytest
import unittest.mock
from datetime import date, timedelta
from src.database import get_productivity_heatmap_data, get_streak_info

# Mock DB connection and cursor using monkeypatch and unittest.mock

def test_streak_calculation_logic(monkeypatch):
    # Mock get_connection to return a sequence of dates
    mock_conn = unittest.mock.Mock()
    mock_cursor = unittest.mock.Mock()
    
    # Case 1: 3-day streak ending today
    today = date.today()
    dates = [
        today - timedelta(days=2),
        today - timedelta(days=1),
        today
    ]
    
    monkeypatch.setattr("src.database.get_connection", lambda: mock_conn)
    mock_conn.execute.return_value = mock_cursor
    mock_cursor.fetchall.return_value = [{"date": d.isoformat()} for d in dates]
    
    stats = get_streak_info()
    
    assert stats["current_streak"] == 3
    assert stats["longest_streak"] == 3
    assert stats["total_days_tracked"] == 3

def test_streak_broken_logic(monkeypatch):
    # Case 2: Streak broken yesterday
    today = date.today()
    dates = [
        today - timedelta(days=3),
        today - timedelta(days=2)
    ]
    # Missing yesterday and today
    
    mock_conn = unittest.mock.Mock()
    mock_cursor = unittest.mock.Mock()
    monkeypatch.setattr("src.database.get_connection", lambda: mock_conn)
    mock_conn.execute.return_value = mock_cursor
    mock_cursor.fetchall.return_value = [{"date": d.isoformat()} for d in dates]
    
    stats = get_streak_info()
    
    assert stats["current_streak"] == 0
    assert stats["longest_streak"] == 2
    assert stats["total_days_tracked"] == 2

def test_heatmap_data_formatting(monkeypatch):
    mock_conn = unittest.mock.Mock()
    mock_cursor = unittest.mock.Mock()
    
    # Mock return data from DB
    mock_data = [
        {"date": "2023-01-01", "total_seconds": 3600, "productive_seconds": 1800, "distraction_seconds": 1800},
        {"date": "2023-01-02", "total_seconds": 7200, "productive_seconds": 7200, "distraction_seconds": 0},
        {"date": "2023-01-03", "total_seconds": 0, "productive_seconds": 0, "distraction_seconds": 0}, # empty day usually filtered by logic logic but let's see
    ]
    
    monkeypatch.setattr("src.database.get_connection", lambda: mock_conn)
    mock_conn.execute.return_value = mock_cursor
    mock_cursor.fetchall.return_value = mock_data
    
    results = get_productivity_heatmap_data(weeks=1)
    
    assert len(results) == 3
    assert results[0]["score"] == 50  # 1800/3600
    assert results[1]["score"] == 100 # 7200/7200
    assert results[2]["score"] == 0   # 0/0
