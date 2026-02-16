"""
TraceCLI Auto-Start Manager
~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Creates/removes a Windows Task Scheduler task that silently launches
TraceCLI on user logon using a VBS wrapper (no visible console window).
"""

import os
import subprocess
import shutil
from pathlib import Path


# ── Configuration ──────────────────────────────────────────────────────────

TASK_NAME = "TraceCLI_AutoStart"
DATA_DIR = Path.home() / ".tracecli"
VBS_PATH = DATA_DIR / "silent_start.vbs"

# The VBS script that launches tracecli silently (no console window)
VBS_CONTENT = '''
' TraceCLI Silent Launcher
' Launches tracecli start in background with no visible console window.
Set WshShell = CreateObject("WScript.Shell")
WshShell.Run "tracecli start", 0, False
Set WshShell = Nothing
'''.strip()


# ── Public API ─────────────────────────────────────────────────────────────

def enable_autostart() -> tuple[bool, str]:
    """
    Enable TraceCLI to start automatically when the user logs in.

    Creates:
      1. A VBS launcher script at ~/.tracecli/silent_start.vbs
      2. A Windows Task Scheduler task that runs it at logon

    Returns:
        (success, message)
    """
    # Verify tracecli is installed
    tracecli_path = shutil.which("tracecli")
    if not tracecli_path:
        return False, (
            "tracecli command not found in PATH.\n"
            "Install with: pip install -e . (in the project directory)"
        )

    # Create data directory
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Write the VBS launcher script
    VBS_PATH.write_text(VBS_CONTENT, encoding="utf-8")

    # Remove existing task if present (clean re-create)
    _delete_task()

    # Create the Task Scheduler task
    # /SC ONLOGON = trigger at user logon
    # /RL HIGHEST = run with highest available privileges
    # /F = force create (overwrite if exists)
    # /TR = the command to run (wscript.exe with our VBS)
    cmd = [
        "schtasks", "/Create",
        "/TN", TASK_NAME,
        "/SC", "ONLOGON",
        "/TR", f'wscript.exe "{VBS_PATH}"',
        "/RL", "HIGHEST",
        "/F",
        "/IT",  # Interactive only (only when user is logged in)
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=15,
        )

        if result.returncode == 0:
            return True, (
                f"Auto-start enabled!\n"
                f"  Task: {TASK_NAME}\n"
                f"  Script: {VBS_PATH}\n"
                f"TraceCLI will start silently on next login."
            )
        else:
            error = result.stderr.strip() or result.stdout.strip()
            return False, f"Failed to create scheduled task: {error}"

    except subprocess.TimeoutExpired:
        return False, "Timed out creating scheduled task."
    except FileNotFoundError:
        return False, "schtasks.exe not found. Windows Task Scheduler may not be available."
    except Exception as e:
        return False, f"Unexpected error: {e}"


def disable_autostart() -> tuple[bool, str]:
    """
    Disable TraceCLI auto-start.

    Removes:
      1. The Windows Task Scheduler task
      2. The VBS launcher script

    Returns:
        (success, message)
    """
    task_deleted = _delete_task()

    # Remove VBS file
    vbs_deleted = False
    try:
        if VBS_PATH.exists():
            VBS_PATH.unlink()
            vbs_deleted = True
    except Exception:
        pass

    if task_deleted or vbs_deleted:
        return True, "Auto-start disabled. Task and launcher removed."
    else:
        return True, "Auto-start was not enabled (nothing to remove)."


def is_autostart_enabled() -> bool:
    """Check if the auto-start scheduled task exists."""
    try:
        result = subprocess.run(
            ["schtasks", "/Query", "/TN", TASK_NAME],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0
    except Exception:
        return False


def get_autostart_info() -> dict:
    """Get detailed info about the auto-start configuration."""
    enabled = is_autostart_enabled()
    vbs_exists = VBS_PATH.exists()

    info = {
        "enabled": enabled,
        "task_name": TASK_NAME,
        "vbs_path": str(VBS_PATH),
        "vbs_exists": vbs_exists,
    }

    if enabled:
        try:
            result = subprocess.run(
                ["schtasks", "/Query", "/TN", TASK_NAME, "/V", "/FO", "LIST"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                for line in result.stdout.splitlines():
                    line = line.strip()
                    if line.startswith("Status:"):
                        info["status"] = line.split(":", 1)[1].strip()
                    elif line.startswith("Next Run Time:"):
                        info["next_run"] = line.split(":", 1)[1].strip()
                    elif line.startswith("Last Run Time:"):
                        info["last_run"] = line.split(":", 1)[1].strip()
        except Exception:
            pass

    return info


# ── Internal Helpers ───────────────────────────────────────────────────────

def _delete_task() -> bool:
    """Delete the scheduled task if it exists. Returns True if deleted."""
    try:
        result = subprocess.run(
            ["schtasks", "/Delete", "/TN", TASK_NAME, "/F"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0
    except Exception:
        return False
