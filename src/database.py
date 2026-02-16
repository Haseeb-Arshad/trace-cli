"""
TraceCLI Database Layer
~~~~~~~~~~~~~~~~~~~~~~~
SQLite schema and helper functions for storing activity data locally.
All data lives in ~/.tracecli/trace.db — never leaves your machine.
"""

import sqlite3
import os
import threading
from datetime import datetime, date
from pathlib import Path
from typing import Optional


# ── Database Location ──────────────────────────────────────────────────────

DATA_DIR = Path.home() / ".tracecli"
DB_PATH = DATA_DIR / "trace.db"

# Thread-local storage for connections
_local = threading.local()


def _ensure_data_dir():
    """Create the data directory if it doesn't exist."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def get_connection() -> sqlite3.Connection:
    """
    Get a thread-safe SQLite connection.
    Each thread gets its own connection stored in thread-local storage.
    """
    if not hasattr(_local, "connection") or _local.connection is None:
        _ensure_data_dir()
        _local.connection = sqlite3.connect(
            str(DB_PATH),
            timeout=10,
            detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
        )
        _local.connection.row_factory = sqlite3.Row
        _local.connection.execute("PRAGMA journal_mode=WAL")
        _local.connection.execute("PRAGMA synchronous=NORMAL")
    return _local.connection


def close_connection():
    """Close the current thread's connection."""
    if hasattr(_local, "connection") and _local.connection is not None:
        _local.connection.close()
        _local.connection = None


# ── Schema ─────────────────────────────────────────────────────────────────

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS activity_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    app_name        TEXT    NOT NULL,
    window_title    TEXT    NOT NULL,
    start_time      TEXT    NOT NULL,
    end_time        TEXT    NOT NULL,
    duration_seconds REAL   NOT NULL,
    category        TEXT    NOT NULL DEFAULT 'Other'
);

CREATE TABLE IF NOT EXISTS search_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp   TEXT    NOT NULL,
    browser     TEXT    NOT NULL,
    query       TEXT    NOT NULL,
    url         TEXT    NOT NULL,
    source      TEXT    NOT NULL DEFAULT 'Unknown'
);

CREATE TABLE IF NOT EXISTS daily_stats (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    date                TEXT    NOT NULL UNIQUE,
    total_seconds       REAL    NOT NULL DEFAULT 0,
    productive_seconds  REAL    NOT NULL DEFAULT 0,
    distraction_seconds REAL    NOT NULL DEFAULT 0,
    top_app             TEXT    NOT NULL DEFAULT '',
    top_category        TEXT    NOT NULL DEFAULT '',
    session_count       INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_activity_start ON activity_log(start_time);
CREATE INDEX IF NOT EXISTS idx_activity_category ON activity_log(category);
CREATE INDEX IF NOT EXISTS idx_search_timestamp ON search_history(timestamp);
CREATE INDEX IF NOT EXISTS idx_daily_date ON daily_stats(date);
"""


def init_db():
    """Initialize the database schema. Safe to call multiple times."""
    conn = get_connection()
    conn.executescript(SCHEMA_SQL)
    conn.commit()


# ── Insert Helpers ─────────────────────────────────────────────────────────

def insert_activity(
    app_name: str,
    window_title: str,
    start_time: datetime,
    end_time: datetime,
    duration_seconds: float,
    category: str = "Other",
):
    """Insert an activity record into the log."""
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO activity_log
            (app_name, window_title, start_time, end_time, duration_seconds, category)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            app_name,
            window_title,
            start_time.isoformat(),
            end_time.isoformat(),
            round(duration_seconds, 2),
            category,
        ),
    )
    conn.commit()


def insert_search(
    timestamp: datetime,
    browser: str,
    query: str,
    url: str,
    source: str = "Unknown",
):
    """Insert a search query record."""
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO search_history (timestamp, browser, query, url, source)
        VALUES (?, ?, ?, ?, ?)
        """,
        (timestamp.isoformat(), browser, query, url, source),
    )
    conn.commit()


# ── Query Helpers ──────────────────────────────────────────────────────────

def query_activities(
    target_date: Optional[date] = None,
    limit: int = 100,
) -> list[dict]:
    """
    Fetch activity records for a given date.
    Returns list of dicts. Defaults to today.
    """
    if target_date is None:
        target_date = date.today()

    conn = get_connection()
    date_prefix = target_date.isoformat()
    cursor = conn.execute(
        """
        SELECT app_name, window_title, start_time, end_time,
               duration_seconds, category
        FROM activity_log
        WHERE start_time LIKE ? || '%'
        ORDER BY start_time DESC
        LIMIT ?
        """,
        (date_prefix, limit),
    )
    return [dict(row) for row in cursor.fetchall()]


def query_searches(
    target_date: Optional[date] = None,
    limit: int = 50,
) -> list[dict]:
    """Fetch search history for a given date."""
    if target_date is None:
        target_date = date.today()

    conn = get_connection()
    date_prefix = target_date.isoformat()
    cursor = conn.execute(
        """
        SELECT timestamp, browser, query, url, source
        FROM search_history
        WHERE timestamp LIKE ? || '%'
        ORDER BY timestamp DESC
        LIMIT ?
        """,
        (date_prefix, limit),
    )
    return [dict(row) for row in cursor.fetchall()]


