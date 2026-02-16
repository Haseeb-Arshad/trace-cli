"""
TraceCLI Shutdown Guard
~~~~~~~~~~~~~~~~~~~~~~~
Windows-specific zero-loss shutdown protection.
Creates a hidden window to intercept WM_QUERYENDSESSION / WM_ENDSESSION
and flushes all in-memory data before the OS terminates the process.
"""

import atexit
import signal
import threading
import ctypes
from typing import Optional, Callable

import win32gui
import win32con
import win32api


# ── Constants ──────────────────────────────────────────────────────────────

WM_QUERYENDSESSION = 0x0011
WM_ENDSESSION = 0x0016

WINDOW_CLASS_NAME = "TraceCLI_ShutdownGuard"


# ── Shutdown Guard ─────────────────────────────────────────────────────────

class ShutdownGuard:
    """
    Intercepts Windows shutdown/logoff signals and ensures all data is
    flushed to the database before the process terminates.

    Creates a hidden window with a custom WndProc that listens for:
      - WM_QUERYENDSESSION: Windows is about to shut down
      - WM_ENDSESSION: Shutdown confirmed
      - WM_CLOSE: Window close request

    Also registers atexit and signal handlers as fallbacks.
    """

    def __init__(self):
        self._flush_callback: Optional[Callable] = None
        self._thread: Optional[threading.Thread] = None
        self._hwnd: Optional[int] = None
        self._running = False
        self._flushed = False
        self._lock = threading.Lock()

    def start(self, flush_callback: Callable):
        """
        Start the shutdown guard.

        Args:
            flush_callback: Function to call when shutdown is detected.
                           This should save all in-memory data to disk.
        """
        self._flush_callback = flush_callback
        self._running = True

        # Register atexit handler (fallback for normal exits)
        atexit.register(self._do_flush)

        # Register signal handlers (fallback for Ctrl+C, SIGTERM)
        try:
            signal.signal(signal.SIGINT, self._signal_handler)
            signal.signal(signal.SIGTERM, self._signal_handler)
        except (OSError, ValueError):
            pass  # May fail if not on main thread

        # Start the hidden window in a background thread
        self._thread = threading.Thread(
            target=self._run_message_loop,
            name="TraceCLI-ShutdownGuard",
            daemon=False,  # Must NOT be daemon — needs to outlive main thread
        )
        self._thread.start()

    def stop(self):
        """Stop the shutdown guard and clean up."""
        self._running = False
        self._do_flush()

        # Close the hidden window to terminate the message loop
        if self._hwnd:
            try:
                win32gui.PostMessage(self._hwnd, win32con.WM_CLOSE, 0, 0)
            except Exception:
                pass

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)

    # ── Internal ───────────────────────────────────────────────────────

    def _do_flush(self):
        """Execute the flush callback exactly once."""
        with self._lock:
            if self._flushed:
                return
            self._flushed = True

        if self._flush_callback:
            try:
                self._flush_callback()
            except Exception:
                pass

    def _signal_handler(self, signum, frame):
        """Handle SIGINT/SIGTERM signals."""
        self._do_flush()
        raise SystemExit(0)

    def _run_message_loop(self):
        """Create a hidden window and run the Win32 message pump."""
        try:
            # Register the window class
            wc = win32gui.WNDCLASS()
            wc.lpfnWndProc = self._wnd_proc
            wc.lpszClassName = WINDOW_CLASS_NAME
            wc.hInstance = win32api.GetModuleHandle(None)

            try:
                class_atom = win32gui.RegisterClass(wc)
            except Exception:
                # Class may already be registered from a previous run
                pass

            # Create a hidden message-only window
            self._hwnd = win32gui.CreateWindowEx(
                0,
                WINDOW_CLASS_NAME,
                "TraceCLI Shutdown Guard",
                0,      # No visible style
                0, 0, 0, 0,
                0,      # No parent (message-only would use HWND_MESSAGE)
                0,
                wc.hInstance,
                None,
            )

            # Tell Windows we want to be notified about shutdown
            if self._hwnd:
                try:
                    # ShutdownBlockReasonCreate for Windows Vista+
                    ctypes.windll.user32.ShutdownBlockReasonCreate(
                        self._hwnd,
                        "TraceCLI is saving your activity data...",
                    )
                except Exception:
                    pass

            # Run the message pump
            while self._running:
                try:
                    # PeekMessage with a timeout to allow checking _running
                    result = win32gui.PumpWaitingMessages()
                except Exception:
                    break

                if not self._running:
                    break

                # Small sleep to avoid busy-waiting
                import time
                time.sleep(0.1)

        except Exception:
            pass

    def _wnd_proc(self, hwnd, msg, wparam, lparam):
        """Custom window procedure to intercept shutdown messages."""
        if msg == WM_QUERYENDSESSION:
            # Windows is asking: "Can I shut down?"
            # Flush data immediately, then allow shutdown
            self._do_flush()
            return True  # Allow shutdown

        elif msg == WM_ENDSESSION:
            # Shutdown is confirmed and happening now
            if wparam:
                self._do_flush()
            return 0

        elif msg == win32con.WM_CLOSE:
            # Window is being closed
            self._do_flush()
            win32gui.DestroyWindow(hwnd)
            return 0

        elif msg == win32con.WM_DESTROY:
            win32gui.PostQuitMessage(0)
            return 0

        return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)


# ── Console Control Handler ───────────────────────────────────────────────

def register_console_handler(flush_callback: Callable):
    """
    Register a Windows console control handler for Ctrl+C, Ctrl+Break,
    and console window close events.

    This is a secondary safety net alongside ShutdownGuard.
    """
    try:
        import win32console

        def console_handler(event):
            if event in (
                win32console.CTRL_C_EVENT,
                win32console.CTRL_BREAK_EVENT,
                win32console.CTRL_CLOSE_EVENT,
                win32console.CTRL_LOGOFF_EVENT,
                win32console.CTRL_SHUTDOWN_EVENT,
            ):
                flush_callback()
                return True
            return False

        win32console.SetConsoleCtrlHandler(console_handler, True)
    except Exception:
        pass
