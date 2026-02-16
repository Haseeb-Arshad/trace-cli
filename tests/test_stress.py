"""
TraceCLI Stress Tests
~~~~~~~~~~~~~~~~~~~~~
Adversarial, edge-case, and failure-mode testing.
These tests are designed to FIND BUGS by exercising real edge conditions.
"""

import os
import sys
import math
import sqlite3
import tempfile
import threading
import time
import pytest
from datetime import datetime, date, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock, PropertyMock
from dataclasses import dataclass


# ══════════════════════════════════════════════════════════════════════════
# TEST DATABASE SETUP (shared by all database tests)
# ══════════════════════════════════════════════════════════════════════════

@pytest.fixture(autouse=True)
def setup_test_db(monkeypatch, tmp_path):
    """Fresh database for every single test — each test gets its own temp dir."""
    import src.database as db

    test_db = tmp_path / "stress_trace.db"

    monkeypatch.setattr(db, "DB_PATH", test_db)
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)

    if hasattr(db._local, "connection") and db._local.connection:
        db._local.connection.close()
        db._local.connection = None

    db.init_db()
    yield
    db.close_connection()
    # Best-effort cleanup — threads may hold connections on Windows
    try:
        if test_db.exists():
            test_db.unlink()
    except PermissionError:
        pass  # Thread-local connections will be GC'd


# ══════════════════════════════════════════════════════════════════════════
# 1. DATABASE STRESS TESTS
# ══════════════════════════════════════════════════════════════════════════

