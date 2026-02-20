"""
TraceCLI AI Agent
~~~~~~~~~~~~~~~~~
Zero-dependency AI integration using urllib.
Handles Text-to-SQL generation and natural language summarization.
"""

import json
import sqlite3
import urllib.request
import urllib.error
import time
from datetime import date
from typing import Optional, Dict, Any, List

from rich.console import Console
from rich.panel import Panel
from rich.live import Live
from rich.text import Text
from rich.spinner import Spinner
from rich import box

from . import config
from .database import get_connection, DB_PATH

console = Console()

# ── API Clients ────────────────────────────────────────────────────────────

def _post_json(url: str, headers: Dict[str, str], data: Dict[str, Any]) -> Dict:
    """Helper to send JSON POST request using standard library (with retries)."""
    import time
    
    max_retries = 3
    backoff = 1  # seconds

    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(data).encode("utf-8"),
                headers=headers,
                method="POST"
            )
            with urllib.request.urlopen(req) as response:
                return json.load(response)
        except urllib.error.HTTPError as e:
            if e.code == 429:
                if attempt < max_retries - 1:
                    console.print(f"[yellow]Rate limited (429). Retrying in {backoff}s...[/yellow]")
                    time.sleep(backoff)
                    backoff *= 2
                    continue
            
            try:
                err_body = e.read().decode()
                console.print(f"[red]API Error {e.code}: {err_body}[/red]")
            except Exception:
                console.print(f"[red]API Error: {e}[/red]")
            return {}
        except Exception as e:
            console.print(f"[red]Network Error: {e}[/red]")
            return {}
    return {}


def call_gemini(api_key: str, prompt: str, model: str = ""):
    """Call Google Gemini API."""
    model = model or "gemini-flash-latest"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}
    data = {
        "contents": [{"parts": [{"text": prompt}]}]
    }
    
    resp = _post_json(url, headers, data)
    try:
        return resp["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError):
        return None


def call_openai(api_key: str, prompt: str, model: str = ""):
    """Call OpenAI API."""
    model = model or "gpt-3.5-turbo"
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    data = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0
    }
    
    resp = _post_json(url, headers, data)
    try:
        return resp["choices"][0]["message"]["content"]
    except (KeyError, IndexError):
        return None


def call_claude(api_key: str, prompt: str, model: str = ""):
    """Call Anthropic Claude API."""
    model = model or "claude-3-haiku-20240307"
    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }
    data = {
        "model": model,
        "max_tokens": 1024,
        "messages": [{"role": "user", "content": prompt}]
    }
    
    resp = _post_json(url, headers, data)
    try:
        return resp["content"][0]["text"]
    except (KeyError, IndexError):
        return None


def ask_llm(provider: str, api_key: str, prompt: str, model: str = "") -> Optional[str]:
    """Dispatch to the configured provider."""
    provider = provider.lower()
    if provider == "gemini":
        return call_gemini(api_key, prompt, model)
    elif provider == "openai":
        return call_openai(api_key, prompt, model)
    elif provider == "claude":
        return call_claude(api_key, prompt, model)
    else:
        console.print(f"[red]Unknown provider: {provider}[/red]")
        return None


# ── Text-to-SQL Logic ──────────────────────────────────────────────────────

def get_schema_summary() -> str:
    """Get a summary of the database schema for the LLM."""
    conn = get_connection()
    cursor = conn.cursor()
    
    schema = []
    tables = ["activity_log", "daily_stats", "process_snapshots", "browser_urls", "search_history"]
    
    for table in tables:
        cursor.execute(f"PRAGMA table_info({table})")
        cols = [f"{row['name']} ({row['type']})" for row in cursor.fetchall()]
        schema.append(f"Table {table}: " + ", ".join(cols))
        
    return "\n".join(schema)


VALID_CATEGORIES = [
    "💻 Development", "🌐 Browsing", "📚 Research", "💬 Communication",
    "📝 Productivity", "🎮 Distraction", "❓ Other"
]


