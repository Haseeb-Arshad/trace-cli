"""
Tests for Focus Mode logic.
"""
import pytest
from datetime import datetime, timedelta
from src.focus import FocusSession, FocusMonitor, Interruption

def test_focus_session_initialization():
    start = datetime.now()
    session = FocusSession(start_time=start, target_minutes=25, goal_label="Testing")
    
    assert session.target_minutes == 25
    assert session.goal_label == "Testing"
    assert session.focused_seconds == 0
    assert session.distracted_seconds == 0
    assert session.interruptions == []
    assert not session.is_complete

def test_focus_session_metrics():
    start = datetime.now()
    session = FocusSession(start_time=start, target_minutes=25)
    
    # Simulate time passing
    session.focused_seconds = 600  # 10 mins
    session.distracted_seconds = 60  # 1 min (distracted)
    
    assert session.total_seconds == 660
    assert session.focus_score == pytest.approx(90.9, 0.1)  # 600 / 660 = 90.9%

def test_focus_session_completion():
    start = datetime.now() - timedelta(minutes=30)
    session = FocusSession(start_time=start, target_minutes=25)
    
    # Even if tracked time is low, wall clock time determines completion
    assert session.remaining_seconds == 0
    assert session.is_complete

def test_interruption_tracking():
    start = datetime.now()
    session = FocusSession(start_time=start, target_minutes=25)
    
    intr = Interruption(
        timestamp=datetime.now(),
        app_name="spotify.exe",
        window_title="Spotify",
        category="Distraction",
        duration_seconds=15
    )
    session.interruptions.append(intr)
    
    assert len(session.interruptions) == 1
    assert session.interruptions[0].app_name == "spotify.exe"

    assert len(session.interruptions) == 1
    assert session.interruptions[0].app_name == "spotify.exe"

def test_focus_monitor_lifecycle(monkeypatch):
    import unittest.mock
    
    # Mock OS calls
    mock_get_foreground = unittest.mock.Mock(return_value=123)
    mock_get_text = unittest.mock.Mock(return_value="VS Code")
    mock_get_thread = unittest.mock.Mock(return_value=(0, 456))
    
    monkeypatch.setattr("src.focus.win32gui.GetForegroundWindow", mock_get_foreground)
    monkeypatch.setattr("src.focus.win32gui.GetWindowText", mock_get_text)
    monkeypatch.setattr("src.focus.win32process.GetWindowThreadProcessId", mock_get_thread)
    
    mock_proc = unittest.mock.Mock()
    mock_proc.name.return_value = "code.exe"
    mock_process_class = unittest.mock.Mock(return_value=mock_proc)
    monkeypatch.setattr("src.focus.psutil.Process", mock_process_class)
    
    # Mock DB insert
    mock_insert = unittest.mock.Mock()
    monkeypatch.setattr("src.focus.db.insert_focus_session", mock_insert)
    
    monitor = FocusMonitor(target_minutes=1, poll_interval=0.1)
    
    monitor.start()
    assert monitor._running
    assert monitor.session is not None
    
    # Stop
    session = monitor.stop()
    assert not monitor._running
    assert session.end_time is not None
    
    # Verify save called
    mock_insert.assert_called_once()
