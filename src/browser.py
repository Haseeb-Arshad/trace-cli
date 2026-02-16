"""
TraceCLI Browser Search Extraction
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Extracts search queries from Chrome/Edge browser history databases.
Copies the locked DB to a temp file, queries it, and parses search URLs.
"""

import os
import re
import shutil
import sqlite3
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urlparse, parse_qs, unquote_plus


# ── Data Classes ───────────────────────────────────────────────────────────

@dataclass
class SearchResult:
    """A single extracted search query."""
    timestamp: datetime
    browser: str
    query: str
    url: str
    source: str      # Google, Bing, DuckDuckGo, YouTube, etc.


# ── Browser History Paths ──────────────────────────────────────────────────

BROWSER_HISTORY_PATHS = {
    "Chrome": Path(os.environ.get("LOCALAPPDATA", ""))
    / "Google" / "Chrome" / "User Data" / "Default" / "History",

    "Chrome (Profile 1)": Path(os.environ.get("LOCALAPPDATA", ""))
    / "Google" / "Chrome" / "User Data" / "Profile 1" / "History",

    "Edge": Path(os.environ.get("LOCALAPPDATA", ""))
    / "Microsoft" / "Edge" / "User Data" / "Default" / "History",

    "Edge (Profile 1)": Path(os.environ.get("LOCALAPPDATA", ""))
    / "Microsoft" / "Edge" / "User Data" / "Profile 1" / "History",

    "Brave": Path(os.environ.get("LOCALAPPDATA", ""))
    / "BraveSoftware" / "Brave-Browser" / "User Data" / "Default" / "History",

    "Vivaldi": Path(os.environ.get("LOCALAPPDATA", ""))
    / "Vivaldi" / "User Data" / "Default" / "History",
}


def get_available_browsers() -> dict[str, Path]:
    """Return dict of browser_name -> history_path for installed browsers."""
    available = {}
    for name, path in BROWSER_HISTORY_PATHS.items():
        if path.exists():
            available[name] = path
    return available


# ── Search URL Parsers ─────────────────────────────────────────────────────

# Patterns: (domain_regex, query_param, source_name)
SEARCH_ENGINE_PATTERNS = [
    # Google Search
    (re.compile(r"google\.\w+/search"), "q", "Google"),
    # Bing
    (re.compile(r"bing\.com/search"), "q", "Bing"),
    # DuckDuckGo
    (re.compile(r"duckduckgo\.com/"), "q", "DuckDuckGo"),
    # YouTube
    (re.compile(r"youtube\.com/results"), "search_query", "YouTube"),
    # Yahoo
    (re.compile(r"search\.yahoo\.com/search"), "p", "Yahoo"),
    # Ecosia
    (re.compile(r"ecosia\.org/search"), "q", "Ecosia"),
    # Startpage
    (re.compile(r"startpage\.com/search"), "query", "Startpage"),
    # Brave Search
    (re.compile(r"search\.brave\.com/search"), "q", "Brave Search"),
    # GitHub search
    (re.compile(r"github\.com/search"), "q", "GitHub"),
    # Stack Overflow search
    (re.compile(r"stackoverflow\.com/search"), "q", "Stack Overflow"),
    # PyPI search
    (re.compile(r"pypi\.org/search"), "q", "PyPI"),
    # npm search
    (re.compile(r"npmjs\.com/search"), "q", "npm"),
]


def parse_search_query(url: str) -> Optional[tuple[str, str]]:
    """
    Parse a URL to extract a search query.

    Returns:
        (query_text, source_name) or None if not a search URL.
    """
    for pattern, param, source in SEARCH_ENGINE_PATTERNS:
        if pattern.search(url):
            parsed = urlparse(url)
            params = parse_qs(parsed.query)
            if param in params:
                query = unquote_plus(params[param][0])
                # Clean up the query
                query = query.strip()
                if query:
                    return (query, source)
    return None


# ── Chrome Timestamp Conversion ────────────────────────────────────────────

# Chrome stores timestamps as microseconds since 1601-01-01
CHROME_EPOCH = datetime(1601, 1, 1, tzinfo=timezone.utc)


def chrome_time_to_datetime(chrome_timestamp: int) -> datetime:
    """Convert Chrome's microsecond timestamp to a Python datetime."""
    if chrome_timestamp == 0:
        return datetime.now()
    try:
        delta = timedelta(microseconds=chrome_timestamp)
        return (CHROME_EPOCH + delta).replace(tzinfo=None)
    except (OverflowError, OSError):
        return datetime.now()