def generate_sql(question: str, provider: str, api_key: str, model: str) -> Optional[str]:
    """Ask LLM to generate SQL."""
    schema = get_schema_summary()
    today = date.today().isoformat()
    
    prompt = f"""
    You are a SQLite expert. Given the database schema below, write a single SQL query to answer the user's question.
    
    Current Date: {today}
    Schema:
    {schema}
    
    Rules:
    1. Return ONLY the SQL query. No markdown, no explanations.
    2. Use safe localized time comparison: `start_time LIKE '2023-01-01%'` or `timestamp LIKE '2023-01-01%'`.
    3. Calculate durations in minutes if relevant (duration_seconds / 60 or visit_duration / 60).
    4. Only use SELECT statements.
    
    Data Quirks:
    - `category` column uses these exact strings: {VALID_CATEGORIES}
    - If user asks for "Entertainment", "Social", or "Chat", look for keywords in `app_name` OR include `category = '❓ Other'` to find uncategorized apps.
    - `search_history` entries with `url = ''` are captured from browser titles.
    - To join `search_history` with `browser_urls` for productivity time, use:
      `ON s.url = b.url OR (s.url = '' AND b.title LIKE '%' || s.query || '%')`
    
    Question: {question}
    SQL:
    """
    
    response = ask_llm(provider, api_key, prompt, model)
    if not response:
        return None
        
    # Clean up response (remove markdown if any)
    sql = response.strip()
    if sql.startswith("```"):
        sql = sql.split("\n", 1)[1]
    if sql.endswith("```"):
        sql = sql.rsplit("\n", 1)[0]
    return sql.strip()


def summarize_result(question: str, sql: str, rows: list, provider: str, api_key: str, model: str) -> str:
    """Ask LLM to summarize the SQL result."""
    # Truncate rows if too large
    data_str = str(rows[:20])
    if len(rows) > 20:
        data_str += f"... (+{len(rows)-20} more rows)"
        
    prompt = f"""
    You are a helpful assistant analyzing activity data.
    User Question: "{question}"
    SQL Query Run: "{sql}"
    Result Data: {data_str}
    
    You are a helpful assistant analyzing activity data.
    User Question: "{question}"
    SQL Query Run: "{sql}"
    Result Data: {data_str}
    
    Provide a concise, friendly answer based on the data.
    - If you see apps with `category='❓ Other'`, analyze their `app_name` or `window_title`. If they look like games, social media, or entertainment, point them out as potential distractions.
    - If the data is empty, say so politely.
    Answer:
    """
    
    return ask_llm(provider, api_key, prompt, model) or "Error generating summary."


def handle_ask(question: str):
    """Main entry point for 'tracecli ask' with cool animations."""
    provider, api_key, model = config.get_ai_config()
    
    if not api_key:
        console.print("[yellow]⚠️  AI API Key not configured.[/yellow]")
        console.print(f"Run [bold]tracecli config --key YOUR_KEY[/bold] to set it up.")
        return

    # Cool animation sequence
    ai_status_msgs = [
        "Consulting the neural networks...",
        "Searching your digital history...",
        "Aggregating activity patterns...",
        "Synthesizing insights...",
        "Finalizing the answer..."
    ]
    
    with Live(refresh_per_second=10) as live:
        def update_status(msg, spinner="dots"):
            panel = Panel(
                Text.from_markup(f"[bold bright_cyan]{msg}[/bold bright_cyan]"),
                title="🤖 [bold]Trace AI[/bold]",
                border_style="bright_blue",
                box=box.ROUNDED,
                expand=False
            )
            live.update(panel)

        # 1. Start thinking
        update_status(ai_status_msgs[0])
        
        # 2. Generate SQL (Internal)
        sql = generate_sql(question, provider, api_key, model)
        if not sql:
            live.stop()
            console.print("[red]Failed to generate SQL query.[/red]")
            return
            
        # Safety Check
        if not sql.upper().startswith("SELECT"):
            live.stop()
            console.print("[red]Safety Violation: Generated SQL is not a SELECT statement.[/red]")
            return
            
        update_status(ai_status_msgs[1])
        time.sleep(0.5)
        
        # 3. Execute SQL (Internal)
        try:
            conn = get_connection()
            cursor = conn.execute(sql)
            cols = [description[0] for description in cursor.description]
            rows = [dict(zip(cols, row)) for row in cursor.fetchall()]
        except Exception as e:
            live.stop()
            console.print(f"[red]SQL Error: {e}[/red]")
            return

        if not rows:
            live.stop()
            console.print("\n[yellow]No data found matching your query.[/yellow]\n")
            return

        update_status(ai_status_msgs[2])
        time.sleep(0.5)

        # 4. Summarize (Internal)
        update_status(ai_status_msgs[3])
        answer = summarize_result(question, sql, rows, provider, api_key, model)
        
        update_status(ai_status_msgs[4])
        time.sleep(0.3)
    
    # Final Presentation
    console.print()
    console.print(Panel(
        answer,
        title="🤖 [bold bright_white]AI Answer[/bold bright_white]",
        subtitle=f"[dim]Powered by {provider.capitalize()}[/dim]",
        border_style="bright_cyan",
        padding=(1, 2),
        box=box.DOUBLE_EDGE
    ))
    console.print()