def get_category_breakdown(target_date: Optional[date] = None) -> list[dict]:
    """Get time spent per category for a given date."""
    if target_date is None:
        target_date = date.today()

    conn = get_connection()
    date_prefix = target_date.isoformat()
    cursor = conn.execute(
        """
        SELECT category,
               SUM(duration_seconds) as total_seconds,
               COUNT(*) as switch_count
        FROM activity_log
        WHERE start_time LIKE ? || '%'
        GROUP BY category
        ORDER BY total_seconds DESC
        """,
        (date_prefix,),
    )
    return [dict(row) for row in cursor.fetchall()]


def get_app_breakdown(target_date: Optional[date] = None) -> list[dict]:
    """Get time spent per application for a given date."""
    if target_date is None:
        target_date = date.today()

    conn = get_connection()
    date_prefix = target_date.isoformat()
    cursor = conn.execute(
        """
        SELECT app_name,
               SUM(duration_seconds) as total_seconds,
               COUNT(*) as switch_count
        FROM activity_log
        WHERE start_time LIKE ? || '%'
        GROUP BY app_name
        ORDER BY total_seconds DESC
        """,
        (date_prefix,),
    )
    return [dict(row) for row in cursor.fetchall()]


# ── Daily Stats ────────────────────────────────────────────────────────────

PRODUCTIVE_CATEGORIES = {
    "💻 Development",
    "📚 Research",
    "📝 Productivity",
}

DISTRACTION_CATEGORIES = {
    "🎮 Distraction",
}


def upsert_daily_stats(target_date: Optional[date] = None):
    """Compute and upsert the daily summary from activity_log data."""
    if target_date is None:
        target_date = date.today()

    conn = get_connection()
    date_prefix = target_date.isoformat()

    # Total time
    row = conn.execute(
        "SELECT COALESCE(SUM(duration_seconds), 0) FROM activity_log WHERE start_time LIKE ? || '%'",
        (date_prefix,),
    ).fetchone()
    total = row[0]

    # Productive time
    placeholders = ",".join("?" for _ in PRODUCTIVE_CATEGORIES)
    row = conn.execute(
        f"SELECT COALESCE(SUM(duration_seconds), 0) FROM activity_log WHERE start_time LIKE ? || '%' AND category IN ({placeholders})",
        (date_prefix, *PRODUCTIVE_CATEGORIES),
    ).fetchone()
    productive = row[0]

    # Distraction time
    placeholders = ",".join("?" for _ in DISTRACTION_CATEGORIES)
    row = conn.execute(
        f"SELECT COALESCE(SUM(duration_seconds), 0) FROM activity_log WHERE start_time LIKE ? || '%' AND category IN ({placeholders})",
        (date_prefix, *DISTRACTION_CATEGORIES),
    ).fetchone()
    distraction = row[0]

    # Top app
    row = conn.execute(
        "SELECT app_name FROM activity_log WHERE start_time LIKE ? || '%' GROUP BY app_name ORDER BY SUM(duration_seconds) DESC LIMIT 1",
        (date_prefix,),
    ).fetchone()
    top_app = row[0] if row else ""

    # Top category
    row = conn.execute(
        "SELECT category FROM activity_log WHERE start_time LIKE ? || '%' GROUP BY category ORDER BY SUM(duration_seconds) DESC LIMIT 1",
        (date_prefix,),
    ).fetchone()
    top_category = row[0] if row else ""

    # Session count (unique contiguous blocks)
    row = conn.execute(
        "SELECT COUNT(*) FROM activity_log WHERE start_time LIKE ? || '%'",
        (date_prefix,),
    ).fetchone()
    session_count = row[0]

    conn.execute(
        """
        INSERT INTO daily_stats (date, total_seconds, productive_seconds, distraction_seconds, top_app, top_category, session_count)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(date) DO UPDATE SET
            total_seconds = excluded.total_seconds,
            productive_seconds = excluded.productive_seconds,
            distraction_seconds = excluded.distraction_seconds,
            top_app = excluded.top_app,
            top_category = excluded.top_category,
            session_count = excluded.session_count
        """,
        (target_date.isoformat(), total, productive, distraction, top_app, top_category, session_count),
    )
    conn.commit()


def get_daily_stats(target_date: Optional[date] = None) -> Optional[dict]:
    """Fetch the daily summary for a date."""
    if target_date is None:
        target_date = date.today()

    conn = get_connection()
    cursor = conn.execute(
        "SELECT * FROM daily_stats WHERE date = ?",
        (target_date.isoformat(),),
    )
    row = cursor.fetchone()
    return dict(row) if row else None


def get_stats_range(days: int = 7) -> list[dict]:
    """Fetch daily stats for the last N days."""
    conn = get_connection()
    cursor = conn.execute(
        """
        SELECT * FROM daily_stats
        ORDER BY date DESC
        LIMIT ?
        """,
        (days,),
    )
    return [dict(row) for row in cursor.fetchall()]