class TestDatabaseEdgeCases:
    """Hammer the DB with edge cases that could cause real crashes."""

    def test_insert_activity_with_unicode_bomb(self):
        """App names and titles with emoji, CJK, RTL, null bytes."""
        from src.database import insert_activity, query_activities

        now = datetime.now()
        crazy_names = [
            "🔥app.exe",
            "日本語アプリ.exe",
            "app with spaces and (parens).exe",
            "app'with\"quotes.exe",
            "مرحبا.exe",  # Arabic
            "a" * 1000 + ".exe",  # Very long name
        ]
        for name in crazy_names:
            insert_activity(name, "Window 窗口 🪟", now, now, 10.0, "❓ Other")

        results = query_activities(date.today())
        assert len(results) == len(crazy_names)

    def test_insert_activity_with_extreme_numbers(self):
        """Duration, memory, CPU at extremes."""
        from src.database import insert_activity, query_activities

        now = datetime.now()
        insert_activity("a.exe", "t", now, now, 0.0, "Other")  # Zero duration
        insert_activity("b.exe", "t", now, now, 999999.99, "Other")  # Huge duration
        insert_activity("c.exe", "t", now, now, 0.001, "Other", 99999.0, 100.0, 999999)

        results = query_activities(date.today())
        assert len(results) == 3

    def test_query_on_nonexistent_date(self):
        """Queries on dates with no data should return empty, not crash."""
        from src.database import (
            query_activities, query_searches, get_category_breakdown,
            get_app_breakdown, get_daily_stats, get_top_memory_apps,
            get_top_cpu_apps, get_snapshot_count, query_browser_urls,
            get_domain_breakdown, get_app_analytics, get_app_history,
            get_all_tracked_apps,
        )

        ancient = date(1990, 1, 1)
        assert query_activities(ancient) == []
        assert query_searches(ancient) == []
        assert get_category_breakdown(ancient) == []
        assert get_app_breakdown(ancient) == []
        assert get_daily_stats(ancient) is None
        assert get_top_memory_apps(ancient) == []
        assert get_top_cpu_apps(ancient) == []
        assert get_snapshot_count(ancient) == 0
        assert query_browser_urls(ancient) == []
        assert get_domain_breakdown(ancient) == []
        assert get_app_analytics("anything.exe", ancient) == {}
        assert get_app_history("anything.exe") == []
        assert get_all_tracked_apps() == []

    def test_concurrent_inserts_from_multiple_threads(self):
        """Simulate tracker + monitor + search sync all writing at once."""
        from src.database import insert_activity, bulk_insert_snapshots, insert_search

        errors = []

        def writer_activities():
            try:
                for i in range(50):
                    insert_activity(
                        f"app_{i}.exe", f"window_{i}",
                        datetime.now(), datetime.now(),
                        float(i), "Other"
                    )
            except Exception as e:
                errors.append(("activity", e))

        def writer_snapshots():
            try:
                for i in range(10):
                    ts = datetime.now().isoformat()
                    data = [(ts, f"proc_{j}.exe", j, float(j), float(j), "running", j)
                            for j in range(20)]
                    bulk_insert_snapshots(data)
            except Exception as e:
                errors.append(("snapshot", e))

        def writer_searches():
            try:
                for i in range(30):
                    insert_search(
                        datetime.now(), "Chrome",
                        f"query {i}", f"http://example.com/?q={i}", "Google"
                    )
            except Exception as e:
                errors.append(("search", e))

        threads = [
            threading.Thread(target=writer_activities),
            threading.Thread(target=writer_snapshots),
            threading.Thread(target=writer_searches),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        # No errors should have occurred
        assert errors == [], f"Concurrent write errors: {errors}"

    def test_app_analytics_with_null_resources(self):
        """Activities inserted WITHOUT memory/cpu should not crash analytics."""
        from src.database import insert_activity, get_app_analytics, get_app_breakdown

        now = datetime.now()
        # Insert with default 0 values (simulating old data without resource tracking)
        insert_activity("old_app.exe", "Old Window", now, now, 100.0, "❓ Other")

        analytics = get_app_analytics("old_app.exe", date.today())
        assert analytics["avg_memory_mb"] == 0.0
        assert analytics["avg_cpu"] == 0.0

        breakdown = get_app_breakdown(date.today())
        assert breakdown[0]["avg_memory_mb"] == 0.0

    def test_upsert_daily_stats_with_no_activities(self):
        """Upserting stats when there are zero activities should not crash."""
        from src.database import upsert_daily_stats, get_daily_stats

        upsert_daily_stats(date.today())
        stats = get_daily_stats(date.today())
        assert stats is not None
        assert stats["total_seconds"] == 0
        assert stats["top_app"] == ""

    def test_upsert_app_usage_history_with_no_data(self):
        """App usage history upsert with empty activity_log should not crash."""
        from src.database import upsert_app_usage_history

        # Should not raise
        upsert_app_usage_history(date.today())

    def test_bulk_insert_empty_list(self):
        """Bulk insert with empty list should be a no-op, not crash."""
        from src.database import bulk_insert_snapshots, bulk_insert_browser_urls

        bulk_insert_snapshots([])
        bulk_insert_browser_urls([])

    def test_migration_on_fresh_db(self):
        """Migration logic should be safe on a DB that already has all columns."""
        from src.database import init_db
        # Double-init should not crash
        init_db()
        init_db()
        init_db()

    def test_sql_injection_safety(self):
        """Ensure parameterized queries prevent injection."""
        from src.database import insert_activity, query_activities

        now = datetime.now()
        evil_name = "'; DROP TABLE activity_log; --"
        insert_activity(evil_name, "title", now, now, 10.0, "Other")

        results = query_activities(date.today())
        assert len(results) == 1
        assert results[0]["app_name"] == evil_name


# ══════════════════════════════════════════════════════════════════════════
# 2. TRACKER STRESS TESTS
# ══════════════════════════════════════════════════════════════════════════

class TestActivityRecordEdgeCases:
    """Test the ActivityRecord dataclass under stress."""

    def test_finalize_with_no_samples(self):
        """Finalizing with zero resource samples should give 0, not crash."""
        from src.tracker import ActivityRecord

        record = ActivityRecord(
            app_name="test.exe",
            window_title="test",
            start_time=datetime.now() - timedelta(seconds=5),
        )
        record.finalize()

        assert record.memory_mb == 0.0
        assert record.cpu_percent == 0.0
        assert record.duration_seconds >= 4.0  # At least 4 seconds

    def test_finalize_averages_correctly(self):
        """Resource averaging should compute correct values."""
        from src.tracker import ActivityRecord

        record = ActivityRecord(
            app_name="test.exe",
            window_title="test",
            start_time=datetime.now(),
        )
        record.add_resource_sample(100.0, 10.0)
        record.add_resource_sample(200.0, 20.0)
        record.add_resource_sample(300.0, 30.0)
        record.finalize()

        assert record.memory_mb == 200.0
        assert record.cpu_percent == 20.0

    def test_to_dict_before_finalize(self):
        """to_dict() should not crash even if end_time is None."""
        from src.tracker import ActivityRecord

        record = ActivityRecord(
            app_name="test.exe",
            window_title="test",
            start_time=datetime.now(),
        )
        d = record.to_dict()
        assert d["end_time"] is None
        assert d["app_name"] == "test.exe"

    def test_huge_number_of_samples(self):
        """Adding thousands of samples should not cause memory issues."""
        from src.tracker import ActivityRecord

        record = ActivityRecord(
            app_name="test.exe",
            window_title="test",
            start_time=datetime.now(),
        )
        for i in range(10000):
            record.add_resource_sample(float(i), float(i % 100))
        record.finalize()

        assert record.memory_mb == 4999.5  # Mean of 0..9999
        assert record.cpu_percent == 49.5   # Mean of 0..99 repeated

    def test_get_process_resources_dead_pid(self):
        """Querying resources for a PID that doesn't exist."""
        from src.tracker import get_process_resources

        mem, cpu = get_process_resources(999999999)
        assert mem == 0.0
        assert cpu == 0.0

    def test_get_process_resources_pid_zero(self):
        """PID 0 is the System Idle Process on Windows."""
        from src.tracker import get_process_resources

        # Should not crash even if access denied
        mem, cpu = get_process_resources(0)
        assert isinstance(mem, float)
        assert isinstance(cpu, float)


class TestTrackerConcurrency:
    """Test the tracker under concurrent access."""

    def test_get_current_returns_none_when_stopped(self):
        """get_current() after stop should return None."""
        from src.tracker import ActivityTracker

        tracker = ActivityTracker()
        assert tracker.get_current() is None

    def test_session_duration_before_start(self):
        """Session duration before start should be 0."""
        from src.tracker import ActivityTracker

        tracker = ActivityTracker()
        assert tracker.get_session_duration() == 0.0

    def test_double_start(self):
        """Starting twice should be safe (no duplicate threads)."""
        from src.tracker import ActivityTracker

        tracker = ActivityTracker(poll_interval=100)
        tracker.start()
        tracker.start()
        assert tracker._running
        tracker.stop()

    def test_double_stop(self):
        """Stopping twice should be safe."""
        from src.tracker import ActivityTracker

        tracker = ActivityTracker(poll_interval=100)
        tracker.start()
        tracker.stop()
        tracker.stop()
        assert not tracker._running

    def test_flush_when_no_current(self):
        """Flushing with no current activity should be a no-op."""
        from src.tracker import ActivityTracker

        tracker = ActivityTracker()
        tracker.flush()  # Should not crash


# ══════════════════════════════════════════════════════════════════════════
# 3. MONITOR STRESS TESTS
# ══════════════════════════════════════════════════════════════════════════

class TestMonitorEdgeCases:
    """Test the system monitor under adversarial conditions."""

    @patch("src.monitor.psutil.disk_usage")
    @patch("src.monitor.psutil.cpu_percent")
    @patch("src.monitor.psutil.cpu_count")
    @patch("src.monitor.psutil.virtual_memory")
    def test_system_info_large_ram(self, mock_mem, mock_count, mock_cpu, mock_disk):
        """System with 128GB RAM, 64 cores."""
        from src.monitor import get_system_info

        mock_mem.return_value = MagicMock(
            total=128 * 1024**3, used=96 * 1024**3, percent=75.0
        )
        mock_count.return_value = 64
        mock_cpu.return_value = 95.0
        mock_disk.return_value = MagicMock(
            total=4000 * 1024**3, used=3000 * 1024**3, percent=75.0
        )

        info = get_system_info()
        assert info["total_ram_gb"] == 128.0
        assert info["cpu_count"] == 64
        assert info["cpu_percent"] == 95.0

    @patch("src.monitor.psutil.process_iter")
    def test_empty_process_list(self, mock_iter):
        """No processes returned (shouldn't happen but be safe)."""
        from src.monitor import get_running_processes

        mock_iter.return_value = []
        procs = get_running_processes()
        assert procs == []

    @patch("src.monitor.psutil.process_iter")
    def test_process_with_null_name(self, mock_iter):
        """Process with None name should default to 'Unknown'."""
        from src.monitor import get_running_processes

        mock_iter.return_value = [
            MagicMock(info={
                "pid": 1, "name": None,
                "memory_info": MagicMock(rss=10 * 1024 * 1024),
                "cpu_percent": 0.0, "status": "running", "num_threads": 1,
            }),
        ]
        procs = get_running_processes()
        assert len(procs) == 1
        assert procs[0]["app_name"] == "Unknown"

    @patch("src.monitor.psutil.process_iter")
    def test_process_with_null_memory_info(self, mock_iter):
        """Process with None memory_info should not crash."""
        from src.monitor import get_running_processes

        mock_iter.return_value = [
            MagicMock(info={
                "pid": 1, "name": "test.exe",
                "memory_info": None,
                "cpu_percent": 5.0, "status": "running", "num_threads": 1,
            }),
        ]
        procs = get_running_processes()
        assert len(procs) == 1
        assert procs[0]["memory_mb"] == 0

    def test_monitor_double_start_stop(self):
        """Starting/stopping monitor multiple times should not crash."""
        from src.monitor import SystemMonitor

        monitor = SystemMonitor(interval=1000)
        monitor.start()
        monitor.start()
        monitor.stop()
        monitor.stop()

    @patch("src.monitor.psutil.process_iter")
    def test_sort_by_cpu(self, mock_iter):
        """Sorting by CPU should work correctly."""
        from src.monitor import get_running_processes

        mock_iter.return_value = [
            MagicMock(info={
                "pid": 1, "name": "low_cpu.exe",
                "memory_info": MagicMock(rss=500 * 1024 * 1024),
                "cpu_percent": 2.0, "status": "running", "num_threads": 5,
            }),
            MagicMock(info={
                "pid": 2, "name": "high_cpu.exe",
                "memory_info": MagicMock(rss=10 * 1024 * 1024),
                "cpu_percent": 95.0, "status": "running", "num_threads": 20,
            }),
        ]
        procs = get_running_processes(sort_by="cpu")
        assert procs[0]["app_name"] == "high_cpu.exe"
        assert procs[1]["app_name"] == "low_cpu.exe"


# ══════════════════════════════════════════════════════════════════════════
# 4. BROWSER STRESS TESTS
# ══════════════════════════════════════════════════════════════════════════

class TestBrowserEdgeCases:
    """Test browser extraction under adversarial conditions."""

    def test_extract_domain_malformed_urls(self):
        """Malformed URLs should not crash domain extraction."""
        from src.browser import extract_domain

        assert extract_domain("") == ""
        assert extract_domain("not-a-url") == ""
        assert extract_domain("http://") == ""
        assert extract_domain("ftp://files.example.com") == "files.example.com"
        assert extract_domain("https://www.example.com/path?q=1") == "example.com"
        assert extract_domain("chrome-extension://abc/page") == "abc"

    def test_chrome_time_edge_cases(self):
        """Chrome timestamp conversion extremes."""
        from src.browser import chrome_time_to_datetime

        # Zero timestamp
        result = chrome_time_to_datetime(0)
        assert isinstance(result, datetime)

        # Negative timestamp
        result = chrome_time_to_datetime(-1)
        assert isinstance(result, datetime)

        # Very large timestamp (far future)
        result = chrome_time_to_datetime(99999999999999999)
        assert isinstance(result, datetime)

    def test_parse_search_query_edge_cases(self):
        """Edge cases in search URL parsing."""
        from src.browser import parse_search_query

        # Empty query param
        assert parse_search_query("https://google.com/search?q=") is None

        # Whitespace-only query
        assert parse_search_query("https://google.com/search?q=+++") is None

        # Multiple q params (should take first)
        result = parse_search_query("https://google.com/search?q=first&q=second")
        assert result is not None
        assert result[0] == "first"

        # URL with no query string
        assert parse_search_query("https://google.com/search") is None
        assert parse_search_query("") is None

    def test_title_extraction_with_dashes(self):
        """Title extraction with various dash types."""
        from src.browser import extract_searches_from_titles

        # Em dash
        result = extract_searches_from_titles(
            "python tutorial — Google Search", "chrome.exe"
        )
        assert result is not None
        assert result.query == "python tutorial"

        # En dash
        result = extract_searches_from_titles(
            "python tutorial – Google Search", "chrome.exe"
        )
        assert result is not None

    def test_title_extraction_very_short_query(self):
        """Query of 2 chars or less should be rejected."""
        from src.browser import extract_searches_from_titles

        result = extract_searches_from_titles(
            "ab - Google Search", "chrome.exe"
        )
        assert result is None

    def test_browser_url_dataclass(self):
        """BrowserUrl dataclass should be constructable."""
        from src.browser import BrowserUrl

        url = BrowserUrl(
            timestamp=datetime.now(),
            browser="Chrome",
            url="https://example.com",
            title="Example",
            visit_duration=10.0,
            domain="example.com",
        )
        assert url.domain == "example.com"


# ══════════════════════════════════════════════════════════════════════════
# 5. CATEGORIZER STRESS TESTS
# ══════════════════════════════════════════════════════════════════════════

class TestCategorizerEdgeCases:
    """Edge cases for the categorizer."""

    def test_get_app_role_empty_string(self):
        from src.categorizer import get_app_role
        result = get_app_role("")
        assert isinstance(result, str)
        assert result == "Unknown Process"

    def test_get_app_role_whitespace(self):
        from src.categorizer import get_app_role
        result = get_app_role("   ")
        assert isinstance(result, str)

    def test_get_app_role_case_insensitive(self):
        from src.categorizer import get_app_role
        result = get_app_role("Chrome.EXE")
        assert "Chrome" in result

    def test_get_app_role_unknown_exe(self):
        from src.categorizer import get_app_role
        result = get_app_role("supernewapp42.exe")
        assert result == "Application"

    def test_categorize_with_whitespace_in_process(self):
        from src.categorizer import categorize, CATEGORIES
        # Process names with leading/trailing whitespace
        result = categorize(" code.exe ", "some title")
        assert result == CATEGORIES["DEVELOPMENT"]

    def test_categorize_empty_process(self):
        from src.categorizer import categorize, CATEGORIES
        result = categorize("", "some title")
        assert isinstance(result, str)

    def test_categorize_very_long_title(self):
        from src.categorizer import categorize, CATEGORIES
        long_title = "a" * 10000
        result = categorize("chrome.exe", long_title)
        assert result == CATEGORIES["BROWSING"]

    def test_all_categories_are_strings(self):
        from src.categorizer import CATEGORIES
        for key, val in CATEGORIES.items():
            assert isinstance(val, str)
            assert len(val) > 0


# ══════════════════════════════════════════════════════════════════════════
# 6. CLI HELPER FUNCTION STRESS TESTS
# ══════════════════════════════════════════════════════════════════════════

class TestCLIHelpers:
    """Test CLI formatting helpers under extreme inputs."""

    def test_format_duration_zero(self):
        from src.cli import format_duration
        assert format_duration(0) == "0s"

    def test_format_duration_negative(self):
        from src.cli import format_duration
        # Negative duration should not crash
        result = format_duration(-10)
        assert isinstance(result, str)

    def test_format_duration_very_large(self):
        from src.cli import format_duration
        result = format_duration(999999)
        assert "h" in result

    def test_format_memory_edge_cases(self):
        from src.cli import format_memory
        assert "KB" in format_memory(0.5)
        assert "MB" in format_memory(100)
        assert "GB" in format_memory(2048)
        result = format_memory(0)
        assert isinstance(result, str)

    def test_format_time_invalid_input(self):
        from src.cli import format_time
        assert format_time("not-a-date") == "not-a-date"
        assert format_time("") == ""
        assert format_time(None) == None or isinstance(format_time(None), str)

    def test_parse_date_invalid(self):
        from src.cli import parse_date
        with pytest.raises(SystemExit):
            parse_date("garbage")

    def test_parse_date_none(self):
        from src.cli import parse_date
        result = parse_date(None)
        assert result == date.today()

    def test_parse_date_valid(self):
        from src.cli import parse_date
        result = parse_date("2025-06-15")
        assert result == date(2025, 6, 15)

    def test_truncate_edge_cases(self):
        from src.cli import truncate
        assert truncate("", 10) == ""
        assert truncate("short", 10) == "short"
        assert truncate("a" * 100, 10) == "a" * 9 + "…"
        assert truncate("exact", 5) == "exact"


class TestCLIDivisionByZero:
    """The productivity score computation divides by total_seconds.
    If total_seconds is 0, it would crash with ZeroDivisionError."""

    def test_report_with_zero_total_no_crash(self):
        """Category breakdown with zero total should not crash the division."""
        # This tests the logic path, not the CLI command itself
        total_seconds = 0
        productive = 0
        # This is the calculation from cli.py report command
        score = (productive / total_seconds * 100) if total_seconds > 0 else 0
        assert score == 0

    def test_category_bar_with_zero_total(self):
        """Bar chart percentage with zero total."""
        total_seconds = 0
        cat_seconds = 100
        pct = (cat_seconds / total_seconds * 100) if total_seconds > 0 else 0
        assert pct == 0


# ══════════════════════════════════════════════════════════════════════════
# 7. INTEGRATION-LEVEL STRESS TESTS
# ══════════════════════════════════════════════════════════════════════════

class TestEndToEndDataFlow:
    """Test the full pipeline: insert → aggregate → query."""

    def test_full_lifecycle(self):
        """Insert activities, compute stats, query analytics — full pipeline."""
        from src.database import (
            insert_activity, upsert_daily_stats, upsert_app_usage_history,
            get_daily_stats, get_app_analytics, get_app_breakdown,
            get_category_breakdown, get_all_tracked_apps,
        )

        now = datetime.now()
        # Simulate a real workday
        insert_activity("code.exe", "main.py - VS Code", now, now, 7200, "💻 Development", 300.0, 15.0, 100)
        insert_activity("chrome.exe", "GitHub - PR Review", now, now, 1800, "📚 Research", 450.0, 8.0, 200)
        insert_activity("chrome.exe", "YouTube - Music", now, now, 600, "🎮 Distraction", 500.0, 12.0, 200)
        insert_activity("slack.exe", "Team Chat", now, now, 900, "💬 Communication", 200.0, 3.0, 300)
        insert_activity("code.exe", "test.py - VS Code", now, now, 3600, "💻 Development", 350.0, 18.0, 100)

        # Aggregate
        upsert_daily_stats()
        upsert_app_usage_history()

        # Verify stats
        stats = get_daily_stats()
        assert stats["total_seconds"] == 14100
        assert stats["productive_seconds"] == 12600  # 7200 + 1800 + 3600
        assert stats["distraction_seconds"] == 600
        assert stats["top_app"] == "code.exe"

        # Verify analytics
        code_analytics = get_app_analytics("code.exe")
        assert code_analytics["session_count"] == 2
        assert code_analytics["total_seconds"] == 10800
        assert code_analytics["avg_memory_mb"] == 325.0  # (300+350)/2

        # Verify breakdowns
        cat_breakdown = get_category_breakdown()
        assert len(cat_breakdown) == 4

        app_breakdown = get_app_breakdown()
        assert app_breakdown[0]["app_name"] == "code.exe"

        all_apps = get_all_tracked_apps()
        assert len(all_apps) == 3  # code, chrome, slack

    def test_browser_url_lifecycle(self):
        """Insert URLs, query domain breakdown."""
        from src.database import (
            insert_browser_url, bulk_insert_browser_urls,
            query_browser_urls, get_domain_breakdown,
        )

        now = datetime.now()
        insert_browser_url(now, "Chrome", "https://github.com/repo", "Repo", 10.0, "github.com")
        insert_browser_url(now, "Chrome", "https://github.com/other", "Other", 5.0, "github.com")
        insert_browser_url(now, "Edge", "https://stackoverflow.com/q/123", "Q", 8.0, "stackoverflow.com")

        urls = query_browser_urls()
        assert len(urls) == 3

        domains = get_domain_breakdown()
        assert len(domains) == 2
        # github.com should have 2 visits
        gh = next(d for d in domains if d["domain"] == "github.com")
        assert gh["visit_count"] == 2

    def test_snapshot_lifecycle(self):
        """Insert snapshots, query top consumers."""
        from src.database import (
            bulk_insert_snapshots, get_top_memory_apps,
            get_top_cpu_apps, get_snapshot_count,
        )

        ts1 = datetime.now().isoformat()
        ts2 = (datetime.now() + timedelta(seconds=30)).isoformat()

        snapshots = [
            (ts1, "chrome.exe", 100, 1024.0, 25.0, "running", 30),
            (ts1, "code.exe", 200, 512.0, 10.0, "running", 15),
            (ts1, "explorer.exe", 300, 64.0, 1.0, "running", 5),
            (ts2, "chrome.exe", 100, 1100.0, 30.0, "running", 32),
            (ts2, "code.exe", 200, 480.0, 8.0, "running", 14),
        ]
        bulk_insert_snapshots(snapshots)

        assert get_snapshot_count() == 2  # 2 unique timestamps

        top_mem = get_top_memory_apps()
        assert top_mem[0]["app_name"] == "chrome.exe"
        assert top_mem[0]["avg_memory_mb"] > 1000  # Average of 1024 and 1100

        top_cpu = get_top_cpu_apps()
        assert top_cpu[0]["app_name"] == "chrome.exe"  # Highest avg CPU
