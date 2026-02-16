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
-- Core activity tracking (enriched with resource data)
CREATE TABLE IF NOT EXISTS activity_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    app_name        TEXT    NOT NULL,
    window_title    TEXT    NOT NULL,
    start_time      TEXT    NOT NULL,
    end_time        TEXT    NOT NULL,
    duration_seconds REAL   NOT NULL,
    category        TEXT    NOT NULL DEFAULT 'Other',
    memory_mb       REAL    DEFAULT 0,
    cpu_percent     REAL    DEFAULT 0,
    pid             INTEGER DEFAULT 0
);

-- Search query extraction
CREATE TABLE IF NOT EXISTS search_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp   TEXT    NOT NULL,
    browser     TEXT    NOT NULL,
    query       TEXT    NOT NULL,
    url         TEXT    NOT NULL,
    source      TEXT    NOT NULL DEFAULT 'Unknown'
);

-- Daily productivity summary
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

-- System-wide process snapshots (every ~30s)
CREATE TABLE IF NOT EXISTS process_snapshots (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp   TEXT    NOT NULL,
    app_name    TEXT    NOT NULL,
    pid         INTEGER NOT NULL,
    memory_mb   REAL    NOT NULL DEFAULT 0,
    cpu_percent REAL    NOT NULL DEFAULT 0,
    status      TEXT    NOT NULL DEFAULT 'running',
    num_threads INTEGER NOT NULL DEFAULT 0
);

-- Per-app daily aggregate analytics
CREATE TABLE IF NOT EXISTS app_usage_history (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    date                TEXT    NOT NULL,
    app_name            TEXT    NOT NULL,
    total_duration      REAL    NOT NULL DEFAULT 0,
    total_memory_avg_mb REAL    NOT NULL DEFAULT 0,
    total_cpu_avg       REAL    NOT NULL DEFAULT 0,
    launch_count        INTEGER NOT NULL DEFAULT 0,
    category            TEXT    NOT NULL DEFAULT 'Other',
    role                TEXT    NOT NULL DEFAULT '',
    UNIQUE(date, app_name)
);

-- Full browser URL history
CREATE TABLE IF NOT EXISTS browser_urls (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp       TEXT    NOT NULL,
    browser         TEXT    NOT NULL,
    url             TEXT    NOT NULL,
    title           TEXT    NOT NULL DEFAULT '',
    visit_duration  REAL    NOT NULL DEFAULT 0,
    domain          TEXT    NOT NULL DEFAULT ''
);

