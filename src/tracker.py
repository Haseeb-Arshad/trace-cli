"""
TraceCLI Activity Tracker
~~~~~~~~~~~~~~~~~~~~~~~~~
Background listener that monitors the Windows foreground window.
Detects window switches, computes duration, categorizes, and logs to SQLite.
"""

import time
import threading
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional, Callable

import win32gui
import win32process
import psutil

from . import database as db
from .categorizer import categorize
from .browser import extract_searches_from_titles


# ── Data Structures ────────────────────────────────────────────────────────

@dataclass
class ActivityRecord:
    """An in-progress or completed activity record."""
    app_name: str
    window_title: str
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_seconds: float = 0.0
    category: str = "❓ Other"

    def finalize(self):
        """Set end time and compute duration."""
        self.end_time = datetime.now()
        self.duration_seconds = (
            self.end_time - self.start_time
        ).total_seconds()

    def to_dict(self) -> dict:
        return {
            "app_name": self.app_name,
            "window_title": self.window_title,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_seconds": round(self.duration_seconds, 2),
            "category": self.category,
        }


# ── Foreground Window Helpers ──────────────────────────────────────────────

def get_foreground_info() -> tuple[str, str]:
    """
    Get the current foreground window's process name and title.

    Returns:
        (process_name, window_title) — e.g. ("chrome.exe", "Google - Google Chrome")
    """
    try:
        hwnd = win32gui.GetForegroundWindow()
        if not hwnd:
            return ("", "")

        window_title = win32gui.GetWindowText(hwnd)
        _, pid = win32process.GetWindowThreadProcessId(hwnd)

        try:
            proc = psutil.Process(pid)
            process_name = proc.name()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            process_name = "Unknown"

        return (process_name, window_title)
    except Exception:
        return ("", "")


# ── Main Tracker ───────────────────────────────────────────────────────────

class ActivityTracker:
    """
    Background activity tracker that polls the foreground window.

    Usage:
        tracker = ActivityTracker()
        tracker.start()
        # ... later ...
        tracker.stop()
    """

    def __init__(
        self,
        poll_interval: float = 1.0,
        min_duration: float = 2.0,
        on_switch: Optional[Callable[[ActivityRecord], None]] = None,
    ):
        """
        Args:
            poll_interval: Seconds between foreground window checks.
            min_duration: Minimum seconds an activity must last to be logged.
            on_switch: Optional callback fired on each window switch.
        """
        self.poll_interval = poll_interval
        self.min_duration = min_duration
        self.on_switch = on_switch

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._current: Optional[ActivityRecord] = None
        self._lock = threading.Lock()

        # Stats
        self.total_switches = 0
        self.total_logged = 0
        self.session_start: Optional[datetime] = None

    # ── Public Methods ─────────────────────────────────────────────────

    def start(self):
        """Start the background tracking thread."""
        if self._running:
            return

        db.init_db()
        self._running = True
        self.session_start = datetime.now()
        self._thread = threading.Thread(
            target=self._poll_loop,
            name="TraceCLI-Tracker",
            daemon=True,
        )
        self._thread.start()

    def stop(self):
        """Stop tracking and flush the current activity."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        self.flush()

    def flush(self):
        """Flush the current in-progress activity to the database."""
        with self._lock:
            if self._current:
                self._finalize_and_save(self._current)
                self._current = None

    def get_current(self) -> Optional[dict]:
        """Get the current in-progress activity as a dict."""
        with self._lock:
            if self._current:
                # Create a snapshot with live duration
                elapsed = (datetime.now() - self._current.start_time).total_seconds()
                return {
                    "app_name": self._current.app_name,
                    "window_title": self._current.window_title,
                    "start_time": self._current.start_time.isoformat(),
                    "duration_seconds": round(elapsed, 1),
                    "category": self._current.category,
                }
        return None

    def get_session_duration(self) -> float:
        """Get total seconds since tracking started."""
        if self.session_start:
            return (datetime.now() - self.session_start).total_seconds()
        return 0.0

    # ── Internal Logic ─────────────────────────────────────────────────

    def _poll_loop(self):
        """Main polling loop — runs in a background thread."""
        while self._running:
            try:
                self._check_foreground()
            except Exception:
                pass  # Never crash the tracking loop
            time.sleep(self.poll_interval)

    def _check_foreground(self):
        """Check the foreground window and handle transitions."""
        app_name, window_title = get_foreground_info()

        # Skip empty / invalid windows
        if not app_name or not window_title:
            return

        with self._lock:
            # First ever check
            if self._current is None:
                self._current = self._create_record(app_name, window_title)
                return

            # Same window — no action
            if (
                self._current.app_name == app_name
                and self._current.window_title == window_title
            ):
                return

            # Window changed — finalize old, start new
            self.total_switches += 1
            self._finalize_and_save(self._current)
            self._current = self._create_record(app_name, window_title)

    def _create_record(self, app_name: str, window_title: str) -> ActivityRecord:
        """Create a new ActivityRecord."""
        category = categorize(app_name, window_title)
        record = ActivityRecord(
            app_name=app_name,
            window_title=window_title,
            start_time=datetime.now(),
            category=category,
        )

        # Try to extract search queries from browser titles
        search = extract_searches_from_titles(window_title, app_name)
        if search:
            try:
                db.insert_search(
                    timestamp=search.timestamp,
                    browser=search.browser,
                    query=search.query,
                    url=search.url,
                    source=search.source,
                )
            except Exception:
                pass

        return record

    def _finalize_and_save(self, record: ActivityRecord):
        """Finalize a record and save it to the database."""
        record.finalize()

        # Only log activities that lasted long enough
        if record.duration_seconds < self.min_duration:
            return

        try:
            db.insert_activity(
                app_name=record.app_name,
                window_title=record.window_title,
                start_time=record.start_time,
                end_time=record.end_time,
                duration_seconds=record.duration_seconds,
                category=record.category,
            )
            self.total_logged += 1

            if self.on_switch:
                self.on_switch(record)
        except Exception:
            pass
