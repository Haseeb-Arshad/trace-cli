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
from .monitor import SystemMonitor, get_system_info, get_running_processes
from .system import ShutdownGuard, register_console_handler
from .browser import extract_searches, extract_full_history
from .categorizer import is_productive, get_category_emoji, get_app_role

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


def format_memory(mb: float) -> str:
    """Format memory in MB with appropriate units."""
    if mb < 1:
        return f"{mb * 1024:.0f} KB"
    elif mb < 1024:
        return f"{mb:.1f} MB"
    else:
        return f"{mb / 1024:.2f} GB"


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
@click.version_option(version="2.0.0", prog_name="TraceCLI")
def main():
    """🔍 TraceCLI — The terminal's black box for your digital life.

    A privacy-first activity monitor that tracks window usage, memory/CPU,
    browser history, and productivity — all stored locally in SQLite.
    No cloud. No accounts. No tracking.
    """
    pass


# ── START Command ──────────────────────────────────────────────────────────

@main.command()
@click.option("--poll-interval", default=1.0, help="Polling interval in seconds")
@click.option("--min-duration", default=2.0, help="Minimum activity duration to log (seconds)")
@click.option("--sync-searches", default=300, help="Browser search sync interval (seconds)")
@click.option("--snapshot-interval", default=30, help="System snapshot interval (seconds)")
def start(poll_interval, min_duration, sync_searches, snapshot_interval):
    """▶️  Start background activity tracking with live dashboard."""
    print_banner()
    db.init_db()

    tracker = ActivityTracker(
        poll_interval=poll_interval,
        min_duration=min_duration,
    )

    monitor = SystemMonitor(interval=snapshot_interval)

    guard = ShutdownGuard()

    def flush_all():
        """Emergency flush for shutdown scenarios."""
        tracker.flush()
        try:
            db.upsert_daily_stats()
            db.upsert_app_usage_history()
        except Exception:
            pass

    guard.start(flush_all)
    register_console_handler(flush_all)
    tracker.start()
    monitor.start()

    console.print()
    console.print("[bold green]✔ Tracker started![/bold green]")
    console.print(f"  [dim]Poll interval:[/dim]       {poll_interval}s")
    console.print(f"  [dim]Min duration:[/dim]        {min_duration}s")
    console.print(f"  [dim]Snapshot interval:[/dim]   {snapshot_interval}s")
    console.print(f"  [dim]Database:[/dim]             {db.DB_PATH}")
    console.print(f"  [dim]Search sync:[/dim]          every {sync_searches}s")
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

            # Sync full URL history too
            try:
                urls = extract_full_history(since_minutes=10)
                for u in urls:
                    try:
                        db.insert_browser_url(
                            timestamp=u.timestamp,
                            browser=u.browser,
                            url=u.url,
                            title=u.title,
                            visit_duration=u.visit_duration,
                            domain=u.domain,
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
                sys_info = monitor.get_latest_system_info()

                panel_content = _build_live_panel(current, session_dur, tracker, sys_info)
                live.update(panel_content)
                time.sleep(1)

    except (KeyboardInterrupt, SystemExit):
        console.print()
        console.print("[yellow]⏳ Stopping tracker...[/yellow]")

        tracker.stop()
        monitor.stop()
        search_stop.set()

        # Update daily stats and app history
        try:
            db.upsert_daily_stats()
            db.upsert_app_usage_history()
        except Exception:
            pass

        guard.stop()

        console.print("[bold green]✔ All data saved. Session complete.[/bold green]")
        console.print(
            f"  [dim]Activities logged:[/dim]   {tracker.total_logged}"
        )
        console.print(
            f"  [dim]Window switches:[/dim]    {tracker.total_switches}"
        )
        console.print(
            f"  [dim]Snapshots taken:[/dim]    {monitor.total_snapshots}"
        )
        console.print(
            f"  [dim]Session duration:[/dim]   {format_duration(session_dur)}"
        )


def _build_live_panel(
    current: Optional[dict],
    session_dur: float,
    tracker,
    sys_info: Optional[dict] = None,
) -> Panel:
    """Build the live dashboard panel with resource data."""
    if not current:
        content = Text("Waiting for window activity...", style="dim italic")
    else:
        lines = Text()
        lines.append("  App:       ", style="dim")
        lines.append(f"{current['app_name']}\n", style="bold white")
        lines.append("  Window:    ", style="dim")
        lines.append(f"{truncate(current['window_title'], 65)}\n", style="white")
        lines.append("  Category:  ", style="dim")

        cat = current["category"]
        cat_style = "green" if is_productive(cat) else "red" if "Distraction" in cat else "yellow"
        lines.append(f"{cat}\n", style=f"bold {cat_style}")

        lines.append("  Duration:  ", style="dim")
        lines.append(f"{format_duration(current['duration_seconds'])}\n", style="cyan")

        # Resource info for current app
        mem = current.get("memory_mb", 0)
        cpu = current.get("cpu_percent", 0)
        lines.append("  Memory:    ", style="dim")
        mem_style = "red" if mem > 500 else "yellow" if mem > 200 else "green"
        lines.append(f"{format_memory(mem)}\n", style=mem_style)
        lines.append("  CPU:       ", style="dim")
        cpu_style = "red" if cpu > 50 else "yellow" if cpu > 20 else "green"
        lines.append(f"{cpu:.1f}%\n", style=cpu_style)

        lines.append("\n")

        # Session stats bar
        lines.append(f"  Session:   ", style="dim")
        lines.append(f"{format_duration(session_dur)}", style="bright_blue")
        lines.append(f"  │  Logged: ", style="dim")
        lines.append(f"{tracker.total_logged}", style="bright_blue")
        lines.append(f"  │  Switches: ", style="dim")
        lines.append(f"{tracker.total_switches}", style="bright_blue")

        # System info
        if sys_info:
            lines.append("\n\n")
            lines.append("  ─── System ───\n", style="dim")
            lines.append("  RAM:  ", style="dim")
            ram_pct = sys_info.get("ram_percent", 0)
            ram_style = "red" if ram_pct > 85 else "yellow" if ram_pct > 60 else "green"
            lines.append(
                f"{sys_info.get('used_ram_gb', 0):.1f}/{sys_info.get('total_ram_gb', 0):.1f} GB ({ram_pct:.0f}%)",
                style=ram_style,
            )
            lines.append("  │  CPU: ", style="dim")
            sys_cpu = sys_info.get("cpu_percent", 0)
            scpu_style = "red" if sys_cpu > 80 else "yellow" if sys_cpu > 40 else "green"
            lines.append(f"{sys_cpu:.0f}%", style=scpu_style)

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

    # Top apps table (enriched with resource data)
    app_table = Table(
        title="🏆 Top Applications",
        box=box.SIMPLE_HEAVY,
        show_lines=False,
        title_style="bold bright_cyan",
    )
    app_table.add_column("#", style="dim", width=3)
    app_table.add_column("Application", style="bold", min_width=18)
    app_table.add_column("Duration", justify="right", style="cyan", width=9)
    app_table.add_column("Avg RAM", justify="right", width=10)
    app_table.add_column("Peak RAM", justify="right", width=10)
    app_table.add_column("Avg CPU", justify="right", width=8)
    app_table.add_column("Sessions", justify="right", style="dim", width=8)

    for i, app in enumerate(app_breakdown[:10], 1):
        avg_mem = app.get("avg_memory_mb", 0) or 0
        peak_mem = app.get("peak_memory_mb", 0) or 0
        avg_cpu = app.get("avg_cpu_percent", 0) or 0

        mem_style = "red" if avg_mem > 500 else "yellow" if avg_mem > 200 else "green"
        cpu_style = "red" if avg_cpu > 50 else "yellow" if avg_cpu > 20 else "dim"

        app_table.add_row(
            str(i),
            app["app_name"],
            format_duration(app["total_seconds"]),
            f"[{mem_style}]{format_memory(avg_mem)}[/{mem_style}]",
            f"[{mem_style}]{format_memory(peak_mem)}[/{mem_style}]",
            f"[{cpu_style}]{avg_cpu:.1f}%[/{cpu_style}]",
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
    log_table.add_column("App", style="bold", width=16)
    log_table.add_column("Window Title", min_width=28)
    log_table.add_column("RAM", justify="right", width=9)
    log_table.add_column("Category", width=18)

    for act in activities[:30]:
        cat = act["category"]
        cat_style = "green" if is_productive(cat) else (
            "red" if "Distraction" in cat else "yellow"
        )
        mem = act.get("memory_mb", 0) or 0
        log_table.add_row(
            format_time(act["start_time"]),
            format_duration(act["duration_seconds"]),
            act["app_name"],
            truncate(act["window_title"], 40),
            format_memory(mem),
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
            title = truncate(act["window_title"], 45)
            mem = act.get("memory_mb", 0) or 0
            mem_str = f" [{format_memory(mem)}]" if mem > 0 else ""
            console.print(f"    {emoji} [dim]{dur:>7}[/dim]  {act['app_name']}: {title}[dim]{mem_str}[/dim]")

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
                table.add_column("App", style="bold", width=16)
                table.add_column("Window", min_width=30)
                table.add_column("RAM", justify="right", width=9)
                table.add_column("CPU", justify="right", width=6)
                table.add_column("Category", width=18)

                for act in activities:
                    cat = act["category"]
                    style = "green" if is_productive(cat) else (
                        "red" if "Distraction" in cat else "yellow"
                    )
                    mem = act.get("memory_mb", 0) or 0
                    cpu = act.get("cpu_percent", 0) or 0
                    table.add_row(
                        format_time(act["start_time"]),
                        format_duration(act["duration_seconds"]),
                        act["app_name"],
                        truncate(act["window_title"], 40),
                        format_memory(mem),
                        f"{cpu:.1f}%",
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


# ── APP Command (Deep Analytics) ──────────────────────────────────────────

@main.command()
@click.argument("app_name")
@click.option("--date", "-d", "date_str", default=None, help="Date (YYYY-MM-DD)")
def app(app_name, date_str):
    """🔬 Deep analytics drill-down for a specific application.

    Examples:
        tracecli app chrome.exe
        tracecli app code.exe --date 2025-02-15
    """
    target = parse_date(date_str)
    db.init_db()

    analytics = db.get_app_analytics(app_name, target)
    if not analytics:
        # Try case-insensitive match
        all_apps = db.get_all_tracked_apps()
        matched = [a for a in all_apps if app_name.lower() in a["app_name"].lower()]
        if matched:
            console.print(f"\n[yellow]No exact match for '{app_name}'. Did you mean:[/yellow]")
            for a in matched[:5]:
                console.print(f"  • {a['app_name']} ({format_duration(a['total_seconds'])} total)")
        else:
            console.print(f"\n[yellow]No data for '{app_name}' on {target}.[/yellow]")
        return

    role = get_app_role(app_name)

    console.print()
    console.print(
        Panel(
            f"[bold]🔬 App Analytics — {app_name}[/bold]\n"
            f"[dim]{role}[/dim]",
            border_style="bright_cyan",
            box=box.DOUBLE_EDGE,
        )
    )

    # Summary card
    info_table = Table(box=box.SIMPLE, show_header=False, padding=(0, 3))
    info_table.add_column("Key", style="dim")
    info_table.add_column("Value", style="bold")

    info_table.add_row("📅 Date", str(target))
    info_table.add_row("⏱️  Total Time", format_duration(analytics["total_seconds"]))
    info_table.add_row("🔄 Sessions", str(analytics["session_count"]))
    info_table.add_row("📂 Category", analytics["category"])
    info_table.add_row("🏷️  Role", role)

    mem_style = "red" if analytics["avg_memory_mb"] > 500 else "yellow" if analytics["avg_memory_mb"] > 200 else "green"
    info_table.add_row("💾 Avg Memory", f"[{mem_style}]{format_memory(analytics['avg_memory_mb'])}[/{mem_style}]")
    info_table.add_row("💾 Peak Memory", f"[{mem_style}]{format_memory(analytics['peak_memory_mb'])}[/{mem_style}]")

    cpu_style = "red" if analytics["avg_cpu"] > 50 else "yellow" if analytics["avg_cpu"] > 20 else "green"
    info_table.add_row("⚡ Avg CPU", f"[{cpu_style}]{analytics['avg_cpu']:.1f}%[/{cpu_style}]")
    info_table.add_row("⚡ Peak CPU", f"[{cpu_style}]{analytics['peak_cpu']:.1f}%[/{cpu_style}]")

    if analytics.get("first_seen"):
        info_table.add_row("🕐 First Seen", format_time(analytics["first_seen"]))
    if analytics.get("last_seen"):
        info_table.add_row("🕐 Last Seen", format_time(analytics["last_seen"]))

    console.print(
        Panel(info_table, title="[bold]Summary[/bold]", border_style="bright_blue", box=box.ROUNDED)
    )

    # Top window titles
    titles = analytics.get("top_titles", [])
    if titles:
        title_table = Table(
            title="🪟 Window Titles (by time)",
            box=box.SIMPLE_HEAVY,
            title_style="bold bright_cyan",
        )
        title_table.add_column("#", style="dim", width=3)
        title_table.add_column("Window Title", style="white", min_width=40)
        title_table.add_column("Duration", justify="right", style="cyan", width=9)
        title_table.add_column("Count", justify="right", style="dim", width=6)

        for i, t in enumerate(titles[:10], 1):
            title_table.add_row(
                str(i),
                truncate(t["window_title"], 55),
                format_duration(t["total_seconds"]),
                str(t["count"]),
            )

        console.print(title_table)
        console.print()

    # Usage history (multi-day trend)
    history = db.get_app_history(app_name, days=14)
    if history and len(history) > 1:
        hist_table = Table(
            title="📈 Usage History (last 14 days)",
            box=box.SIMPLE_HEAVY,
            title_style="bold bright_cyan",
        )
        hist_table.add_column("Date", style="bold", width=12)
        hist_table.add_column("Duration", justify="right", style="cyan", width=9)
        hist_table.add_column("Sessions", justify="right", style="dim", width=8)
        hist_table.add_column("Avg RAM", justify="right", width=10)
        hist_table.add_column("Trend", width=22)

        max_dur = max(h["total_seconds"] for h in history)
        for h in history:
            pct = (h["total_seconds"] / max_dur * 100) if max_dur > 0 else 0
            bar_len = int(pct / 5)
            bar = "█" * bar_len + "░" * (20 - bar_len)
            avg_mem = h.get("avg_memory_mb", 0) or 0

            hist_table.add_row(
                h["date"],
                format_duration(h["total_seconds"]),
                str(h["session_count"]),
                format_memory(avg_mem),
                f"[bright_blue]{bar}[/bright_blue]",
            )

        console.print(hist_table)
        console.print()

    # Resource timeline (if snapshots exist)
    timeline_data = analytics.get("resource_timeline", [])
    if timeline_data and len(timeline_data) > 2:
        console.print(
            Panel(
                f"[dim]{len(timeline_data)} resource snapshots recorded for this app today[/dim]",
                border_style="dim",
            )
        )


# ── SYSTEM Command ────────────────────────────────────────────────────────

@main.command()
@click.option("--date", "-d", "date_str", default=None, help="Date (YYYY-MM-DD)")
@click.option("--live-now", is_flag=True, help="Show live system snapshot (ignores date)")
def system(date_str, live_now):
    """💻 Show system resource overview — memory, CPU, and all running apps."""
    db.init_db()

    if live_now:
        _show_live_system()
        return

    target = parse_date(date_str)

    console.print()
    console.print(
        Panel(
            f"[bold]💻 System Overview — {target}[/bold]",
            border_style="bright_cyan",
            box=box.DOUBLE_EDGE,
        )
    )

    # Current system info
    sys_info = get_system_info()
    info_table = Table(box=box.SIMPLE, show_header=False, padding=(0, 3))
    info_table.add_column("Key", style="dim")
    info_table.add_column("Value", style="bold")

    ram_pct = sys_info["ram_percent"]
    ram_style = "red" if ram_pct > 85 else "yellow" if ram_pct > 60 else "green"
    info_table.add_row("💾 Total RAM", f"{sys_info['total_ram_gb']:.1f} GB")
    info_table.add_row("💾 Used RAM", f"[{ram_style}]{sys_info['used_ram_gb']:.1f} GB ({ram_pct:.0f}%)[/{ram_style}]")
    info_table.add_row("⚡ CPU Cores", str(sys_info["cpu_count"]))
    info_table.add_row("⚡ CPU Load", f"{sys_info['cpu_percent']:.0f}%")
    info_table.add_row("💿 Disk", f"{sys_info['disk_used_gb']:.0f}/{sys_info['disk_total_gb']:.0f} GB ({sys_info['disk_percent']:.0f}%)")

    snapshot_count = db.get_snapshot_count(target)
    info_table.add_row("📸 Snapshots Today", str(snapshot_count))

    console.print(
        Panel(info_table, title="[bold]Current System[/bold]", border_style="bright_blue", box=box.ROUNDED)
    )

    # Top memory consumers (from snapshots)
    top_mem = db.get_top_memory_apps(target)
    if top_mem:
        mem_table = Table(
            title="💾 Top Memory Consumers (from snapshots)",
            box=box.SIMPLE_HEAVY,
            title_style="bold bright_cyan",
        )
        mem_table.add_column("#", style="dim", width=3)
        mem_table.add_column("Application", style="bold", min_width=22)
        mem_table.add_column("Avg RAM", justify="right", width=10)
        mem_table.add_column("Peak RAM", justify="right", width=10)
        mem_table.add_column("Instances", justify="right", style="dim", width=9)
        mem_table.add_column("Avg CPU", justify="right", width=8)

        for i, app in enumerate(top_mem, 1):
            avg_m = app.get("avg_memory_mb", 0) or 0
            peak_m = app.get("peak_memory_mb", 0) or 0
            m_style = "red" if avg_m > 500 else "yellow" if avg_m > 200 else "green"

            mem_table.add_row(
                str(i),
                app["app_name"],
                f"[{m_style}]{format_memory(avg_m)}[/{m_style}]",
                f"[{m_style}]{format_memory(peak_m)}[/{m_style}]",
                str(app.get("instance_count", 0)),
                f"{app.get('avg_cpu', 0) or 0:.1f}%",
            )

        console.print(mem_table)
        console.print()

    # Top CPU consumers
    top_cpu = db.get_top_cpu_apps(target)
    if top_cpu:
        cpu_table = Table(
            title="⚡ Top CPU Consumers (from snapshots)",
            box=box.SIMPLE_HEAVY,
            title_style="bold bright_cyan",
        )
        cpu_table.add_column("#", style="dim", width=3)
        cpu_table.add_column("Application", style="bold", min_width=22)
        cpu_table.add_column("Avg CPU", justify="right", width=8)
        cpu_table.add_column("Peak CPU", justify="right", width=8)
        cpu_table.add_column("Avg RAM", justify="right", width=10)

        for i, app in enumerate(top_cpu, 1):
            avg_c = app.get("avg_cpu", 0) or 0
            c_style = "red" if avg_c > 50 else "yellow" if avg_c > 20 else "green"

            cpu_table.add_row(
                str(i),
                app["app_name"],
                f"[{c_style}]{avg_c:.1f}%[/{c_style}]",
                f"{app.get('peak_cpu', 0) or 0:.1f}%",
                format_memory(app.get("avg_memory_mb", 0) or 0),
            )

        console.print(cpu_table)
        console.print()

    if not top_mem and not top_cpu:
        console.print("[yellow]No process snapshots yet. Run 'tracecli start' to begin capturing.[/yellow]")
        console.print()


def _show_live_system():
    """Show a live snapshot of all running processes."""
    console.print()
    console.print(
        Panel("[bold]💻 Live System Snapshot[/bold]", border_style="bright_cyan", box=box.DOUBLE_EDGE)
    )

    sys_info = get_system_info()
    console.print(
        f"  [dim]RAM:[/dim] {sys_info['used_ram_gb']:.1f}/{sys_info['total_ram_gb']:.1f} GB "
        f"({sys_info['ram_percent']:.0f}%)  │  "
        f"[dim]CPU:[/dim] {sys_info['cpu_percent']:.0f}% "
        f"({sys_info['cpu_count']} cores)  │  "
        f"[dim]Disk:[/dim] {sys_info['disk_percent']:.0f}%"
    )
    console.print()

    processes = get_running_processes(sort_by="memory")

    proc_table = Table(
        title="🔄 All Running Processes (sorted by memory)",
        box=box.SIMPLE_HEAVY,
        title_style="bold bright_cyan",
    )
    proc_table.add_column("#", style="dim", width=3)
    proc_table.add_column("PID", style="dim", width=8)
    proc_table.add_column("Application", style="bold", min_width=22)
    proc_table.add_column("Role", style="dim", min_width=20)
    proc_table.add_column("Memory", justify="right", width=10)
    proc_table.add_column("CPU %", justify="right", width=7)
    proc_table.add_column("Threads", justify="right", style="dim", width=8)
    proc_table.add_column("Status", width=10)

    for i, proc in enumerate(processes[:40], 1):
        mem = proc["memory_mb"]
        cpu = proc["cpu_percent"]
        mem_style = "red" if mem > 500 else "yellow" if mem > 200 else "green" if mem > 10 else "dim"
        cpu_style = "red" if cpu > 50 else "yellow" if cpu > 20 else "dim"
        status_style = "green" if proc["status"] == "running" else "yellow"
        role = get_app_role(proc["app_name"])

        proc_table.add_row(
            str(i),
            str(proc["pid"]),
            proc["app_name"],
            truncate(role, 25),
            f"[{mem_style}]{format_memory(mem)}[/{mem_style}]",
            f"[{cpu_style}]{cpu:.1f}%[/{cpu_style}]",
            str(proc["num_threads"]),
            f"[{status_style}]{proc['status']}[/{status_style}]",
        )

    console.print(proc_table)
    console.print()
    console.print(f"[dim]Total processes: {len(processes)}[/dim]")
    console.print()


# ── URLS Command ──────────────────────────────────────────────────────────

@main.command()
@click.option("--date", "-d", "date_str", default=None, help="Date (YYYY-MM-DD)")
@click.option("--sync/--no-sync", default=True, help="Sync browser history first")
@click.option("--limit", "-n", default=50, help="Max URLs to show")
def urls(date_str, sync, limit):
    """🌐 Show full browser URL history with domain breakdown."""
    target = parse_date(date_str)
    db.init_db()

    # Optionally sync browser history
    if sync and target == date.today():
        console.print("[dim]Syncing browser URL history...[/dim]")
        try:
            browser_urls = extract_full_history(since_minutes=1440)
            for u in browser_urls:
                try:
                    db.insert_browser_url(
                        timestamp=u.timestamp,
                        browser=u.browser,
                        url=u.url,
                        title=u.title,
                        visit_duration=u.visit_duration,
                        domain=u.domain,
                    )
                except Exception:
                    pass
        except Exception:
            pass

    # Domain breakdown
    domain_breakdown = db.get_domain_breakdown(target)
    if domain_breakdown:
        console.print()
        domain_table = Table(
            title=f"🌐 Domain Breakdown — {target}",
            box=box.SIMPLE_HEAVY,
            title_style="bold bright_cyan",
        )
        domain_table.add_column("#", style="dim", width=3)
        domain_table.add_column("Domain", style="bold", min_width=25)
        domain_table.add_column("Visits", justify="right", style="cyan", width=8)
        domain_table.add_column("Total Time", justify="right", style="dim", width=10)

        for i, d in enumerate(domain_breakdown[:20], 1):
            domain_table.add_row(
                str(i),
                d["domain"],
                str(d["visit_count"]),
                format_duration(d.get("total_duration", 0) or 0),
            )

        console.print(domain_table)
        console.print()

    # Full URL list
    url_records = db.query_browser_urls(target, limit)
    if not url_records and not domain_breakdown:
        console.print(f"\n[yellow]No browser URLs recorded for {target}.[/yellow]")
        return

    if url_records:
        url_table = Table(
            title=f"📋 Recent URLs — {target}",
            box=box.SIMPLE_HEAVY,
            title_style="bold bright_cyan",
        )
        url_table.add_column("Time", style="dim", width=10)
        url_table.add_column("Title", style="white", min_width=35)
        url_table.add_column("Domain", style="bright_magenta", width=20)
        url_table.add_column("Browser", style="dim", width=10)

        for u in url_records:
            url_table.add_row(
                format_time(u["timestamp"]),
                truncate(u.get("title", "") or "", 45),
                u.get("domain", ""),
                u.get("browser", ""),
            )

        console.print(url_table)
        console.print()


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

        row = conn.execute("SELECT COUNT(DISTINCT timestamp) FROM process_snapshots").fetchone()
        info_table.add_row("System Snapshots", str(row[0]))

        row = conn.execute("SELECT COUNT(*) FROM browser_urls").fetchone()
        info_table.add_row("Browser URLs", str(row[0]))

        row = conn.execute(
            "SELECT MIN(start_time), MAX(start_time) FROM activity_log"
        ).fetchone()
        if row[0]:
            info_table.add_row("First Record", format_time(row[0]))
            info_table.add_row("Latest Record", format_time(row[1]))
    except Exception:
        pass

    # Current system snapshot
    try:
        sys_info = get_system_info()
        ram_pct = sys_info["ram_percent"]
        ram_style = "red" if ram_pct > 85 else "yellow" if ram_pct > 60 else "green"
        info_table.add_row("", "")  # spacer
        info_table.add_row(
            "System RAM",
            f"[{ram_style}]{sys_info['used_ram_gb']:.1f}/{sys_info['total_ram_gb']:.1f} GB ({ram_pct:.0f}%)[/{ram_style}]",
        )
        info_table.add_row("System CPU", f"{sys_info['cpu_percent']:.0f}% ({sys_info['cpu_count']} cores)")
    except Exception:
        pass

    console.print(Panel(info_table, title="[bold]TraceCLI Status[/bold]", border_style="bright_cyan"))
    console.print()


# ── Auto-Start Management ─────────────────────────────────────────────────

@main.command()
@click.option("--enable", "action", flag_value="enable", help="Enable auto-start on Windows login")
@click.option("--disable", "action", flag_value="disable", help="Disable auto-start")
@click.option("--status", "action", flag_value="status", default=True, help="Show auto-start status (default)")
def autostart(action):
    """Manage TraceCLI Windows startup behavior.

    \b
    tracecli autostart --enable   Start TraceCLI silently on login
    tracecli autostart --disable  Remove auto-start
    tracecli autostart --status   Check current status
    """
    from .autostart import enable_autostart, disable_autostart, get_autostart_info

    if action == "enable":
        success, msg = enable_autostart()
        if success:
            console.print(f"\n[bold green]✅ {msg}[/bold green]\n")
        else:
            console.print(f"\n[bold red]❌ {msg}[/bold red]\n")
            raise SystemExit(1)

    elif action == "disable":
        success, msg = disable_autostart()
        if success:
            console.print(f"\n[bold yellow]🔕 {msg}[/bold yellow]\n")
        else:
            console.print(f"\n[bold red]❌ {msg}[/bold red]\n")

    else:  # status
        info = get_autostart_info()
        status_table = Table(show_header=False, box=box.SIMPLE, padding=(0, 2))
        status_table.add_column("Key", style="bold cyan")
        status_table.add_column("Value")

        if info["enabled"]:
            status_table.add_row("Status", "[bold green]✅ Enabled[/bold green]")
        else:
            status_table.add_row("Status", "[dim]❌ Disabled[/dim]")

        status_table.add_row("Task Name", info["task_name"])
        status_table.add_row("VBS Script", info["vbs_path"])
        status_table.add_row("VBS Exists", "✅" if info["vbs_exists"] else "❌")

        if info.get("last_run"):
            status_table.add_row("Last Run", info["last_run"])
        if info.get("status"):
            status_table.add_row("Task Status", info["status"])

        console.print()
        console.print(Panel(
            status_table,
            title="[bold]TraceCLI Auto-Start[/bold]",
            border_style="bright_cyan",
        ))
        console.print()


# ── Entry Point ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    main()
