"""
TraceCLI — Rich Terminal Interface
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Beautiful CLI dashboard for viewing and controlling your activity tracker.
Built with Click + Rich for a premium terminal experience.
"""

import sys
import subprocess
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
from . import autostart as autostart_mod  # Renamed to avoid alias conflict with command
from .tracker import ActivityTracker
from .monitor import SystemMonitor, get_system_info, get_running_processes
from .system import ShutdownGuard, register_console_handler
from .browser import extract_searches, extract_full_history
from .categorizer import is_productive, get_category_emoji, get_app_role
from .focus import FocusMonitor

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

@click.group(invoke_without_command=True)
@click.version_option(version="2.0.0", prog_name="TraceCLI")
@click.pass_context
def main(ctx):
    """TraceCLI — The terminal's black box for your digital life.

    A privacy-first activity monitor that tracks window usage, memory/CPU,
    browser history, and productivity — all stored locally in SQLite.
    No cloud. No accounts. No tracking.
    """
    if ctx.invoked_subcommand is None:
        show_dashboard()


def show_dashboard():
    """Display the daily dashboard."""
    print_banner()
    db.init_db()
    today = date.today()

    # Fetch Data
    stats = db.get_daily_stats(today)
    total = stats["total_seconds"] if stats else 0
    total = stats["total_seconds"] if stats else 0
    prod = stats["productive_seconds"] if stats else 0
    
    # Calculate score (fallback if DB doesn't have it stored)
    fallback_score = (prod / total * 100) if total > 0 else 0
    score = stats.get("score", fallback_score) if stats else 0
    
    top_app = stats["top_app"] if stats else "None"

    # Fetch System Status
    auto_info = autostart_mod.get_autostart_info()
    auto_status = "Enabled" if auto_info["enabled"] else "Disabled"
    auto_icon = "🟢" if auto_info["enabled"] else "⚪"

    # Determine styles
    score_style = "green" if score >= 70 else "yellow" if score >= 40 else "red"
    bar_len = int(score / 5)
    bar = "█" * bar_len + "░" * (20 - bar_len)

    # Build Dashboard Panel
    dashboard_text = Text()
    dashboard_text.append(f"\n📅 {today.strftime('%A, %B %d, %Y')}\n\n", style="bold white")
    
    dashboard_text.append(f"  ⏱️  Total Tracked:    ", style="dim")
    dashboard_text.append(f"{format_duration(total)}\n", style="bright_cyan bold")
    
    dashboard_text.append(f"  🧠 Productive Time:  ", style="dim")
    dashboard_text.append(f"{format_duration(prod)}\n", style="green bold")
    
    dashboard_text.append(f"  🏆 Top App:          ", style="dim")
    dashboard_text.append(f"{top_app}\n", style="white")
    
    dashboard_text.append(f"  🚀 Auto-Start:       ", style="dim")
    dashboard_text.append(f"{auto_icon} {auto_status}\n\n", style="white")

    dashboard_text.append(f"  Productivity Score:\n  [{score_style}]{bar}[/{score_style}] {score:.0f}%\n", style="bold")

    console.print(
        Panel(
            dashboard_text,
            title="📊 Daily Summary",
            border_style="bright_blue",
            box=box.ROUNDED,
            expand=False,
            padding=(1, 2),
        )
    )

    # Quick Commands
    console.print("\n[dim]Available Commands:[/dim]")
    grid = Table.grid(padding=(0, 2))
    grid.add_column(style="bold cyan")
    grid.add_column(style="dim")
    
    grid.add_row("tracecli start", "Start activity tracking")
    grid.add_row("tracecli live", "View live activity feed")
    grid.add_row("tracecli report", "Detailed daily report")
    grid.add_row("tracecli timeline", "Visual daily timeline")
    grid.add_row("tracecli stats", "Daily productivity stats")
    grid.add_row("tracecli heatmap", "Productivity heatmap graph")
    grid.add_row("tracecli focus", "Start focus session")
    grid.add_row("tracecli insights", "Get AI-powered insights")
    grid.add_row("tracecli app", "Deep analytics for an app")
    grid.add_row("tracecli urls", "Browser history & domains")
    grid.add_row("tracecli searches", "Search query history")
    grid.add_row("tracecli system", "System resource overview")
    grid.add_row("tracecli ask", "Ask AI about your data")
    grid.add_row("tracecli status", "CLI and Database status")
    
    console.print(Panel(grid, border_style="dim", box=box.MINIMAL))
    console.print("[dim]Use [bold white]tracecli --help[/bold white] for more options.[/dim]")
    console.print()


