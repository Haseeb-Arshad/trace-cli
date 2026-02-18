"""
TraceCLI System Monitor
~~~~~~~~~~~~~~~~~~~~~~~
Background system-wide process monitor that captures resource usage
(memory, CPU, threads) for ALL running processes at regular intervals.
"""

import time
import threading
from datetime import datetime
from typing import Optional, Callable

import psutil

from . import database as db


# ── Data Helpers ───────────────────────────────────────────────────────────

def get_system_info() -> dict:
    """Get current system-wide resource stats."""
    mem = psutil.virtual_memory()
    cpu = psutil.cpu_percent(interval=0)
    disk = psutil.disk_usage("/")

    return {
        "total_ram_gb": round(mem.total / (1024 ** 3), 2),
        "used_ram_gb": round(mem.used / (1024 ** 3), 2),
        "ram_percent": mem.percent,
        "cpu_percent": cpu,
        "cpu_count": psutil.cpu_count(),
        "disk_total_gb": round(disk.total / (1024 ** 3), 2),
        "disk_used_gb": round(disk.used / (1024 ** 3), 2),
        "disk_percent": disk.percent,
    }


def get_running_processes(sort_by: str = "memory") -> list[dict]:
    """
    Get a snapshot of all running processes with resource info.

    Args:
        sort_by: "memory" or "cpu"

    Returns:
        List of dicts with process info, sorted by the specified metric.
    """
    processes = []
    for proc in psutil.process_iter(
        ["pid", "name", "memory_info", "cpu_percent", "status", "num_threads"]
    ):
        try:
            info = proc.info
            memory_mb = (info["memory_info"].rss / (1024 * 1024)) if info.get("memory_info") else 0
            processes.append({
                "pid": info["pid"],
                "app_name": info["name"] or "Unknown",
                "memory_mb": round(memory_mb, 2),
                "cpu_percent": round(info.get("cpu_percent", 0) or 0, 2),
                "status": info.get("status", "unknown"),
                "num_threads": info.get("num_threads", 0) or 0,
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

    # Sort by the specified metric
    sort_key = "memory_mb" if sort_by == "memory" else "cpu_percent"
    processes.sort(key=lambda p: p[sort_key], reverse=True)
    return processes


def get_process_resource(pid: int) -> Optional[dict]:
    """Get memory and CPU info for a specific PID."""
    try:
        proc = psutil.Process(pid)
        mem_info = proc.memory_info()
        cpu = proc.cpu_percent(interval=0)
        return {
            "memory_mb": round(mem_info.rss / (1024 * 1024), 2),
            "cpu_percent": round(cpu, 2),
            "num_threads": proc.num_threads(),
            "status": proc.status(),
        }
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return None


# ── System Monitor Class ──────────────────────────────────────────────────

class SystemMonitor:
    """
    Background monitor that snapshots ALL running processes at regular
    intervals and stores them in the database.

    Usage:
        monitor = SystemMonitor(interval=30)
        monitor.start()
        # ... later ...
        monitor.stop()
    """

    def __init__(
        self,
        interval: float = 30.0,
        top_n: int = 50,
    ):
        """
        Args:
            interval: Seconds between snapshots.
            top_n: Only capture top N processes by memory to reduce DB size.
        """
        self.interval = interval
        self.top_n = top_n

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        # Stats
        self.total_snapshots = 0
        self.last_snapshot_time: Optional[datetime] = None
        self._latest_system_info: Optional[dict] = None
        self._latest_top_processes: list[dict] = []

    def start(self):
        """Start the background monitoring thread."""
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(
            target=self._monitor_loop,
            name="TraceCLI-SystemMonitor",
            daemon=True,
        )
        self._thread.start()

    def stop(self):
        """Stop the monitor."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)

    def get_latest_system_info(self) -> Optional[dict]:
        """Get the most recent system info snapshot."""
        with self._lock:
            return self._latest_system_info

    def get_latest_top_processes(self) -> list[dict]:
        """Get the most recent process list."""
        with self._lock:
            return list(self._latest_top_processes)

    # ── Internal ───────────────────────────────────────────────────────

    def _monitor_loop(self):
        """Main monitoring loop."""
        while self._running:
            try:
                self._take_snapshot()
            except Exception:
                pass
            # Use smaller sleep intervals so we can exit quickly
            for _ in range(int(self.interval)):
                if not self._running:
                    break
                time.sleep(1)

    def _take_snapshot(self):
        """Take a snapshot of all running processes."""
        now = datetime.now()
        timestamp_str = now.isoformat()

        # Get system info
        sys_info = get_system_info()

        # Get all processes
        processes = get_running_processes(sort_by="memory")

        # Update cached state
        with self._lock:
            self._latest_system_info = sys_info
            self._latest_top_processes = processes[:self.top_n]
            self.last_snapshot_time = now
            self.total_snapshots += 1

        # Store top N in database
        snapshots_to_store = []
        for proc in processes[:self.top_n]:
            snapshots_to_store.append((
                timestamp_str,
                proc["app_name"],
                proc["pid"],
                proc["memory_mb"],
                proc["cpu_percent"],
                proc["status"],
                proc["num_threads"],
            ))

        try:
            db.bulk_insert_snapshots(snapshots_to_store)
        except Exception:
            pass
