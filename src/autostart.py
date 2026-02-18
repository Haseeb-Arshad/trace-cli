"""
TraceCLI Auto-Start Manager
~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Manages TraceCLI auto-start on Windows login using two mechanisms:

1. **Registry Run key** (primary) — HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run
   - No admin rights needed, runs at user logon
   - Standard Windows mechanism for per-user startup apps

2. **VBS silent wrapper** — Launches tracecli with no visible console window

Together: Windows runs the VBS at login → VBS launches tracecli in background.
"""

import os
import shutil
import winreg
from pathlib import Path


# ── Configuration ──────────────────────────────────────────────────────────

REGISTRY_KEY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
REGISTRY_VALUE_NAME = "TraceCLI"
DATA_DIR = Path.home() / ".tracecli"
VBS_PATH = DATA_DIR / "silent_start.vbs"

# The VBS script that launches tracecli silently (no console window)
VBS_CONTENT = '''\
' TraceCLI Silent Launcher
' Launches tracecli start in background with no visible console window.
Set WshShell = CreateObject("WScript.Shell")
WshShell.Run "tracecli start", 0, False
Set WshShell = Nothing
'''


# ── Public API ─────────────────────────────────────────────────────────────

def enable_autostart() -> tuple[bool, str]:
    """
    Enable TraceCLI to start automatically when the user logs in.

    Creates:
      1. A VBS launcher script at ~/.tracecli/silent_start.vbs
      2. A Registry Run key pointing to wscript.exe + the VBS

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
    vbs_script = (
        "' TraceCLI Silent Launcher\n"
        "' Launches tracecli start in background with no visible console window.\n"
        "Set WshShell = CreateObject(\"WScript.Shell\")\n"
        f"WshShell.Run \"\"\"{tracecli_path}\"\" start\", 0, False\n"
        "Set WshShell = Nothing\n"
    )
    VBS_PATH.write_text(vbs_script, encoding="utf-8")

    # Create the Registry Run key
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            REGISTRY_KEY_PATH,
            0,
            winreg.KEY_SET_VALUE,
        )
        winreg.SetValueEx(
            key,
            REGISTRY_VALUE_NAME,
            0,
            winreg.REG_SZ,
            f'wscript.exe "{VBS_PATH}"',
        )
        winreg.CloseKey(key)

        return True, (
            f"Auto-start enabled!\n"
            f"  Registry: HKCU\\{REGISTRY_KEY_PATH}\\{REGISTRY_VALUE_NAME}\n"
            f"  Script: {VBS_PATH}\n"
            f"TraceCLI will start silently on next login."
        )

    except WindowsError as e:
        return False, f"Failed to write registry key: {e}"
    except Exception as e:
        return False, f"Unexpected error: {e}"


def disable_autostart() -> tuple[bool, str]:
    """
    Disable TraceCLI auto-start.

    Removes:
      1. The Registry Run key
      2. The VBS launcher script

    Returns:
        (success, message)
    """
    reg_deleted = _delete_registry_value()

    # Remove VBS file
    vbs_deleted = False
    try:
        if VBS_PATH.exists():
            VBS_PATH.unlink()
            vbs_deleted = True
    except Exception:
        pass

    if reg_deleted or vbs_deleted:
        return True, "Auto-start disabled. Registry key and launcher removed."
    else:
        return True, "Auto-start was not enabled (nothing to remove)."


def is_autostart_enabled() -> bool:
    """Check if the auto-start Registry Run key exists."""
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            REGISTRY_KEY_PATH,
            0,
            winreg.KEY_READ,
        )
        winreg.QueryValueEx(key, REGISTRY_VALUE_NAME)
        winreg.CloseKey(key)
        return True
    except FileNotFoundError:
        return False
    except Exception:
        return False


def is_autostart_valid() -> tuple[bool, str]:
    """
    Check if the existing auto-start configuration is valid and points
    to the current Python-based tracecli executable.

    Returns:
        (is_valid, reason)
    """
    if not is_autostart_enabled():
        return False, "Autostart is not enabled in Registry."

    if not VBS_PATH.exists():
        return False, f"VBS launcher script not found at {VBS_PATH}."

    # Check VBS content
    try:
        content = VBS_PATH.read_text(encoding="utf-8")
        current_tracecli = shutil.which("tracecli")
        
        if not current_tracecli:
            return False, "Current tracecli executable not found in PATH."

        # If it points to an NPM version (AppData\Roaming\npm), it's invalid
        if "AppData\\Roaming\\npm" in content:
            return False, "VBS script points to a legacy NPM version of tracecli."

        # If it doesn't contain the current executable path, it's invalid
        if current_tracecli.lower() not in content.lower():
            return False, f"VBS script points to a different executable path."

        return True, "Autostart configuration is valid."
    except Exception as e:
        return False, f"Failed to read/validate VBS script: {e}"


def get_autostart_info() -> dict:
    """Get detailed info about the auto-start configuration."""
    enabled = is_autostart_enabled()
    vbs_exists = VBS_PATH.exists()
    valid, reason = is_autostart_valid()

    info = {
        "enabled": enabled,
        "valid": valid,
        "reason": reason,
        "registry_path": f"HKCU\\{REGISTRY_KEY_PATH}",
        "registry_value": REGISTRY_VALUE_NAME,
        "vbs_path": str(VBS_PATH),
        "vbs_exists": vbs_exists,
    }

    if enabled:
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                REGISTRY_KEY_PATH,
                0,
                winreg.KEY_READ,
            )
            value, _ = winreg.QueryValueEx(key, REGISTRY_VALUE_NAME)
            winreg.CloseKey(key)
            info["command"] = value
        except Exception:
            pass

    return info


# ── Internal Helpers ───────────────────────────────────────────────────────

def _delete_registry_value() -> bool:
    """Delete the Registry Run value if it exists. Returns True if deleted."""
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            REGISTRY_KEY_PATH,
            0,
            winreg.KEY_SET_VALUE,
        )
        winreg.DeleteValue(key, REGISTRY_VALUE_NAME)
        winreg.CloseKey(key)
        return True
    except FileNotFoundError:
        return False
    except Exception:
        return False