# ── Weekly Productivity Digest ─────────────────────────────────────────────

def generate_weekly_digest(days: int = 7) -> Optional[str]:
    """
    Generate an AI-powered productivity digest for the past N days.

    Collects daily stats, app usage, and search patterns, then asks
    the LLM to generate a personalized productivity coaching report.
    """
    provider, api_key, model = config.get_ai_config()
    if not api_key:
        return None

    from .database import (
        get_stats_range, get_category_breakdown, get_app_breakdown,
        get_focus_stats, query_searches,
    )
    from datetime import date, timedelta

    # Gather data
    stats = get_stats_range(days)
    today = date.today()

    if not stats:
        return "No activity data found for the past week."

    # Build structured summary
    total_seconds = sum(s["total_seconds"] for s in stats)
    productive_seconds = sum(s["productive_seconds"] for s in stats)
    distraction_seconds = sum(s["distraction_seconds"] for s in stats)

    # App breakdown for latest day
    app_breakdown = get_app_breakdown(today)
    top_apps = [
        {"app": a["app_name"], "time_hours": round(a["total_seconds"] / 3600, 1)}
        for a in app_breakdown[:5]
    ]

    # Category breakdown for latest day
    cat_breakdown = get_category_breakdown(today)
    categories = [
        {"category": c["category"], "time_hours": round(c["total_seconds"] / 3600, 1)}
        for c in cat_breakdown
    ]

    # Focus stats
    focus = get_focus_stats()

    # Search patterns
    searches = query_searches(today)
    recent_queries = [s["query"] for s in searches[:10]]

    summary = {
        "period_days": days,
        "total_tracked_hours": round(total_seconds / 3600, 1),
        "productive_hours": round(productive_seconds / 3600, 1),
        "distraction_hours": round(distraction_seconds / 3600, 1),
        "productivity_score": round((productive_seconds / total_seconds) * 100) if total_seconds > 0 else 0,
        "days_tracked": len(stats),
        "daily_breakdown": [
            {
                "date": s["date"],
                "hours": round(s["total_seconds"] / 3600, 1),
                "productive_hours": round(s["productive_seconds"] / 3600, 1),
                "score": round((s["productive_seconds"] / s["total_seconds"]) * 100) if s["total_seconds"] > 0 else 0,
            }
            for s in stats
        ],
        "top_apps": top_apps,
        "categories": categories,
        "focus_sessions": focus.get("total_sessions", 0),
        "avg_focus_score": round(focus.get("avg_focus_score", 0), 1),
        "recent_searches": recent_queries,
    }

    prompt = f"""You are a friendly, insightful productivity coach analyzing someone's computer usage data.

Here is their activity summary for the past {days} days:
{json.dumps(summary, indent=2)}

Generate a concise, personalized productivity digest with these sections:
1. 🏆 **Top Achievement** — Highlight their best metric or pattern (be specific with numbers)
2. ⚠️ **Biggest Distraction Pattern** — Identify when/where they get distracted most
3. 💡 **Actionable Suggestion** — One specific, practical tip to improve tomorrow
4. 📊 **Week-over-Week** — Comment on trends if multiple days of data exist

Keep each section to 1-2 sentences. Be encouraging but honest.
Use emoji and make it engaging. Don't use markdown headers, just the emoji labels above.
If there's limited data, acknowledge it and focus on what you can see."""

    result = ask_llm(provider, api_key, prompt, model)
    return result
