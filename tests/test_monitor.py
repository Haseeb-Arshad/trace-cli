"""Tests for the System Monitor module."""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime

from src.monitor import (
    get_system_info,
    get_running_processes,
    get_process_resource,
    SystemMonitor,
)


class TestGetSystemInfo:
    """Test system info retrieval."""

    @patch("src.monitor.psutil")
    def test_returns_dict_with_expected_keys(self, mock_psutil):
        mock_psutil.virtual_memory.return_value = MagicMock(
            total=16 * 1024**3, used=8 * 1024**3, percent=50.0
        )
        mock_psutil.cpu_percent.return_value = 25.0
        mock_psutil.cpu_count.return_value = 8
        mock_psutil.disk_usage.return_value = MagicMock(
            total=500 * 1024**3, used=200 * 1024**3, percent=40.0
        )

        info = get_system_info()
        assert "total_ram_gb" in info
        assert "used_ram_gb" in info
        assert "ram_percent" in info
        assert "cpu_percent" in info
        assert "cpu_count" in info
        assert "disk_total_gb" in info
        assert info["total_ram_gb"] == 16.0
        assert info["ram_percent"] == 50.0
        assert info["cpu_count"] == 8


class TestGetRunningProcesses:
    """Test process enumeration."""

    @patch("src.monitor.psutil.process_iter")
    def test_returns_sorted_by_memory(self, mock_iter):
        mock_iter.return_value = [
            MagicMock(info={
                "pid": 1, "name": "small.exe",
                "memory_info": MagicMock(rss=10 * 1024 * 1024),
                "cpu_percent": 5.0, "status": "running", "num_threads": 2,
            }),
            MagicMock(info={
                "pid": 2, "name": "big.exe",
                "memory_info": MagicMock(rss=500 * 1024 * 1024),
                "cpu_percent": 15.0, "status": "running", "num_threads": 10,
            }),
        ]

        procs = get_running_processes(sort_by="memory")
        assert len(procs) == 2
        assert procs[0]["app_name"] == "big.exe"
        assert procs[0]["memory_mb"] > procs[1]["memory_mb"]

    @patch("src.monitor.psutil.process_iter")
    def test_handles_access_denied(self, mock_iter):
        from psutil import AccessDenied
        proc = MagicMock()
        proc.info.__getitem__ = MagicMock(side_effect=AccessDenied(1))
        type(proc).info = property(lambda self: (_ for _ in ()).throw(AccessDenied(1)))
        mock_iter.return_value = [proc]

        procs = get_running_processes()
        assert isinstance(procs, list)


class TestSystemMonitor:
    """Test the SystemMonitor class."""

    def test_init_defaults(self):
        monitor = SystemMonitor()
        assert monitor.interval == 30.0
        assert monitor.top_n == 50
        assert monitor.total_snapshots == 0
        assert not monitor._running

    def test_start_and_stop(self):
        monitor = SystemMonitor(interval=100)
        monitor.start()
        assert monitor._running
        monitor.stop()
        assert not monitor._running

    def test_get_latest_returns_none_before_start(self):
        monitor = SystemMonitor()
        assert monitor.get_latest_system_info() is None
        assert monitor.get_latest_top_processes() == []


class TestGetProcessResource:
    """Test individual process resource lookup."""

    @patch("src.monitor.psutil.Process")
    def test_returns_resource_dict(self, mock_proc_class):
        mock_proc = MagicMock()
        mock_proc.memory_info.return_value = MagicMock(rss=256 * 1024 * 1024)
        mock_proc.cpu_percent.return_value = 12.5
        mock_proc.num_threads.return_value = 8
        mock_proc.status.return_value = "running"
        mock_proc_class.return_value = mock_proc

        result = get_process_resource(1234)
        assert result is not None
        assert result["memory_mb"] == 256.0
        assert result["cpu_percent"] == 12.5
        assert result["num_threads"] == 8

    @patch("src.monitor.psutil.Process")
    def test_returns_none_for_missing_process(self, mock_proc_class):
        from psutil import NoSuchProcess
        mock_proc_class.side_effect = NoSuchProcess(99999)
        result = get_process_resource(99999)
        assert result is None
