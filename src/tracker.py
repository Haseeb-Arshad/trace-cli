"""
TraceCLI Activity Tracker
~~~~~~~~~~~~~~~~~~~~~~~~~
Background listener that monitors the Windows foreground window.
Detects window switches, computes duration, categorizes, and logs to SQLite.
Now also captures memory and CPU usage for each activity.
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
    memory_mb: float = 0.0
    cpu_percent: float = 0.0
    pid: int = 0
    _memory_samples: list = field(default_factory=list, repr=False)
    _cpu_samples: list = field(default_factory=list, repr=False)

    def add_resource_sample(self, memory_mb: float, cpu_percent: float):
        """Add a resource usage sample for averaging."""
        self._memory_samples.append(memory_mb)
        self._cpu_samples.append(cpu_percent)

    def finalize(self):
        """Set end time, compute duration, and average resource usage."""
        self.end_time = datetime.now()
        self.duration_seconds = (
            self.end_time - self.start_time
        ).total_seconds()

        # Average memory and CPU from all samples
        if self._memory_samples:
            self.memory_mb = sum(self._memory_samples) / len(self._memory_samples)
        if self._cpu_samples:
            self.cpu_percent = sum(self._cpu_samples) / len(self._cpu_samples)

    def to_dict(self) -> dict:
        return {
            "app_name": self.app_name,
            "window_title": self.window_title,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_seconds": round(self.duration_seconds, 2),
            "category": self.category,
            "memory_mb": round(self.memory_mb, 2),
            "cpu_percent": round(self.cpu_percent, 2),
            "pid": self.pid,
        }


# ── Foreground Window Helpers ──────────────────────────────────────────────

def get_foreground_info() -> tuple[str, str, int]:
    """
    Get the current foreground window's process name, title, and PID.

    Returns:
        (process_name, window_title, pid) — e.g. ("chrome.exe", "Google - ...", 1234)
    """
    try:
        hwnd = win32gui.GetForegroundWindow()
        if not hwnd:
            return ("", "", 0)

        window_title = win32gui.GetWindowText(hwnd)
        _, pid = win32process.GetWindowThreadProcessId(hwnd)

        try:
            proc = psutil.Process(pid)
            process_name = proc.name()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            process_name = "Unknown"

        return (process_name, window_title, pid)
    except Exception:
        return ("", "", 0)


def get_process_resources(pid: int) -> tuple[float, float]:
    """
    Get memory (MB) and CPU (%) for a given PID.

    Returns:
        (memory_mb, cpu_percent)
    """
    try:
        proc = psutil.Process(pid)
        mem_info = proc.memory_info()
        memory_mb = mem_info.rss / (1024 * 1024)
        cpu_percent = proc.cpu_percent(interval=0)
        return (round(memory_mb, 2), round(cpu_percent, 2))
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return (0.0, 0.0)


# ── Main Tracker ───────────────────────────────────────────────────────────

class ActivityTracker:
    """
    Background activity tracker that polls the foreground window.
    Now captures memory and CPU usage per activity.

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
        """Get the current in-progress activity as a dict with live resource data."""
        with self._lock:
            if self._current:
                elapsed = (datetime.now() - self._current.start_time).total_seconds()
                # Get live resource data
                mem, cpu = 0.0, 0.0
                if self._current.pid:
                    mem, cpu = get_process_resources(self._current.pid)
                return {
                    "app_name": self._current.app_name,
                    "window_title": self._current.window_title,
                    "start_time": self._current.start_time.isoformat(),
                    "duration_seconds": round(elapsed, 1),
                    "category": self._current.category,
                    "memory_mb": mem,
                    "cpu_percent": cpu,
                    "pid": self._current.pid,
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
        app_name, window_title, pid = get_foreground_info()

        # Skip empty / invalid windows
        if not app_name or not window_title:
            return

        with self._lock:
            # First ever check
            if self._current is None:
                self._current = self._create_record(app_name, window_title, pid)
                return

            # Same window — collect resource sample
            if (
                self._current.app_name == app_name
                and self._current.window_title == window_title
            ):
                # Sample resources on every poll
                mem, cpu = get_process_resources(pid)
                self._current.add_resource_sample(mem, cpu)
                return

            # Window changed — finalize old, start new
            self.total_switches += 1
            self._finalize_and_save(self._current)
            self._current = self._create_record(app_name, window_title, pid)

    def _create_record(self, app_name: str, window_title: str, pid: int) -> ActivityRecord:
        """Create a new ActivityRecord with initial resource snapshot."""
        category = categorize(app_name, window_title)

        # Get initial resource reading
        mem, cpu = get_process_resources(pid)

        record = ActivityRecord(
            app_name=app_name,
            window_title=window_title,
            start_time=datetime.now(),
            category=category,
            pid=pid,
        )
        record.add_resource_sample(mem, cpu)

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
                memory_mb=record.memory_mb,
                cpu_percent=record.cpu_percent,
                pid=record.pid,
            )
            self.total_logged += 1

            if self.on_switch:
                self.on_switch(record)
        except Exception:
            pass
