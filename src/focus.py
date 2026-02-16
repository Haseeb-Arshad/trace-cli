"""
TraceCLI Focus Mode
~~~~~~~~~~~~~~~~~~~
Pomodoro-powered focus timer with real-time distraction detection.
Warns you the moment you switch to a distracting app during a focus session.
"""

import time
import threading
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Optional, Callable

import win32gui
import win32process
import psutil

from .categorizer import categorize, is_productive, CATEGORIES, get_category_emoji
from . import database as db


# ── Data Models ────────────────────────────────────────────────────────────

@dataclass
class Interruption:
    """A single distraction interruption during a focus session."""
    timestamp: datetime
    app_name: str
    window_title: str
    category: str
    duration_seconds: float = 0.0


@dataclass
class FocusSession:
    """Represents a complete focus session with metrics."""
    start_time: datetime
    target_minutes: int
    goal_label: str = ""
    end_time: Optional[datetime] = None
    interruptions: list = field(default_factory=list)
    focused_seconds: float = 0.0
    distracted_seconds: float = 0.0

    @property
    def focus_score(self) -> float:
        """Percentage of time spent on productive tasks (0-100)."""
        total = self.focused_seconds + self.distracted_seconds
        if total <= 0:
            return 100.0
        return round((self.focused_seconds / total) * 100, 1)

    @property
    def total_seconds(self) -> float:
        """Total elapsed seconds."""
        return self.focused_seconds + self.distracted_seconds

    @property
    def remaining_seconds(self) -> float:
        """Seconds remaining in the target duration."""
        elapsed = (datetime.now() - self.start_time).total_seconds()
        remaining = (self.target_minutes * 60) - elapsed
        return max(0, remaining)

    @property
    def is_complete(self) -> bool:
        """Whether the target duration has been reached."""
        return self.remaining_seconds <= 0

    def to_dict(self) -> dict:
        return {
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "target_minutes": self.target_minutes,
            "goal_label": self.goal_label,
            "focus_score": self.focus_score,
            "focused_seconds": self.focused_seconds,
            "distracted_seconds": self.distracted_seconds,
            "interruption_count": len(self.interruptions),
        }


# ── Focus Monitor ──────────────────────────────────────────────────────────

class FocusMonitor:
    """
    Background thread that monitors the foreground window during focus mode
    and detects when the user switches to a distracting application.
    """

    def __init__(
        self,
        target_minutes: int = 25,
        goal_label: str = "",
        poll_interval: float = 1.0,
        on_distraction: Optional[Callable] = None,
        on_tick: Optional[Callable] = None,
        on_complete: Optional[Callable] = None,
    ):
        self.target_minutes = target_minutes
        self.goal_label = goal_label
        self.poll_interval = poll_interval
        self.on_distraction = on_distraction  # Called when distraction detected
        self.on_tick = on_tick                # Called every poll cycle
        self.on_complete = on_complete        # Called when timer ends

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self.session: Optional[FocusSession] = None

        # Tracking state
        self._last_app = ""
        self._last_category = ""
        self._distraction_start: Optional[datetime] = None

    def start(self):
        """Start the focus session."""
        if self._running:
            return

        self.session = FocusSession(
            start_time=datetime.now(),
            target_minutes=self.target_minutes,
            goal_label=self.goal_label,
        )
        self._running = True
        self._thread = threading.Thread(
            target=self._run_loop,
            name="TraceCLI-FocusMonitor",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> Optional[FocusSession]:
        """Stop the focus session and return the completed session."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)

        if self.session:
            self.session.end_time = datetime.now()
            self._save_session()

        return self.session

    def _run_loop(self):
        """Main polling loop."""
        while self._running:
            try:
                self._check_foreground()
            except Exception:
                pass

            # Check if session is complete
            if self.session and self.session.is_complete:
                self._running = False
                self.session.end_time = datetime.now()
                self._save_session()
                if self.on_complete:
                    self.on_complete(self.session)
                break

            # Tick callback
            if self.on_tick and self.session:
                self.on_tick(self.session)

            time.sleep(self.poll_interval)

    def _check_foreground(self):
        """Check the current foreground window and detect distractions."""
        try:
            hwnd = win32gui.GetForegroundWindow()
            if not hwnd:
                return

            # Get process info
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            try:
                proc = psutil.Process(pid)
                app_name = proc.name()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                return

            window_title = win32gui.GetWindowText(hwnd)
            category = categorize(app_name, window_title)
            is_distraction = category in {
                CATEGORIES["DISTRACTION"],
            }

            now = datetime.now()

            if is_distraction:
                if self._last_category != "DISTRACTION_ACTIVE":
                    # New distraction started
                    self._distraction_start = now
                    self._last_category = "DISTRACTION_ACTIVE"

                    interruption = Interruption(
                        timestamp=now,
                        app_name=app_name,
                        window_title=window_title,
                        category=category,
                    )
                    self.session.interruptions.append(interruption)

                    if self.on_distraction:
                        self.on_distraction(app_name, window_title, category)
                else:
                    # Still distracted — accumulate time
                    pass

                self.session.distracted_seconds += self.poll_interval
            else:
                if self._last_category == "DISTRACTION_ACTIVE" and self._distraction_start:
                    # Coming back from distraction
                    duration = (now - self._distraction_start).total_seconds()
                    if self.session.interruptions:
                        self.session.interruptions[-1].duration_seconds = duration
                    self._distraction_start = None

                self._last_category = ""
                self.session.focused_seconds += self.poll_interval

            self._last_app = app_name

        except Exception:
            pass

    def _save_session(self):
        """Save the completed focus session to the database."""
        if not self.session:
            return
        try:
            db.insert_focus_session(
                start_time=self.session.start_time,
                end_time=self.session.end_time or datetime.now(),
                target_minutes=self.session.target_minutes,
                actual_focus_seconds=self.session.focused_seconds,
                interruption_count=len(self.session.interruptions),
                focus_score=self.session.focus_score,
                goal_label=self.session.goal_label,
            )
        except Exception:
            pass
