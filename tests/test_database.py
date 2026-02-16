"""Tests for the database layer."""

import os
import sqlite3
import tempfile
import pytest
from datetime import datetime, date
from unittest.mock import patch
from pathlib import Path

# We need to patch the DB path before importing
_test_dir = tempfile.mkdtemp(prefix="tracecli_test_")
_test_db = os.path.join(_test_dir, "test_trace.db")


@pytest.fixture(autouse=True)
def setup_test_db(monkeypatch):
    """Use a temporary database for each test."""
    import src.database as db

    monkeypatch.setattr(db, "DB_PATH", Path(_test_db))
    monkeypatch.setattr(db, "DATA_DIR", Path(_test_dir))

    # Clear thread-local connection
    if hasattr(db._local, "connection") and db._local.connection:
        db._local.connection.close()
        db._local.connection = None

    # Remove old test db
    if os.path.exists(_test_db):
        os.remove(_test_db)

    db.init_db()
    yield

    # Cleanup
    db.close_connection()
    if os.path.exists(_test_db):
        os.remove(_test_db)


class TestInitDb:
    def test_creates_tables(self):
        from src.database import get_connection

        conn = get_connection()
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        table_names = {row[0] for row in tables}

        assert "activity_log" in table_names
        assert "search_history" in table_names
        assert "daily_stats" in table_names

    def test_idempotent(self):
        from src.database import init_db

        # Should not raise on second call
        init_db()
        init_db()


class TestInsertAndQuery:
    def test_insert_and_query_activity(self):
        from src.database import insert_activity, query_activities

        now = datetime.now()
        insert_activity(
            app_name="code.exe",
            window_title="test.py — VS Code",
            start_time=now,
            end_time=now,
            duration_seconds=120.5,
            category="💻 Development",
        )

        results = query_activities(date.today())
        assert len(results) == 1
        assert results[0]["app_name"] == "code.exe"
        assert results[0]["duration_seconds"] == 120.5
        assert results[0]["category"] == "💻 Development"

    def test_insert_and_query_search(self):
        from src.database import insert_search, query_searches

        now = datetime.now()
        insert_search(
            timestamp=now,
            browser="Chrome",
            query="python sqlite tutorial",
            url="https://google.com/search?q=python+sqlite+tutorial",
            source="Google",
        )

        results = query_searches(date.today())
        assert len(results) == 1
        assert results[0]["query"] == "python sqlite tutorial"
        assert results[0]["source"] == "Google"

    def test_query_empty_date(self):
        from src.database import query_activities

        results = query_activities(date(2000, 1, 1))
        assert len(results) == 0


class TestDailyStats:
    def test_upsert_daily_stats(self):
        from src.database import insert_activity, upsert_daily_stats, get_daily_stats

        now = datetime.now()
        # Insert some activities
        insert_activity("code.exe", "test.py", now, now, 3600, "💻 Development")
        insert_activity("chrome.exe", "YouTube", now, now, 600, "🎮 Distraction")

        upsert_daily_stats(date.today())
        stats = get_daily_stats(date.today())

        assert stats is not None
        assert stats["total_seconds"] == 4200
        assert stats["productive_seconds"] == 3600
        assert stats["distraction_seconds"] == 600
        assert stats["top_app"] == "code.exe"

    def test_upsert_is_idempotent(self):
        from src.database import insert_activity, upsert_daily_stats, get_daily_stats

        now = datetime.now()
        insert_activity("code.exe", "test.py", now, now, 100, "💻 Development")

        upsert_daily_stats(date.today())
        upsert_daily_stats(date.today())  # Should not duplicate

        stats = get_daily_stats(date.today())
        assert stats["total_seconds"] == 100


class TestBreakdowns:
    def test_category_breakdown(self):
        from src.database import insert_activity, get_category_breakdown

        now = datetime.now()
        insert_activity("code.exe", "a", now, now, 100, "💻 Development")
        insert_activity("code.exe", "b", now, now, 200, "💻 Development")
        insert_activity("chrome.exe", "c", now, now, 50, "🌐 Browsing")

        breakdown = get_category_breakdown(date.today())
        assert len(breakdown) == 2

        dev = next(b for b in breakdown if b["category"] == "💻 Development")
        assert dev["total_seconds"] == 300
        assert dev["switch_count"] == 2

    def test_app_breakdown(self):
        from src.database import insert_activity, get_app_breakdown

        now = datetime.now()
        insert_activity("code.exe", "a", now, now, 100, "💻 Development")
        insert_activity("chrome.exe", "b", now, now, 50, "🌐 Browsing")

        breakdown = get_app_breakdown(date.today())
        assert len(breakdown) == 2
        assert breakdown[0]["app_name"] == "code.exe"  # Sorted by total