-- Focus session tracking
CREATE TABLE IF NOT EXISTS focus_sessions (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    start_time          TEXT    NOT NULL,
    end_time            TEXT    NOT NULL,
    target_minutes      INTEGER NOT NULL DEFAULT 25,
    actual_focus_seconds REAL   NOT NULL DEFAULT 0,
    interruption_count  INTEGER NOT NULL DEFAULT 0,
    focus_score         REAL    NOT NULL DEFAULT 0,
    goal_label          TEXT    NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_activity_start ON activity_log(start_time);
CREATE INDEX IF NOT EXISTS idx_activity_category ON activity_log(category);
CREATE INDEX IF NOT EXISTS idx_activity_app ON activity_log(app_name);
CREATE INDEX IF NOT EXISTS idx_search_timestamp ON search_history(timestamp);
CREATE INDEX IF NOT EXISTS idx_daily_date ON daily_stats(date);
CREATE INDEX IF NOT EXISTS idx_snapshot_timestamp ON process_snapshots(timestamp);
CREATE INDEX IF NOT EXISTS idx_snapshot_app ON process_snapshots(app_name);
CREATE INDEX IF NOT EXISTS idx_app_usage_date ON app_usage_history(date);
CREATE INDEX IF NOT EXISTS idx_app_usage_name ON app_usage_history(app_name);
CREATE INDEX IF NOT EXISTS idx_browser_urls_timestamp ON browser_urls(timestamp);
CREATE INDEX IF NOT EXISTS idx_browser_urls_domain ON browser_urls(domain);
CREATE INDEX IF NOT EXISTS idx_focus_start ON focus_sessions(start_time);
"""

# Migration SQL for existing databases (adds new columns safely)
MIGRATION_SQL = """
-- Add memory/cpu/pid columns to activity_log if they don't exist
-- SQLite doesn't support IF NOT EXISTS for ALTER TABLE, so we use a try/except in code
"""


def init_db():
    """Initialize the database schema. Safe to call multiple times."""
    conn = get_connection()
    conn.executescript(SCHEMA_SQL)

    # Migrate existing activity_log table (add new columns if missing)
    for col, col_type, default in [
        ("memory_mb", "REAL", "0"),
        ("cpu_percent", "REAL", "0"),
        ("pid", "INTEGER", "0"),
    ]:
        try:
            conn.execute(f"ALTER TABLE activity_log ADD COLUMN {col} {col_type} DEFAULT {default}")
        except sqlite3.OperationalError:
            pass  # Column already exists

    conn.commit()


# ── Insert Helpers ─────────────────────────────────────────────────────────

def insert_activity(
    app_name: str,
    window_title: str,
    start_time: datetime,
    end_time: datetime,
    duration_seconds: float,
    category: str = "Other",
    memory_mb: float = 0.0,
    cpu_percent: float = 0.0,
    pid: int = 0,
):
    """Insert an activity record into the log."""
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO activity_log
            (app_name, window_title, start_time, end_time, duration_seconds,
             category, memory_mb, cpu_percent, pid)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            app_name,
            window_title,
            start_time.isoformat(),
            end_time.isoformat(),
            round(duration_seconds, 2),
            category,
            round(memory_mb, 2),
            round(cpu_percent, 2),
            pid,
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


def insert_process_snapshot(
    timestamp: datetime,
    app_name: str,
    pid: int,
    memory_mb: float,
    cpu_percent: float,
    status: str = "running",
    num_threads: int = 0,
):
    """Insert a process snapshot record."""
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO process_snapshots
            (timestamp, app_name, pid, memory_mb, cpu_percent, status, num_threads)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            timestamp.isoformat(),
            app_name,
            pid,
            round(memory_mb, 2),
            round(cpu_percent, 2),
            status,
            num_threads,
        ),
    )
    conn.commit()


def bulk_insert_snapshots(snapshots: list[tuple]):
    """Insert multiple process snapshots at once for efficiency."""
    conn = get_connection()
    conn.executemany(
        """
        INSERT INTO process_snapshots
            (timestamp, app_name, pid, memory_mb, cpu_percent, status, num_threads)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        snapshots,
    )
    conn.commit()


def insert_browser_url(
    timestamp: datetime,
    browser: str,
    url: str,
    title: str = "",
    visit_duration: float = 0.0,
    domain: str = "",
):
    """Insert a browser URL visit record."""
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO browser_urls (timestamp, browser, url, title, visit_duration, domain)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (timestamp.isoformat(), browser, url, title, round(visit_duration, 2), domain),
    )
    conn.commit()


