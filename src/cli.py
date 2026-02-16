"""
TraceCLI — Rich Terminal Interface
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Beautiful CLI dashboard for viewing and controlling your activity tracker.
Built with Click + Rich for a premium terminal experience.
"""

import sys
import time
import threading
from datetime import datetime, date, timedelta
from typing import Optional

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from rich.live import Live
from rich.text import Text
from rich.progress import BarColumn, Progress, TextColumn
from rich.align import Align
from rich import box

from . import database as db
from .tracker import ActivityTracker
from .system import ShutdownGuard, register_console_handler
from .browser import extract_searches
from .categorizer import is_productive, get_category_emoji

console = Console()


# ── Formatting Helpers ─────────────────────────────────────────────────────

def format_duration(seconds: float) -> str:
    """Format seconds into a human-readable string."""
    if seconds < 60:
        return f"{seconds:.0f}s"
    elif seconds < 3600:
        m = int(seconds // 60)
        s = int(seconds % 60)
        return f"{m}m {s}s"
    else:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        return f"{h}h {m}m"


def format_time(iso_str: str) -> str:
    """Format an ISO timestamp to HH:MM:SS."""
    try:
        dt = datetime.fromisoformat(iso_str)
        return dt.strftime("%H:%M:%S")
    except (ValueError, TypeError):
        return iso_str


def parse_date(date_str: Optional[str]) -> date:
    """Parse a date string or return today."""
    if not date_str:
        return date.today()
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        console.print(f"[red]Invalid date format: {date_str}. Use YYYY-MM-DD.[/red]")
        raise SystemExit(1)


def truncate(text: str, max_len: int = 50) -> str:
    """Truncate text with ellipsis."""
    if len(text) > max_len:
        return text[: max_len - 1] + "…"
    return text


# ── ASCII Art Banner ───────────────────────────────────────────────────────

BANNER = r"""
 ████████╗██████╗  █████╗  ██████╗███████╗ ██████╗██╗     ██╗
 ╚══██╔══╝██╔══██╗██╔══██╗██╔════╝██╔════╝██╔════╝██║     ██║
    ██║   ██████╔╝███████║██║     █████╗  ██║     ██║     ██║
    ██║   ██╔══██╗██╔══██║██║     ██╔══╝  ██║     ██║     ██║
    ██║   ██║  ██║██║  ██║╚██████╗███████╗╚██████╗███████╗██║
    ╚═╝   ╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝╚══════╝ ╚═════╝╚══════╝╚═╝
"""


def print_banner():
    """Print the TraceCLI banner."""
    console.print(
        Panel(
            Align.center(
                Text(BANNER, style="bold cyan")
            ),
            subtitle="[dim]The terminal's black box for your digital life[/dim]",
            border_style="bright_blue",
            box=box.DOUBLE_EDGE,
        )
    )


# ── CLI Group ──────────────────────────────────────────────────────────────

@click.group()
@click.version_option(version="1.0.0", prog_name="TraceCLI")
def main():
    """🔍 TraceCLI — The terminal's black box for your digital life.

    A privacy-first activity monitor that tracks your window usage,
    categorizes productivity, and extracts search intent — all stored
    locally in SQLite. No cloud. No accounts. No tracking.
    """
    pass


# ── START Command ──────────────────────────────────────────────────────────

@main.command()
@click.option("--poll-interval", default=1.0, help="Polling interval in seconds")
@click.option("--min-duration", default=2.0, help="Minimum activity duration to log (seconds)")
@click.option("--sync-searches", default=300, help="Browser search sync interval (seconds)")
def start(poll_interval, min_duration, sync_searches):
    """▶️  Start background activity tracking with live dashboard."""
    print_banner()
    db.init_db()

    tracker = ActivityTracker(
        poll_interval=poll_interval,
        min_duration=min_duration,
    )

    guard = ShutdownGuard()

    def flush_all():
        """Emergency flush for shutdown scenarios."""
        tracker.flush()
        try:
            db.upsert_daily_stats()
        except Exception:
            pass

    guard.start(flush_all)
    register_console_handler(flush_all)
    tracker.start()

    console.print()
    console.print("[bold green]✔ Tracker started![/bold green]")
    console.print(f"  [dim]Poll interval:[/dim]    {poll_interval}s")
    console.print(f"  [dim]Min duration:[/dim]     {min_duration}s")
    console.print(f"  [dim]Database:[/dim]          {db.DB_PATH}")
    console.print(f"  [dim]Search sync:[/dim]       every {sync_searches}s")
    console.print()
    console.print("[yellow]Press Ctrl+C to stop tracking.[/yellow]")
    console.print()

    # Start periodic browser search sync
    search_stop = threading.Event()

    def sync_browser_searches():
        while not search_stop.is_set():
            try:
                searches = extract_searches(since_minutes=10)
                for s in searches:
                    try:
                        db.insert_search(
                            timestamp=s.timestamp,
                            browser=s.browser,
                            query=s.query,
                            url=s.url,
                            source=s.source,
                        )
                    except Exception:
                        pass
            except Exception:
                pass
            search_stop.wait(sync_searches)

    sync_thread = threading.Thread(
        target=sync_browser_searches,
        name="TraceCLI-SearchSync",
        daemon=True,
    )
    sync_thread.start()

    # Live dashboard
    try:
        with Live(console=console, refresh_per_second=1, transient=True) as live:
            while True:
                current = tracker.get_current()
                session_dur = tracker.get_session_duration()

                panel_content = _build_live_panel(current, session_dur, tracker)
                live.update(panel_content)
                time.sleep(1)

    except (KeyboardInterrupt, SystemExit):
        console.print()
        console.print("[yellow]⏳ Stopping tracker...[/yellow]")

        tracker.stop()
        search_stop.set()

        # Update daily stats
        try:
            db.upsert_daily_stats()
        except Exception:
            pass

        guard.stop()

        console.print("[bold green]✔ All data saved. Session complete.[/bold green]")
        console.print(
            f"  [dim]Activities logged:[/dim]  {tracker.total_logged}"
        )
        console.print(
            f"  [dim]Window switches:[/dim]   {tracker.total_switches}"
        )
        console.print(
            f"  [dim]Session duration:[/dim]  {format_duration(session_dur)}"
        )


def _build_live_panel(current: Optional[dict], session_dur: float, tracker) -> Panel:
    """Build the live dashboard panel."""
    if not current:
        content = Text("Waiting for window activity...", style="dim italic")
    else:
        lines = Text()
        lines.append("  App:       ", style="dim")
        lines.append(f"{current['app_name']}\n", style="bold white")
        lines.append("  Window:    ", style="dim")
        lines.append(f"{truncate(current['window_title'], 70)}\n", style="white")
        lines.append("  Category:  ", style="dim")

        cat = current["category"]
        cat_style = "green" if is_productive(cat) else "red" if "Distraction" in cat else "yellow"
        lines.append(f"{cat}\n", style=f"bold {cat_style}")

        lines.append("  Duration:  ", style="dim")
        lines.append(f"{format_duration(current['duration_seconds'])}\n", style="cyan")
        lines.append("\n")
        lines.append(f"  Session:   ", style="dim")
        lines.append(f"{format_duration(session_dur)}", style="bright_blue")
        lines.append(f"  │  Logged: ", style="dim")
        lines.append(f"{tracker.total_logged}", style="bright_blue")
        lines.append(f"  │  Switches: ", style="dim")
        lines.append(f"{tracker.total_switches}", style="bright_blue")
        content = lines

    return Panel(
        content,
        title="[bold bright_cyan]⚡ TraceCLI Live[/bold bright_cyan]",
        subtitle=f"[dim]{datetime.now().strftime('%H:%M:%S')}[/dim]",
        border_style="bright_blue",
        box=box.ROUNDED,
        padding=(1, 2),
    )


# ── REPORT Command ────────────────────────────────────────────────────────

@main.command()
@click.option("--date", "-d", "date_str", default=None, help="Date (YYYY-MM-DD), defaults to today")
@click.option("--limit", "-n", default=50, help="Max records to show")
def report(date_str, limit):
    """📊 Show detailed activity report for a day."""
    target = parse_date(date_str)
    db.init_db()

    activities = db.query_activities(target, limit)
    if not activities:
        console.print(f"\n[yellow]No activities recorded for {target}.[/yellow]")
        return

    console.print()
    console.print(
        Panel(
            f"[bold]Activity Report — {target}[/bold]",
            border_style="bright_cyan",
            box=box.DOUBLE_EDGE,
        )
    )

    # Summary stats
    cat_breakdown = db.get_category_breakdown(target)
    app_breakdown = db.get_app_breakdown(target)
    total_seconds = sum(c["total_seconds"] for c in cat_breakdown)

    # Category breakdown table
    cat_table = Table(
        title="📂 Time by Category",
        box=box.SIMPLE_HEAVY,
        show_lines=False,
        title_style="bold bright_cyan",
    )
    cat_table.add_column("Category", style="bold", min_width=20)
    cat_table.add_column("Duration", justify="right", style="cyan")
    cat_table.add_column("% of Day", justify="right")
    cat_table.add_column("Sessions", justify="right", style="dim")

    for cat in cat_breakdown:
        pct = (cat["total_seconds"] / total_seconds * 100) if total_seconds > 0 else 0
        bar_len = int(pct / 5)
        bar = "█" * bar_len + "░" * (20 - bar_len)

        style = "green" if is_productive(cat["category"]) else (
            "red" if "Distraction" in cat["category"] else "yellow"
        )

        cat_table.add_row(
            cat["category"],
            format_duration(cat["total_seconds"]),
            f"[{style}]{bar} {pct:.1f}%[/{style}]",
            str(cat["switch_count"]),
        )

    console.print(cat_table)
    console.print()

    # Top apps table
    app_table = Table(
        title="🏆 Top Applications",
        box=box.SIMPLE_HEAVY,
        show_lines=False,
        title_style="bold bright_cyan",
    )
    app_table.add_column("#", style="dim", width=3)
    app_table.add_column("Application", style="bold", min_width=20)
    app_table.add_column("Duration", justify="right", style="cyan")
    app_table.add_column("Sessions", justify="right", style="dim")

    for i, app in enumerate(app_breakdown[:10], 1):
        app_table.add_row(
            str(i),
            app["app_name"],
            format_duration(app["total_seconds"]),
            str(app["switch_count"]),
        )

    console.print(app_table)
    console.print()

    # Activity log table
    log_table = Table(
        title="📋 Activity Log (Recent)",
        box=box.SIMPLE_HEAVY,
        show_lines=False,
        title_style="bold bright_cyan",
    )
    log_table.add_column("Start", style="dim", width=10)
    log_table.add_column("Duration", justify="right", style="cyan", width=8)
    log_table.add_column("App", style="bold", width=18)
    log_table.add_column("Window Title", min_width=30)
    log_table.add_column("Category", width=18)

    for act in activities[:30]:
        cat = act["category"]
        cat_style = "green" if is_productive(cat) else (
            "red" if "Distraction" in cat else "yellow"
        )
        log_table.add_row(
            format_time(act["start_time"]),
            format_duration(act["duration_seconds"]),
            act["app_name"],
            truncate(act["window_title"], 45),
            f"[{cat_style}]{cat}[/{cat_style}]",
        )

    console.print(log_table)

    # Productivity score
    productive = sum(
        c["total_seconds"] for c in cat_breakdown if is_productive(c["category"])
    )
    score = (productive / total_seconds * 100) if total_seconds > 0 else 0
    score_style = "green" if score >= 70 else "yellow" if score >= 40 else "red"
    console.print()
    console.print(
        Panel(
            f"[bold {score_style}]🎯 Productivity Score: {score:.1f}%[/bold {score_style}]"
            f"\n[dim]Total tracked: {format_duration(total_seconds)} │ "
            f"Productive: {format_duration(productive)}[/dim]",
            border_style=score_style,
            box=box.ROUNDED,
        )
    )


# ── TIMELINE Command ──────────────────────────────────────────────────────

@main.command()
@click.option("--date", "-d", "date_str", default=None, help="Date (YYYY-MM-DD)")
def timeline(date_str):
    """⏰ Show a visual timeline of your day."""
    target = parse_date(date_str)
    db.init_db()

    activities = db.query_activities(target, limit=500)
    if not activities:
        console.print(f"\n[yellow]No activities recorded for {target}.[/yellow]")
        return

    console.print()
    console.print(
        Panel(
            f"[bold]Timeline — {target}[/bold]",
            border_style="bright_cyan",
            box=box.DOUBLE_EDGE,
        )
    )

    # Group by hour
    hourly: dict[int, list] = {}
    for act in reversed(activities):  # Chronological order
        try:
            hour = datetime.fromisoformat(act["start_time"]).hour
        except (ValueError, TypeError):
            continue
        hourly.setdefault(hour, []).append(act)

    for hour in sorted(hourly.keys()):
        acts = hourly[hour]
        total = sum(a["duration_seconds"] for a in acts)
        console.print(f"\n  [bold bright_cyan]{hour:02d}:00[/bold bright_cyan]  ─── {format_duration(total)}")

        for act in acts[:8]:  # Show top 8 per hour
            emoji = get_category_emoji(act["category"])
            dur = format_duration(act["duration_seconds"])
            title = truncate(act["window_title"], 50)
            console.print(f"    {emoji} [dim]{dur:>7}[/dim]  {act['app_name']}: {title}")

        if len(acts) > 8:
            console.print(f"    [dim]... and {len(acts) - 8} more[/dim]")

    console.print()


# ── SEARCHES Command ──────────────────────────────────────────────────────

@main.command()
@click.option("--date", "-d", "date_str", default=None, help="Date (YYYY-MM-DD)")
@click.option("--sync/--no-sync", default=True, help="Sync browser history first")
def searches(date_str, sync):
    """🔎 Show extracted search queries."""
    target = parse_date(date_str)
    db.init_db()

    # Optionally sync browser history
    if sync and target == date.today():
        console.print("[dim]Syncing browser history...[/dim]")
        try:
            results = extract_searches(since_minutes=1440)
            for s in results:
                try:
                    db.insert_search(
                        timestamp=s.timestamp,
                        browser=s.browser,
                        query=s.query,
                        url=s.url,
                        source=s.source,
                    )
                except Exception:
                    pass
        except Exception:
            pass

    search_records = db.query_searches(target)
    if not search_records:
        console.print(f"\n[yellow]No searches recorded for {target}.[/yellow]")
        return

    console.print()
    table = Table(
        title=f"🔎 Search History — {target}",
        box=box.SIMPLE_HEAVY,
        title_style="bold bright_cyan",
    )
    table.add_column("Time", style="dim", width=10)
    table.add_column("Query", style="bold white", min_width=35)
    table.add_column("Source", style="bright_magenta", width=15)
    table.add_column("Browser", style="dim", width=10)

    for s in search_records:
        table.add_row(
            format_time(s["timestamp"]),
            truncate(s["query"], 50),
            s["source"],
            s["browser"],
        )

    console.print(table)
    console.print()


# ── STATS Command ──────────────────────────────────────────────────────────

@main.command()
@click.option("--days", "-n", default=7, help="Number of days to show")
def stats(days):
    """📈 Show daily productivity stats."""
    db.init_db()

    # Ensure today's stats are up to date
    try:
        db.upsert_daily_stats()
    except Exception:
        pass

    records = db.get_stats_range(days)
    if not records:
        console.print("\n[yellow]No daily stats available yet. Run the tracker first![/yellow]")
        return

    console.print()
    table = Table(
        title=f"📈 Daily Stats — Last {days} Days",
        box=box.SIMPLE_HEAVY,
        title_style="bold bright_cyan",
    )
    table.add_column("Date", style="bold", width=12)
    table.add_column("Total", justify="right", style="cyan", width=8)
    table.add_column("Productive", justify="right", style="green", width=10)
    table.add_column("Distracted", justify="right", style="red", width=10)
    table.add_column("Score", justify="right", width=20)
    table.add_column("Top App", style="dim", width=15)

    for rec in records:
        total = rec["total_seconds"]
        productive = rec["productive_seconds"]
        score = (productive / total * 100) if total > 0 else 0
        score_style = "green" if score >= 70 else "yellow" if score >= 40 else "red"

        bar_len = int(score / 5)
        bar = "█" * bar_len + "░" * (20 - bar_len)

        table.add_row(
            rec["date"],
            format_duration(total),
            format_duration(productive),
            format_duration(rec["distraction_seconds"]),
            f"[{score_style}]{bar} {score:.0f}%[/{score_style}]",
            rec["top_app"],
        )

    console.print(table)
    console.print()


# ── LIVE Command ───────────────────────────────────────────────────────────

@main.command()
def live():
    """⚡ Show live activity feed (read-only, tracker must be running)."""
    db.init_db()

    console.print()
    console.print("[dim]Showing latest activity from database (refreshing every 2s)...[/dim]")
    console.print("[dim]Press Ctrl+C to exit.[/dim]")
    console.print()

    try:
        with Live(console=console, refresh_per_second=0.5) as live_display:
            while True:
                activities = db.query_activities(limit=15)
                table = Table(
                    title="⚡ Live Activity Feed",
                    box=box.SIMPLE_HEAVY,
                    title_style="bold bright_cyan",
                )
                table.add_column("Time", style="dim", width=10)
                table.add_column("Duration", justify="right", style="cyan", width=8)
                table.add_column("App", style="bold", width=18)
                table.add_column("Window", min_width=35)
                table.add_column("Category", width=18)

                for act in activities:
                    cat = act["category"]
                    style = "green" if is_productive(cat) else (
                        "red" if "Distraction" in cat else "yellow"
                    )
                    table.add_row(
                        format_time(act["start_time"]),
                        format_duration(act["duration_seconds"]),
                        act["app_name"],
                        truncate(act["window_title"], 45),
                        f"[{style}]{cat}[/{style}]",
                    )

                live_display.update(table)
                time.sleep(2)
    except KeyboardInterrupt:
        console.print("\n[dim]Feed closed.[/dim]")


# ── EXPORT Command ─────────────────────────────────────────────────────────

@main.command()
@click.option("--date", "-d", "date_str", default=None, help="Date (YYYY-MM-DD)")
@click.option(
    "--format", "-f", "fmt",
    type=click.Choice(["csv", "json"]),
    default="csv",
    help="Export format",
)
@click.option("--output", "-o", "output_path", default=None, help="Output file path")
def export(date_str, fmt, output_path):
    """💾 Export activity data to CSV or JSON."""
    target = parse_date(date_str)
    db.init_db()

    activities = db.query_activities(target, limit=10000)
    if not activities:
        console.print(f"\n[yellow]No activities for {target}.[/yellow]")
        return

    if not output_path:
        output_path = f"tracecli_export_{target}.{fmt}"

    if fmt == "csv":
        import csv
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=activities[0].keys())
            writer.writeheader()
            writer.writerows(activities)
    elif fmt == "json":
        import json
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(activities, f, indent=2, ensure_ascii=False)

    console.print(f"\n[bold green]✔ Exported {len(activities)} activities to {output_path}[/bold green]")


