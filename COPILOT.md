# 🤖 Built with GitHub Copilot CLI

TraceCLI was built using **GitHub Copilot CLI** (`gh copilot`) as a core part of the development workflow. This document showcases how Copilot accelerated development across every phase of the project.

---

## How Copilot CLI Was Used

### 🔍 `gh copilot explain` — Understanding Complex APIs

TraceCLI relies on Windows-specific APIs (`pywin32`, `ctypes`) that have sparse documentation. Copilot CLI helped explain unfamiliar APIs:

```bash
# Understanding the Win32 foreground window API
gh copilot explain "What does win32gui.GetForegroundWindow() return and how do I get the window title and process ID from it?"

# Understanding Chrome's timestamp format
gh copilot explain "How does Chrome store timestamps in its SQLite history database and how to convert them to Python datetime?"

# Understanding Windows shutdown messages
gh copilot explain "What are WM_QUERYENDSESSION and WM_ENDSESSION messages in Windows and how to intercept them in Python?"

# Understanding SQLite WAL mode for concurrent access
gh copilot explain "What is SQLite WAL mode and how does it help with concurrent reads and writes from multiple threads?"
```

### 💡 `gh copilot suggest` — Generating Implementation Ideas

Copilot CLI suggested commands and code patterns throughout development:

```bash
# Setting up the project structure
gh copilot suggest "Create a Python CLI tool with Click that has subcommands for start, stop, status, and report"

# Database schema design
gh copilot suggest "SQLite schema for an activity tracker that stores app name, window title, duration, category, and resource usage"

# Browser history extraction
gh copilot suggest "Python script to copy and query Chrome's History SQLite database on Windows without locking the browser"

# Windows Registry for auto-start
gh copilot suggest "Python code to add a program to Windows startup using the Registry Run key"

# Rich terminal dashboard
gh copilot suggest "Create a Rich live dashboard that shows system stats, active processes, and a productivity score"

# AI text-to-SQL integration
gh copilot suggest "Python function that sends a natural language question to an LLM API and converts it to a SQL query for SQLite"
```

---

## Key Areas Where Copilot CLI Helped

| Area | How Copilot Helped |
|------|-------------------|
| **Win32 API** | Explained `GetForegroundWindow`, `GetWindowThreadProcessId`, window class registration |
| **SQLite** | Suggested schema design, WAL mode, parameterized queries, migration patterns |
| **Browser Integration** | Explained Chrome's timestamp format, history DB schema, URL parsing |
| **System Monitoring** | Suggested `psutil` patterns for CPU/memory, process enumeration |
| **Shutdown Guard** | Explained Windows message pump, `WM_QUERYENDSESSION`, hidden window creation |
| **Rich TUI** | Suggested table formatting, live dashboards, progress bars, color schemes |
| **Testing** | Generated pytest fixtures, mock patterns for `psutil` and `win32gui` |
| **Packaging** | Suggested `pyproject.toml` configuration, entry points, `pip install -e .` |

---

## Example Workflow

A typical development session with Copilot CLI:

```bash
# 1. Research: understand what we need
gh copilot explain "How to detect the active window on Windows using Python?"

# 2. Suggest: get implementation ideas  
gh copilot suggest "Poll the foreground window every 2 seconds and log changes to SQLite"

# 3. Build: implement with Copilot's guidance in the editor

# 4. Debug: when something goes wrong
gh copilot explain "Why does psutil.Process(pid).memory_info() raise AccessDenied for system processes?"

# 5. Test: generate test patterns
gh copilot suggest "Pytest test for a function that queries SQLite with date filtering"
```

---

## Why Copilot CLI?

- **Zero context switching** — Get answers without leaving the terminal
- **Windows-specific knowledge** — Copilot understands Win32 APIs that are poorly documented
- **Pattern generation** — From SQLite schemas to pytest fixtures, Copilot suggests idiomatic patterns
- **Learning tool** — `gh copilot explain` teaches *why* something works, not just *what* to type