def bulk_insert_browser_urls(urls: list[tuple]):
    """Insert multiple browser URL records at once."""
    conn = get_connection()
    conn.executemany(
        """
        INSERT INTO browser_urls (timestamp, browser, url, title, visit_duration, domain)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        urls,
    )
    conn.commit()


# ── Query Helpers ──────────────────────────────────────────────────────────

def query_activities(
    target_date: Optional[date] = None,
    limit: int = 100,
) -> list[dict]:
    """Fetch activity records for a given date."""
    if target_date is None:
        target_date = date.today()

    conn = get_connection()
    date_prefix = target_date.isoformat()
    cursor = conn.execute(
        """
        SELECT app_name, window_title, start_time, end_time,
               duration_seconds, category, memory_mb, cpu_percent, pid
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
    """Get time spent per application for a given date, with resource averages."""
    if target_date is None:
        target_date = date.today()

    conn = get_connection()
    date_prefix = target_date.isoformat()
    cursor = conn.execute(
        """
        SELECT app_name,
               SUM(duration_seconds) as total_seconds,
               COUNT(*) as switch_count,
               AVG(memory_mb) as avg_memory_mb,
               AVG(cpu_percent) as avg_cpu_percent,
               MAX(memory_mb) as peak_memory_mb
        FROM activity_log
        WHERE start_time LIKE ? || '%'
        GROUP BY app_name
        ORDER BY total_seconds DESC
        """,
        (date_prefix,),
    )
    return [dict(row) for row in cursor.fetchall()]


# ── Deep App Analytics ─────────────────────────────────────────────────────

def get_app_analytics(app_name: str, target_date: Optional[date] = None) -> dict:
    """
    Get deep analytics for a specific application on a specific date.
    Returns total time, memory/CPU stats, window titles, and category.
    """
    if target_date is None:
        target_date = date.today()

    conn = get_connection()
    date_prefix = target_date.isoformat()

    # Aggregate stats
    row = conn.execute(
        """
        SELECT COUNT(*) as session_count,
               SUM(duration_seconds) as total_seconds,
               AVG(memory_mb) as avg_memory_mb,
               MAX(memory_mb) as peak_memory_mb,
               AVG(cpu_percent) as avg_cpu,
               MAX(cpu_percent) as peak_cpu,
               MIN(start_time) as first_seen,
               MAX(end_time) as last_seen,
               category
        FROM activity_log
        WHERE app_name = ? AND start_time LIKE ? || '%'
        """,
        (app_name, date_prefix),
    ).fetchone()

    if not row or row["session_count"] == 0:
        return {}

    # Top window titles
    titles = conn.execute(
        """
        SELECT window_title,
               SUM(duration_seconds) as total_seconds,
               COUNT(*) as count
        FROM activity_log
        WHERE app_name = ? AND start_time LIKE ? || '%'
        GROUP BY window_title
        ORDER BY total_seconds DESC
        LIMIT 15
        """,
        (app_name, date_prefix),
    ).fetchall()

    # Resource snapshots for this app (from process_snapshots)
    snapshots = conn.execute(
        """
        SELECT timestamp, memory_mb, cpu_percent, num_threads
        FROM process_snapshots
        WHERE app_name = ? AND timestamp LIKE ? || '%'
        ORDER BY timestamp ASC
        """,
        (app_name, date_prefix),
    ).fetchall()

    return {
        "app_name": app_name,
        "date": date_prefix,
        "session_count": row["session_count"],
        "total_seconds": row["total_seconds"] or 0,
        "avg_memory_mb": round(row["avg_memory_mb"] or 0, 2),
        "peak_memory_mb": round(row["peak_memory_mb"] or 0, 2),
        "avg_cpu": round(row["avg_cpu"] or 0, 2),
        "peak_cpu": round(row["peak_cpu"] or 0, 2),
        "first_seen": row["first_seen"],
        "last_seen": row["last_seen"],
        "category": row["category"] or "❓ Other",
        "top_titles": [dict(t) for t in titles],
        "resource_timeline": [dict(s) for s in snapshots],
    }


def get_app_history(app_name: str, days: int = 14) -> list[dict]:
    """Get the usage history of an app over multiple days."""
    conn = get_connection()
    cursor = conn.execute(
        """
        SELECT
            SUBSTR(start_time, 1, 10) as date,
            SUM(duration_seconds) as total_seconds,
            COUNT(*) as session_count,
            AVG(memory_mb) as avg_memory_mb,
            AVG(cpu_percent) as avg_cpu
        FROM activity_log
        WHERE app_name = ?
        GROUP BY SUBSTR(start_time, 1, 10)
        ORDER BY date DESC
        LIMIT ?
        """,
        (app_name, days),
    )
    return [dict(row) for row in cursor.fetchall()]


def get_all_tracked_apps() -> list[dict]:
    """Get list of all apps ever tracked with total time."""
    conn = get_connection()
    cursor = conn.execute(
        """
        SELECT app_name,
               SUM(duration_seconds) as total_seconds,
               COUNT(*) as total_sessions,
               AVG(memory_mb) as avg_memory_mb,
               MAX(memory_mb) as peak_memory_mb,
               category
        FROM activity_log
        GROUP BY app_name
        ORDER BY total_seconds DESC
        """,
    )
    return [dict(row) for row in cursor.fetchall()]


# ── System Overview ────────────────────────────────────────────────────────

def get_top_memory_apps(target_date: Optional[date] = None, limit: int = 10) -> list[dict]:
    """Get top memory-consuming apps from snapshots."""
    if target_date is None:
        target_date = date.today()

    conn = get_connection()
    date_prefix = target_date.isoformat()
    cursor = conn.execute(
        """
        SELECT app_name,
               AVG(memory_mb) as avg_memory_mb,
               MAX(memory_mb) as peak_memory_mb,
               COUNT(DISTINCT pid) as instance_count,
               AVG(cpu_percent) as avg_cpu
        FROM process_snapshots
        WHERE timestamp LIKE ? || '%'
        GROUP BY app_name
        ORDER BY avg_memory_mb DESC
        LIMIT ?
        """,
        (date_prefix, limit),
    )
    return [dict(row) for row in cursor.fetchall()]


def get_top_cpu_apps(target_date: Optional[date] = None, limit: int = 10) -> list[dict]:
    """Get top CPU-consuming apps from snapshots."""
    if target_date is None:
        target_date = date.today()

    conn = get_connection()
    date_prefix = target_date.isoformat()
    cursor = conn.execute(
        """
        SELECT app_name,
               AVG(cpu_percent) as avg_cpu,
               MAX(cpu_percent) as peak_cpu,
               AVG(memory_mb) as avg_memory_mb,
               COUNT(DISTINCT pid) as instance_count
        FROM process_snapshots
        WHERE timestamp LIKE ? || '%'
        GROUP BY app_name
        ORDER BY avg_cpu DESC
        LIMIT ?
        """,
        (date_prefix, limit),
    )
    return [dict(row) for row in cursor.fetchall()]


def get_snapshot_count(target_date: Optional[date] = None) -> int:
    """Get number of process snapshots for a date."""
    if target_date is None:
        target_date = date.today()

    conn = get_connection()
    date_prefix = target_date.isoformat()
    row = conn.execute(
        "SELECT COUNT(DISTINCT timestamp) FROM process_snapshots WHERE timestamp LIKE ? || '%'",
        (date_prefix,),
    ).fetchone()
    return row[0] if row else 0


# ── Browser URL Queries ────────────────────────────────────────────────────

def query_browser_urls(
    target_date: Optional[date] = None,
    limit: int = 100,
) -> list[dict]:
    """Fetch browser URL history for a given date."""
    if target_date is None:
        target_date = date.today()

    conn = get_connection()
    date_prefix = target_date.isoformat()
    cursor = conn.execute(
        """
        SELECT timestamp, browser, url, title, visit_duration, domain
        FROM browser_urls
        WHERE timestamp LIKE ? || '%'
        ORDER BY timestamp DESC
        LIMIT ?
        """,
        (date_prefix, limit),
    )
    return [dict(row) for row in cursor.fetchall()]


def get_domain_breakdown(target_date: Optional[date] = None) -> list[dict]:
    """Get time/visit count per domain."""
    if target_date is None:
        target_date = date.today()

    conn = get_connection()
    date_prefix = target_date.isoformat()
    cursor = conn.execute(
        """
        SELECT domain,
               COUNT(*) as visit_count,
               SUM(visit_duration) as total_duration
        FROM browser_urls
        WHERE timestamp LIKE ? || '%' AND domain != ''
        GROUP BY domain
        ORDER BY visit_count DESC
        LIMIT 30
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

    # Session count
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


def upsert_app_usage_history(target_date: Optional[date] = None):
    """Compute and upsert per-app daily aggregates."""
    if target_date is None:
        target_date = date.today()

    conn = get_connection()
    date_prefix = target_date.isoformat()

    apps = conn.execute(
        """
        SELECT app_name,
               SUM(duration_seconds) as total_duration,
               AVG(memory_mb) as avg_mem,
               AVG(cpu_percent) as avg_cpu,
               COUNT(*) as launch_count,
               category
        FROM activity_log
        WHERE start_time LIKE ? || '%'
        GROUP BY app_name
        """,
        (date_prefix,),
    ).fetchall()

    from .categorizer import get_app_role

    for app in apps:
        role = get_app_role(app["app_name"])
        conn.execute(
            """
            INSERT INTO app_usage_history
                (date, app_name, total_duration, total_memory_avg_mb, total_cpu_avg,
                 launch_count, category, role)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(date, app_name) DO UPDATE SET
                total_duration = excluded.total_duration,
                total_memory_avg_mb = excluded.total_memory_avg_mb,
                total_cpu_avg = excluded.total_cpu_avg,
                launch_count = excluded.launch_count,
                category = excluded.category,
                role = excluded.role
            """,
            (
                date_prefix,
                app["app_name"],
                round(app["total_duration"] or 0, 2),
                round(app["avg_mem"] or 0, 2),
                round(app["avg_cpu"] or 0, 2),
                app["launch_count"],
                app["category"] or "❓ Other",
                role,
            ),
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


def get_productivity_heatmap_data(weeks: int = 52) -> list[dict]:
    """
    Fetch daily productivity scores for the heatmap.

    Returns a list of dicts with 'date', 'total_seconds', 'productive_seconds',
    'score' (0-100) for each day in the range.
    """
    conn = get_connection()
    start_date = date.today() - timedelta(days=weeks * 7)
    cursor = conn.execute(
        """
        SELECT date, total_seconds, productive_seconds, distraction_seconds
        FROM daily_stats
        WHERE date >= ?
        ORDER BY date ASC
        """,
        (start_date.isoformat(),),
    )
    results = []
    for row in cursor.fetchall():
        row_dict = dict(row)
        total = row_dict["total_seconds"] or 0
        productive = row_dict["productive_seconds"] or 0
        score = round((productive / total) * 100) if total > 0 else 0
        results.append({
            "date": row_dict["date"],
            "total_seconds": total,
            "productive_seconds": productive,
            "score": score,
        })
    return results


def get_streak_info() -> dict:
    """
    Calculate current and longest productivity streaks.

    A 'streak day' is any day with total_seconds > 0.
    Returns: {'current_streak': int, 'longest_streak': int, 'total_days_tracked': int}
    """
    conn = get_connection()
    cursor = conn.execute(
        """
        SELECT date FROM daily_stats
        WHERE total_seconds > 0
        ORDER BY date ASC
        """
    )
    dates_tracked = [
        date.fromisoformat(row["date"]) for row in cursor.fetchall()
    ]

    if not dates_tracked:
        return {"current_streak": 0, "longest_streak": 0, "total_days_tracked": 0}

    # Calculate longest streak
    longest = 1
    current = 1
    for i in range(1, len(dates_tracked)):
        if (dates_tracked[i] - dates_tracked[i - 1]).days == 1:
            current += 1
            longest = max(longest, current)
        else:
            current = 1

    # Calculate current streak (counting back from today)
    today = date.today()
    current_streak = 0
    check_date = today
    date_set = set(dates_tracked)
    while check_date in date_set:
        current_streak += 1
        check_date -= timedelta(days=1)

    return {
        "current_streak": current_streak,
        "longest_streak": longest,
        "total_days_tracked": len(dates_tracked),
    }


# ── Focus Session Functions ────────────────────────────────────────────────

def insert_focus_session(
    start_time: datetime,
    end_time: datetime,
    target_minutes: int,
    actual_focus_seconds: float,
    interruption_count: int,
    focus_score: float,
    goal_label: str = "",
):
    """Insert a completed focus session."""
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO focus_sessions
            (start_time, end_time, target_minutes, actual_focus_seconds,
             interruption_count, focus_score, goal_label)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            start_time.isoformat(),
            end_time.isoformat(),
            target_minutes,
            actual_focus_seconds,
            interruption_count,
            focus_score,
            goal_label,
        ),
    )
    conn.commit()


def query_focus_sessions(target_date: Optional[date] = None, limit: int = 20) -> list[dict]:
    """Query focus sessions, optionally filtered by date."""
    conn = get_connection()
    if target_date:
        cursor = conn.execute(
            """
            SELECT * FROM focus_sessions
            WHERE date(start_time) = ?
            ORDER BY start_time DESC
            LIMIT ?
            """,
            (target_date.isoformat(), limit),
        )
    else:
        cursor = conn.execute(
            """
            SELECT * FROM focus_sessions
            ORDER BY start_time DESC
            LIMIT ?
            """,
            (limit,),
        )
    return [dict(row) for row in cursor.fetchall()]


def get_focus_stats() -> dict:
    """Get aggregate focus session statistics."""
    conn = get_connection()
    cursor = conn.execute(
        """
        SELECT
            COUNT(*) as total_sessions,
            COALESCE(SUM(actual_focus_seconds), 0) as total_focus_seconds,
            COALESCE(AVG(focus_score), 0) as avg_focus_score,
            COALESCE(SUM(interruption_count), 0) as total_interruptions,
            COALESCE(MAX(focus_score), 0) as best_score
        FROM focus_sessions
        """
    )
    row = cursor.fetchone()
    return dict(row) if row else {
        "total_sessions": 0,
        "total_focus_seconds": 0,
        "avg_focus_score": 0,
        "total_interruptions": 0,
        "best_score": 0,
    }