# ── Main Extraction ────────────────────────────────────────────────────────

def extract_searches(since_minutes: int = 60) -> list[SearchResult]:
    """
    Extract recent search queries from all available browsers.

    Args:
        since_minutes: How far back to look (default: 60 minutes).

    Returns:
        List of SearchResult objects, newest first.
    """
    results: list[SearchResult] = []
    browsers = get_available_browsers()

    for browser_name, history_path in browsers.items():
        try:
            browser_results = _extract_from_browser(
                browser_name, history_path, since_minutes
            )
            results.extend(browser_results)
        except Exception:
            # Browser may be locked or history corrupted — skip silently
            continue

    # Sort by timestamp, newest first
    results.sort(key=lambda r: r.timestamp, reverse=True)

    # Deduplicate by query text (keep most recent)
    seen_queries: set[str] = set()
    unique_results: list[SearchResult] = []
    for result in results:
        query_lower = result.query.lower()
        if query_lower not in seen_queries:
            seen_queries.add(query_lower)
            unique_results.append(result)

    return unique_results


def _extract_from_browser(
    browser_name: str,
    history_path: Path,
    since_minutes: int,
) -> list[SearchResult]:
    """Extract searches from a single browser's history DB."""
    results: list[SearchResult] = []

    # Copy the DB to a temp file (browser locks the original)
    tmp_dir = tempfile.mkdtemp(prefix="tracecli_")
    tmp_db = os.path.join(tmp_dir, "History_copy")

    try:
        shutil.copy2(str(history_path), tmp_db)
    except (PermissionError, OSError):
        return results

    try:
        conn = sqlite3.connect(tmp_db, timeout=5)
        conn.row_factory = sqlite3.Row

        # Calculate the Chrome timestamp for "since_minutes ago"
        now = datetime.now()
        cutoff = now - timedelta(minutes=since_minutes)
        # Convert to Chrome epoch (microseconds since 1601-01-01)
        chrome_cutoff = int(
            (cutoff - datetime(1601, 1, 1)).total_seconds() * 1_000_000
        )

        cursor = conn.execute(
            """
            SELECT url, title, last_visit_time
            FROM urls
            WHERE last_visit_time > ?
            ORDER BY last_visit_time DESC
            LIMIT 500
            """,
            (chrome_cutoff,),
        )

        for row in cursor.fetchall():
            url = row["url"]
            parsed = parse_search_query(url)
            if parsed:
                query, source = parsed
                timestamp = chrome_time_to_datetime(row["last_visit_time"])
                results.append(
                    SearchResult(
                        timestamp=timestamp,
                        browser=browser_name.split(" (")[0],  # Remove profile suffix
                        query=query,
                        url=url,
                        source=source,
                    )
                )

        conn.close()
    except Exception:
        pass
    finally:
        # Clean up temp file
        try:
            os.remove(tmp_db)
            os.rmdir(tmp_dir)
        except OSError:
            pass

    return results


def extract_searches_from_titles(
    window_title: str,
    app_name: str,
) -> Optional[SearchResult]:
    """
    Try to extract a search query from a browser window title.

    Many browsers show "query - Google Search - Browser" in the title bar.
    """
    if app_name.lower() not in {
        "chrome.exe", "msedge.exe", "firefox.exe",
        "brave.exe", "opera.exe", "vivaldi.exe",
    }:
        return None

    # Common title patterns:
    # "python sqlite tutorial - Google Search - Google Chrome"
    # "how to use pywin32 - Search - Bing"
    search_title_patterns = [
        (re.compile(r"^(.+?)\s*[-–—]\s*Google Search", re.IGNORECASE), "Google"),
        (re.compile(r"^(.+?)\s*[-–—]\s*Search\s*[-–—]\s*Bing", re.IGNORECASE), "Bing"),
        (re.compile(r"^(.+?)\s*at DuckDuckGo", re.IGNORECASE), "DuckDuckGo"),
        (re.compile(r"^(.+?)\s*[-–—]\s*YouTube$", re.IGNORECASE), "YouTube"),
    ]

    for pattern, source in search_title_patterns:
        match = pattern.match(window_title)
        if match:
            query = match.group(1).strip()
            if query and len(query) > 2:
                browser_name = app_name.replace(".exe", "").capitalize()
                return SearchResult(
                    timestamp=datetime.now(),
                    browser=browser_name,
                    query=query,
                    url="",  # No URL from title
                    source=source,
                )

    return None