# ── START Command ──────────────────────────────────────────────────────────

@main.command()
@click.option("--poll-interval", default=1.0, help="Polling interval in seconds")
@click.option("--min-duration", default=2.0, help="Minimum activity duration to log (seconds)")
@click.option("--sync-searches", default=300, help="Browser search sync interval (seconds)")
@click.option("--snapshot-interval", default=30, help="System snapshot interval (seconds)")
@click.option("--background", "-b", is_flag=True, help="Run silently in background (no console window)")
def start(poll_interval, min_duration, sync_searches, snapshot_interval, background):
    """Start background activity tracking with live dashboard."""
    if background:
        # Check if autostart is valid, if not (or not exists), create/fix it
        is_valid, reason = autostart_mod.is_autostart_valid()
        if not is_valid:
            console.print(f"[yellow]Auto-start configuration issue detected: {reason}[/yellow]")
            console.print("[yellow]Repairing background launcher...[/yellow]")
            autostart_mod.enable_autostart()
        
        console.print(f"[green]🚀 Launching TraceCLI in background...[/green]")
        try:
            subprocess.Popen(["wscript", str(autostart_mod.VBS_PATH)], shell=False)
            console.print(f"[dim]Process started! You can now close this terminal.[/dim]")
            console.print(f"[dim]Use 'tracecli live' to verify activity.[/dim]")
        except Exception as e:
            console.print(f"[red]Failed to launch background process: {e}[/red]")
        return

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

                # Periodically update aggregated stats (every ~60s)
                if int(session_dur) % 60 == 0:
                    try:
                        db.upsert_daily_stats()
                        db.upsert_app_usage_history()
                    except Exception:
                        pass

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
    """Show detailed activity report for a day."""
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
    """Show a visual timeline of your day."""
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
    """Show extracted search queries."""
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
    """Show daily productivity stats."""
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
    """Show live activity feed (read-only, tracker must be running)."""
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
    """Export activity data to CSV or JSON."""
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
    """Deep analytics drill-down for a specific application.

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
    """Show system resource overview — memory, CPU, and all running apps."""
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
    """Show full browser URL history with domain breakdown."""
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
    """Show TraceCLI status and database info."""
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
            status_style = "bold green" if info["valid"] else "bold yellow"
            status_text = "✅ Enabled" if info["valid"] else "⚠️ Invalid/Legacy"
            status_table.add_row("Status", f"[{status_style}]{status_text}[/{status_style}]")
            if not info["valid"]:
                status_table.add_row("Reason", f"[yellow]{info['reason']}[/yellow]")
        else:
            status_table.add_row("Status", "[dim]❌ Disabled[/dim]")

        status_table.add_row("Registry", f'{info["registry_path"]}\\{info["registry_value"]}')
        status_table.add_row("VBS Script", info["vbs_path"])
        status_table.add_row("VBS Exists", "✅" if info["vbs_exists"] else "❌")

        if info.get("command"):
            status_table.add_row("Command", info["command"])

        console.print()
        console.print(Panel(
            status_table,
            title="[bold]TraceCLI Auto-Start[/bold]",
            border_style="bright_cyan",
        ))
        console.print()



# ── AI Command ─────────────────────────────────────────────────────────────

@main.command()
@click.argument("question")
def ask(question):
    """Ask AI about your activity data."""
    from . import ai
    ai.handle_ask(question)


# ── Config Command ─────────────────────────────────────────────────────────

@main.command()
@click.option("--key", help="Set AI API Key")
@click.option("--provider", type=click.Choice(["gemini", "openai", "claude"]), help="Set AI Provider")
@click.option("--remove-key", is_flag=True, help="Remove the current AI API Key")
def config(key, provider, remove_key):
    """Configure AI settings."""
    from . import config as cfg
    
    if key:
        cfg.set_ai_key(key)
        console.print(f"[green]API Key updated![/green]")
        
    if remove_key:
        cfg.set_ai_key("")
        console.print(f"[yellow]API Key removed![/yellow]")
        
    if provider:
        cfg.set_ai_provider(provider)
        console.print(f"[green]Provider set to {provider}![/green]")
        
    if not key and not provider and not remove_key:
        # Show current config
        p, k, m = cfg.get_ai_config()
        mask_key = k[:4] + "..." + k[-4:] if len(k) > 8 else "Not Set"
        console.print(f"\n[bold]Current Configuration:[/bold]")
        console.print(f"  Provider: [cyan]{p}[/cyan]")
        console.print(f"  API Key:  [dim]{mask_key}[/dim]")
        
        config_path = cfg.CONFIG_PATH
        console.print(f"\n[dim]Config file: {config_path}[/dim]")
        console.print()


# ── Insights Command ──────────────────────────────────────────────────────

@main.command()
@click.option("--days", "-d", default=7, help="Number of days to analyze (default: 7)")
def insights(days):
    """AI-powered productivity digest and coaching insights."""
    db.init_db()

    from . import config as cfg
    from .ai import generate_weekly_digest

    provider, api_key, model = cfg.get_ai_config()
    if not api_key:
        console.print("\n[red]No API key configured. Run: tracecli config --key YOUR_KEY[/red]")
        console.print("[dim]Supports: gemini, openai, claude[/dim]\n")
        return

    console.print()
    console.print(Panel(
        f"[bold bright_white]🧠 AI Productivity Insights[/bold bright_white]\n"
        f"[dim]Analyzing the past {days} days with {provider}...[/dim]",
        border_style="bright_cyan",
        expand=False,
    ))

    with console.status("[bright_cyan]Generating your personalized digest...[/bright_cyan]"):
        digest = generate_weekly_digest(days)

    if not digest:
        console.print("\n[yellow]Could not generate insights. Check your API key and try again.[/yellow]\n")
        return

    console.print()
    console.print(Panel(
        digest,
        title="[bold bright_white]📊 Your Productivity Digest[/bold bright_white]",
        border_style="bright_green",
        padding=(1, 2),
    ))
    console.print()


# ── Focus Command ─────────────────────────────────────────────────────────

@main.command()
@click.option("--duration", "-d", default=25, help="Focus duration in minutes (default: 25)")
@click.option("--goal", "-g", default="", help="Label for this focus session")
def focus(duration, goal):
    """Start a Pomodoro-style focus session with distraction detection."""
    db.init_db()

    console.print()
    console.print(Panel(
        f"[bold bright_white]🎯 Focus Mode[/bold bright_white]\n"
        f"[dim]Duration: {duration} min{' | Goal: ' + goal if goal else ''}[/dim]",
        border_style="bright_magenta",
        expand=False,
    ))

    distraction_alerts = []

    def on_distraction(app, title, category):
        emoji = get_category_emoji(category)
        alert = f"{emoji} Distraction: {app} — {truncate(title, 40)}"
        distraction_alerts.append(alert)

    def on_complete(session):
        pass  # Handled below

    monitor = FocusMonitor(
        target_minutes=duration,
        goal_label=goal,
        poll_interval=1.0,
        on_distraction=on_distraction,
        on_complete=on_complete,
    )

    monitor.start()
    console.print("[dim]Press Ctrl+C to end the session early.[/dim]\n")

    try:
        with Live(console=console, refresh_per_second=1) as live:
            while monitor._running:
                session = monitor.session
                if not session:
                    time.sleep(0.5)
                    continue

                remaining = session.remaining_seconds
                mins, secs = divmod(int(remaining), 60)
                elapsed = session.focused_seconds + session.distracted_seconds
                elapsed_mins, elapsed_secs = divmod(int(elapsed), 60)

                # Build the live display
                focus_text = Text()

                # Timer
                focus_text.append(f"  ⏱  ", style="bold bright_cyan")
                focus_text.append(f"{mins:02d}:{secs:02d}", style="bold bright_white")
                focus_text.append(f" remaining", style="dim")
                focus_text.append(f"   ({elapsed_mins:02d}:{elapsed_secs:02d} elapsed)\n", style="dim")

                # Score bar
                score = session.focus_score
                score_color = "green" if score >= 80 else "yellow" if score >= 60 else "red"
                bar_len = 30
                filled = int(score / 100 * bar_len)
                bar = "█" * filled + "░" * (bar_len - filled)
                focus_text.append(f"  📊 Focus: ", style="dim")
                focus_text.append(f"{bar} {score:.0f}%\n", style=score_color)

                # Interruptions
                focus_text.append(f"  ⚡ Interruptions: ", style="dim")
                int_count = len(session.interruptions)
                int_color = "green" if int_count == 0 else "yellow" if int_count <= 3 else "red"
                focus_text.append(f"{int_count}\n", style=f"bold {int_color}")

                # Recent distraction alerts
                if distraction_alerts:
                    focus_text.append(f"\n")
                    for alert in distraction_alerts[-3:]:
                        focus_text.append(f"  ⚠  {alert}\n", style="bold red")

                panel = Panel(
                    focus_text,
                    title="[bold bright_magenta]🎯 Focus Mode Active[/bold bright_magenta]",
                    border_style="bright_magenta",
                    expand=False,
                    width=60,
                )
                live.update(panel)
                time.sleep(1)

    except KeyboardInterrupt:
        pass
    finally:
        session = monitor.stop()

    if session:
        # Final summary
        console.print()
        score = session.focus_score
        score_color = "green" if score >= 80 else "yellow" if score >= 60 else "red"

        grade = "🏆 Excellent!" if score >= 90 else "✅ Good" if score >= 70 else "⚠️ Needs work" if score >= 50 else "❌ Too many distractions"

        summary_table = Table(show_header=False, box=None, padding=(0, 2))
        summary_table.add_column(style="dim")
        summary_table.add_column(style="bold")

        summary_table.add_row("Duration", format_duration(session.total_seconds))
        summary_table.add_row("Focused time", format_duration(session.focused_seconds))
        summary_table.add_row("Distracted time", format_duration(session.distracted_seconds))
        summary_table.add_row("Interruptions", str(len(session.interruptions)))
        summary_table.add_row("Focus Score", f"[{score_color}]{score:.1f}%[/{score_color}]")
        summary_table.add_row("Grade", grade)
        if goal:
            summary_table.add_row("Goal", goal)

        console.print(Panel(
            summary_table,
            title="[bold bright_white]📋 Session Complete[/bold bright_white]",
            border_style="bright_cyan",
            expand=False,
        ))
        console.print()


@main.command(name="focus-history")
@click.option("--date", "-d", "date_str", default=None, help="Filter by date (YYYY-MM-DD)")
@click.option("--limit", "-n", default=10, help="Number of sessions to show")
def focus_history(date_str, limit):
    """View past focus sessions."""
    db.init_db()

    target_date = parse_date(date_str) if date_str else None
    sessions = db.query_focus_sessions(target_date, limit)

    if not sessions:
        console.print("\n[yellow]No focus sessions found. Try: tracecli focus[/yellow]\n")
        return

    # Stats
    stats = db.get_focus_stats()

    console.print()
    console.print(Panel(
        f"[bold bright_white]📜 Focus History[/bold bright_white]\n"
        f"[dim]{stats['total_sessions']} sessions | "
        f"Avg score: {stats['avg_focus_score']:.1f}% | "
        f"Best: {stats['best_score']:.1f}%[/dim]",
        border_style="bright_magenta",
        expand=False,
    ))

    table = Table(box=box.SIMPLE_HEAVY)
    table.add_column("Date", style="bright_cyan")
    table.add_column("Time", style="dim")
    table.add_column("Target", justify="right")
    table.add_column("Focused", justify="right")
    table.add_column("Score", justify="right")
    table.add_column("Interruptions", justify="center")
    table.add_column("Goal", style="dim")

    for s in sessions:
        score = s["focus_score"]
        score_color = "green" if score >= 80 else "yellow" if score >= 60 else "red"
        start = format_time(s["start_time"])
        date_part = s["start_time"][:10] if s["start_time"] else ""

        table.add_row(
            date_part,
            start,
            f"{s['target_minutes']}m",
            format_duration(s["actual_focus_seconds"]),
            f"[{score_color}]{score:.0f}%[/{score_color}]",
            str(s["interruption_count"]),
            truncate(s["goal_label"], 20) if s["goal_label"] else "—",
        )

    console.print(table)
    console.print()


# ── Heatmap Command ────────────────────────────────────────────────────────

@main.command()
@click.option("--weeks", default=20, help="Number of weeks to display (default: 20)")
@click.option("--day", "-d", "date_str", is_flag=False, flag_value="today", help="Show hourly heatmap for a specific day (default: today)")
@click.option("--app", "-a", multiple=True, help="Filter by specific apps (for --day view)")
def heatmap(weeks, date_str, app):
    """Display a productivity heatmap (weekly or daily hourly)."""
    db.init_db()

    if date_str:
        target = parse_date(None if date_str == "today" else date_str)
        _show_daily_heatmap(target, list(app) if app else None)
        return

    heatmap_data = db.get_productivity_heatmap_data(weeks)
    streak_info = db.get_streak_info()

    # Build date → score lookup
    score_map = {}
    for entry in heatmap_data:
        score_map[entry["date"]] = entry["score"]

    # Color mapping: score → Rich color
    def score_color(score, has_data):
        if not has_data:
            return "bright_black"
        if score >= 80:
            return "green"
        elif score >= 60:
            return "bright_green"
        elif score >= 40:
            return "yellow"
        elif score >= 20:
            return "dark_orange"
        else:
            return "red"

    # Calculate date range
    today = date.today()
    # Start from the beginning of the week (Monday) for alignment
    start = today - timedelta(days=today.weekday(), weeks=weeks - 1)

    # Header
    console.print()
    console.print(Panel(
        "[bold bright_white]📊 Productivity Heatmap[/bold bright_white]",
        border_style="bright_cyan",
        expand=False,
    ))

    # Day-of-week labels
    day_labels = ["Mon", "   ", "Wed", "   ", "Fri", "   ", "Sun"]

    # Generate the grid: 7 rows (Mon–Sun) × N columns (weeks)
    total_days = weeks * 7
    grid_dates = []
    for i in range(total_days):
        d = start + timedelta(days=i)
        grid_dates.append(d)

    # Build month labels row
    month_text = Text("    ")  # Indent for day labels
    prev_month = -1
    for w in range(weeks):
        col_date = start + timedelta(weeks=w)
        if col_date.month != prev_month:
            month_label = col_date.strftime("%b")
            month_text.append(month_label)
            # Pad remaining space for this month column
            remaining = 2 - len(month_label) + 1
            if remaining > 0:
                month_text.append(" " * remaining)
            prev_month = col_date.month
        else:
            month_text.append("  ")
    console.print(month_text)

    # Build the heatmap rows (one per day of week)
    for day_idx in range(7):
        row = Text()
        row.append(f"{day_labels[day_idx]} ", style="dim")
        for w in range(weeks):
            cell_idx = w * 7 + day_idx
            if cell_idx < len(grid_dates):
                d = grid_dates[cell_idx]
                if d > today:
                    row.append("  ", style="bright_black")
                else:
                    date_str = d.isoformat()
                    has_data = date_str in score_map
                    score = score_map.get(date_str, 0)
                    color = score_color(score, has_data)
                    row.append("█ ", style=color)
            else:
                row.append("  ")
        console.print(row)

    # Legend
    console.print()
    legend = Text("    Less ")
    legend.append("█ ", style="bright_black")
    legend.append("█ ", style="red")
    legend.append("█ ", style="dark_orange")
    legend.append("█ ", style="yellow")
    legend.append("█ ", style="bright_green")
    legend.append("█ ", style="green")
    legend.append(" More")
    console.print(legend)

    # Streak info
    console.print()
    streak_text = Text("    ")
    streak_text.append(f"🔥 Current streak: ", style="dim")
    streak_text.append(f"{streak_info['current_streak']} days", style="bold bright_yellow")
    streak_text.append(f"   🏆 Longest: ", style="dim")
    streak_text.append(f"{streak_info['longest_streak']} days", style="bold bright_cyan")
    streak_text.append(f"   📅 Total: ", style="dim")
    streak_text.append(f"{streak_info['total_days_tracked']} days tracked", style="bold")
    console.print(streak_text)
    console.print()


def _show_daily_heatmap(target_date: date, apps: list[str] = None):
    """Display an hourly usage heatmap for a specific day."""
    data = db.get_daily_app_usage_by_hour(target_date, apps)
    
    if not data:
        console.print(f"\n[yellow]No activity data for {target_date}.[/yellow]\n")
        return

    # Pivot data: App Name -> [duration per hour (0-23)]
    usage_map = {}
    hours_tracked = set()
    for entry in data:
        app = entry["app_name"]
        hour = int(entry["hour"])
        duration = entry["total_seconds"]
        if app not in usage_map:
            usage_map[app] = [0] * 24
        usage_map[app][hour] = duration
        hours_tracked.add(hour)

    # Sort apps by total duration
    sorted_apps = sorted(usage_map.items(), key=lambda x: sum(x[1]), reverse=True)[:15]

    console.print()
    console.print(Panel(
        f"[bold bright_white]📊 Hourly Activity Heatmap — {target_date}[/bold bright_white]",
        border_style="bright_cyan",
        expand=False,
    ))

    # Header (Hours)
    header = Text(" " * 22)
    for h in range(24):
        if h in hours_tracked:
            header.append(f"{h:02d} ", style="dim")
        else:
            header.append(".. ", style="bright_black")
    console.print(header)

    def duration_color(seconds):
        if seconds == 0: return "bright_black"
        if seconds > 1800: return "green"   # > 30m
        if seconds > 900:  return "bright_green" # > 15m
        if seconds > 300:  return "yellow"  # > 5m
        return "red"

    for app_name, hourly_stats in sorted_apps:
        row = Text(f"{truncate(app_name, 20):<20} ", style="bold")
        for seconds in hourly_stats:
            color = duration_color(seconds)
            char = "█ " if seconds > 0 else "░ "
            row.append(char, style=color)
        console.print(row)

    console.print()
    console.print("[dim]  Legend: [red]█[/red] <5m  [yellow]█[/yellow] <15m  [bright_green]█[/bright_green] <30m  [green]█[/green] >30m[/dim]")
    console.print()


# ── Timeline Command ──────────────────────────────────────────────────────

@main.command()
@click.option("--date", "-d", "date_str", default=None, help="Date (YYYY-MM-DD)")
def timeline(date_str):
    """View a chronological timeline of your activities."""
    target = parse_date(date_str)
    db.init_db()

    activities = db.get_daily_activity_timeline(target)
    if not activities:
        console.print(f"\n[yellow]No activities found for {target}.[/yellow]\n")
        return

    console.print()
    console.print(Panel(
        f"[bold bright_white]⏳ Activity Timeline — {target}[/bold bright_white]",
        border_style="bright_magenta",
        expand=False,
    ))

    table = Table(box=box.SIMPLE_HEAVY, show_header=True)
    table.add_column("Time", style="dim", width=12)
    table.add_column("Duration", justify="right", width=10)
    table.add_column("Application", style="bold cyan", width=20)
    table.add_column("Activity / Window Title", style="white")

    for act in activities:
        start = format_time(act["start_time"])
        duration = format_duration(act["duration_seconds"])
        app = act["app_name"]
        title = truncate(act["window_title"], 60)
        
        table.add_row(start, duration, app, title)

    console.print(table)
    console.print()


# ── App Distribution Command ──────────────────────────────────────────────

@main.command(name="app-dist")
@click.argument("app_name")
@click.option("--days", "-n", default=30, help="Analyze last N days")
def app_distribution(app_name, days):
    """View the typical usage distribution of an app over the day."""
    db.init_db()
    data = db.get_app_usage_distribution(app_name, days)

    if not data:
        console.print(f"\n[yellow]No data found for [bold]{app_name}[/bold] in the last {days} days.[/yellow]\n")
        return

    # Map hours
    hours_map = {int(d["hour"]): d["avg_seconds"] for d in data}
    max_avg = max(hours_map.values()) if hours_map else 1

    console.print()
    console.print(Panel(
        f"[bold bright_white]📈 '{app_name}' Usage Distribution (Avg over {days} days)[/bold bright_white]",
        border_style="bright_yellow",
        expand=False,
    ))

    def get_color(val):
        pct = val / max_avg
        if pct > 0.8: return "green"
        if pct > 0.5: return "bright_green"
        if pct > 0.2: return "yellow"
        if pct > 0:   return "red"
        return "bright_black"

    # Heatmap row
    row = Text("    ")
    for h in range(24):
        avg = hours_map.get(h, 0)
        color = get_color(avg)
        char = "█ " if avg > 0 else "░ "
        row.append(char, style=color)
    console.print(row)

    # Hour labels row
    labels = Text("    ")
    for h in range(24):
        labels.append(f"{h:02d} ", style="dim")
    console.print(labels)

    console.print()
    console.print(f"  [dim]Peak usage at: [bold bright_white]{max(hours_map, key=hours_map.get):02d}:00[/bold bright_white][/dim]")
    console.print()


# ── Week Command ──────────────────────────────────────────────────────────

@main.command()
def week():
    """Show a quick weekly productivity summary."""
    db.init_db()

    stats_list = db.get_stats_range(7)

    if not stats_list:
        console.print("\n[yellow]No data for the past week. Start tracking first![/yellow]\n")
        return

    total_seconds = sum(s["total_seconds"] for s in stats_list)
    productive_seconds = sum(s["productive_seconds"] for s in stats_list)
    distraction_seconds = sum(s["distraction_seconds"] for s in stats_list)
    avg_score = round((productive_seconds / total_seconds) * 100) if total_seconds > 0 else 0

    # Find best and worst days
    best = max(stats_list, key=lambda s: s["productive_seconds"])
    worst = min(stats_list, key=lambda s: (s["productive_seconds"] / s["total_seconds"]) if s["total_seconds"] > 0 else 1)

    console.print()
    console.print(Panel(
        "[bold bright_white]📅 Weekly Summary[/bold bright_white]",
        border_style="bright_cyan",
        expand=False,
    ))

    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column(style="dim")
    table.add_column(style="bold")

    table.add_row("Total tracked time", format_duration(total_seconds))
    table.add_row("Productive time", format_duration(productive_seconds))
    table.add_row("Distraction time", format_duration(distraction_seconds))
    table.add_row("Avg. productivity", f"{avg_score}%")
    table.add_row("Days tracked", f"{len(stats_list)}")
    table.add_row("Best day", f"{best['date']} ({format_duration(best['productive_seconds'])} productive)")
    table.add_row("Worst day", f"{worst['date']}")

    console.print(table)
    console.print()


# ── Entry Point ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    main()