# ── STATUS Command ─────────────────────────────────────────────────────────

@main.command()
def status():
    """ℹ️  Show TraceCLI status and database info."""
    db.init_db()

    console.print()
    print_banner()

    info_table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    info_table.add_column("Key", style="dim")
    info_table.add_column("Value", style="bold")

    info_table.add_row("Database", str(db.DB_PATH))
    info_table.add_row("DB Exists", "✔ Yes" if db.DB_PATH.exists() else "✘ No")

    if db.DB_PATH.exists():
        size_mb = db.DB_PATH.stat().st_size / (1024 * 1024)
        info_table.add_row("DB Size", f"{size_mb:.2f} MB")

    # Count records
    try:
        conn = db.get_connection()
        row = conn.execute("SELECT COUNT(*) FROM activity_log").fetchone()
        info_table.add_row("Total Activities", str(row[0]))

        row = conn.execute("SELECT COUNT(*) FROM search_history").fetchone()
        info_table.add_row("Total Searches", str(row[0]))

        row = conn.execute("SELECT COUNT(*) FROM daily_stats").fetchone()
        info_table.add_row("Days Tracked", str(row[0]))

        row = conn.execute(
            "SELECT MIN(start_time), MAX(start_time) FROM activity_log"
        ).fetchone()
        if row[0]:
            info_table.add_row("First Record", format_time(row[0]))
            info_table.add_row("Latest Record", format_time(row[1]))
    except Exception:
        pass

    console.print(Panel(info_table, title="[bold]TraceCLI Status[/bold]", border_style="bright_cyan"))
    console.print()


# ── Entry Point ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    main()
