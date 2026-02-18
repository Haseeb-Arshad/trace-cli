---
title: TraceCLI - The Terminal's Black Box for Your Digital Life
published: true
tags: devchallenge, githubchallenge, cli, githubcopilot
---

*This is a submission for the [GitHub Copilot CLI Challenge](https://dev.to/challenges/github-2026-01-21)*

## What I Built

Open your task manager right now. You'll see 30+ processes running. Close it. Now answer this: how many hours did you actually spend coding today? How much of that "research" was really just Reddit? When did you silently drift from Stack Overflow to YouTube, and how long before you noticed?

You can't answer that. Nobody can. That's the problem.

**TraceCLI** is a local-only, always-on activity recorder that lives in your terminal. It polls your system every second, logs every application switch, every browser tab, every CPU spike — and stores it all in a local SQLite database that never leaves your machine. No accounts. No cloud. No telemetry. Just raw, honest data about where your time actually goes.

### What It Actually Records

Every second, TraceCLI captures:

- **The active window** — process name, full window title, and the category it falls into (Development, Research, Productivity, Communication, Browsing, or Distraction)
- **Browser context** — not just "Chrome is open," but the actual URL, the page title, and the domain. It reads browser history databases directly from Chrome, Edge, Brave, Firefox, Opera, and Vivaldi
- **Search queries** — extracts what you searched for on Google, Bing, DuckDuckGo, YouTube, GitHub, Stack Overflow, PyPI, and npm
- **System resources** — per-process CPU and RAM usage, tied to whichever app is in the foreground. When your laptop fans spin up during a "focus session," TraceCLI tells you exactly which tab is responsible
- **Focus sessions** — timed deep-work blocks with real-time distraction detection, context locking, and a scored history you can review later

All of this lands in `~/.tracecli/trace.db` — a single SQLite file you own completely.

### A Concrete Example

Say it's 6 PM. You feel like you worked hard today but can't point to what you accomplished. You open your terminal:

```bash
$ tracecli report
```

TraceCLI prints a structured breakdown of your entire day:

```
┌─────────────────────────────────────────────┐
│  📅 Monday, February 16, 2026              │
│  ⏱️  Total Tracked: 7h 42m                  │
│  🧠 Productive:     5h 18m (68.8%)          │
│  🎮 Distractions:   1h 23m (17.9%)          │
│  💬 Communication:  1h 01m (13.3%)          │
│  🏆 Top App:        VS Code (3h 47m)        │
│  🎯 Productivity Score: ████████████░░░░ 69% │
└─────────────────────────────────────────────┘
```

You see that 1h 23m of distractions? Drill deeper:

```bash
$ tracecli app chrome --date 2026-02-16
```

Now you see every Chrome session, broken down by domain — 47 minutes on `github.com` (categorized as Research), 22 minutes on `youtube.com` (Distraction), 14 minutes on `reddit.com/r/programming` (Distraction), and 8 minutes on `docs.python.org` (Research). The window titles show you exactly which YouTube videos pulled you off track and when.

Want a bird's-eye view of your consistency over the last few months?

```bash
$ tracecli heatmap
```

A GitHub-style contribution grid fills your terminal — green squares for productive days, red for distraction-heavy ones, dark gray for days you didn't track. Your current streak, your longest streak, and an immediate visual answer to "Am I getting better or worse?"

### How Categorization Works

TraceCLI uses a priority-based rule engine to classify every window switch:

1. **Process-level rules first** — `code.exe` is always Development. `spotify.exe` is always Distraction. There are 50+ built-in process rules covering IDEs, terminals, office suites, creative tools, games, and streaming apps.
2. **Browser windows get title analysis** — if the active process is a browser, TraceCLI inspects the window title with regex patterns. `Stack Overflow`, `GitHub`, `MDN`, `docs.*` → Research. `YouTube`, `Netflix`, `Reddit`, `Twitter` → Distraction. `Google Docs`, `Notion`, `Jira` → Productivity.
3. **User overrides** — disagree with a classification? Edit `~/.tracecli/user_rules.json` and add your own productive/distraction keywords or process names. Your rules take the highest priority.

The productivity score is straightforward: `(time in Development + Research + Productivity) / total tracked time × 100`. No black-box weighting. You can verify it yourself by querying the database directly.

### Focus Mode: Context-Locked Deep Work

```bash
$ tracecli focus 45 --goal "Build authentication module"
```

This starts a 45-minute focus timer that does more than count down. TraceCLI locks onto your current work window. The moment you switch to a different application or an unrelated browser tab, the system detects it:

- **Same app as your locked context?** Timer stays green. Focus score holds.
- **System utility (Explorer, Task Manager)?** Neutral — doesn't count for or against you.
- **Different app or unrelated tab?** Interruption logged. Focus score drops. If AI is configured, TraceCLI evaluates whether the new tab is relevant to your stated goal — switching from your auth module to a tab about "JWT token best practices" might pass the relevance check, while "Top 10 Netflix shows" won't.

When the timer ends, you get a session summary:

```
Focus Score: 87% (Excellent)
Focused Time: 39m 11s
Distracted Time: 5m 49s
Interruptions: 3
```

Every session is saved. Run `tracecli focus-history` to see your trajectory over days and weeks.

The Node.js version also includes a **Pomodoro mode** (`tracecli pomodoro`) that auto-cycles through 25-minute work / 5-minute break phases, with a 15-minute long break every fourth cycle — all with the same context-lock scoring.

### Natural Language Queries

Configure an AI provider (Gemini, OpenAI, or Claude) and you can talk to your data:

```bash
$ tracecli ask "How much time did I spend on VS Code this week?"
```

Behind the scenes, TraceCLI sends your question to an LLM along with the database schema. The LLM generates a SQL query, TraceCLI executes it (read-only — only SELECT statements are allowed), and the LLM summarizes the results in plain language:

```
You spent 18 hours and 34 minutes in VS Code over the last 7 days.
Your most active day was Wednesday (4h 12m), and your least active
was Sunday (42m). Your average daily usage is about 2h 39m.
```

You can ask anything your data can answer: "What's my most-used app after 10 PM?", "Show me my distraction patterns on Mondays vs Fridays", "Export yesterday's focus sessions to CSV."

The `tracecli insights` command goes further — it analyzes your last 7 days and generates a coaching digest: your top achievement, your biggest distraction pattern, an actionable suggestion, and week-over-week trends.

### Auto-Start: The "Flight Recorder" Setup

On Windows, run:

```bash
$ tracecli autostart --enable
```

TraceCLI registers itself in `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` and creates a VBScript launcher at `~/.tracecli/silent_start.vbs` that starts the tracker with no visible console window. From that point on, every time you log into Windows, TraceCLI begins recording silently. A shutdown guard intercepts Windows close signals to flush any buffered data to the database before the system powers off.

No admin rights required. No services to manage. Disable it anytime with `tracecli autostart --disable`.

### Other Commands Worth Mentioning

| Command | What It Does |
|---|---|
| `tracecli live` | Real-time feed of window switches as they happen — useful for debugging or just watching yourself work |
| `tracecli timeline` | Hourly breakdown of your day — see exactly when you were productive vs. distracted |
| `tracecli week` | Weekly summary with daily totals and category distributions |
| `tracecli stats` | 7-day trend of productivity scores |
| `tracecli urls` | Full browser URL history with domain-level grouping |
| `tracecli searches` | Every search query you made, organized by search engine |
| `tracecli system` | Top processes by CPU and RAM consumption, with current system load |
| `tracecli export` | Dump any day's data to CSV or JSON |

---

## Why Two Versions?

TraceCLI ships as two packages because each runtime has genuine strengths:

**Python version** (`pip install tracecli`) — the feature-complete edition. Rich terminal UI with full-color dashboards, heatmaps rendered with box-drawing characters, and the deepest browser integration. Uses the `Rich` library for terminal rendering and `psutil` for system monitoring. If you want every feature, this is the one.

**Node.js version** (`npm install -g tracecli`) — the modern, TypeScript-built edition. Uses `active-win` for reliable window detection and `better-sqlite3` for fast synchronous database operations. Includes the full Pomodoro mode, the AI agent with interactive setup wizard, and a leaner dependency tree. If you prefer the npm ecosystem, start here.

Both versions share the same database schema, the same `~/.tracecli/` directory structure, and the same command interface. You can switch between them or even use both — they write to the same database.

---

## Demo

### 1. The Daily Dashboard (`tracecli` or `tracecli report`)
*Your entire day, broken down in seconds — apps, categories, productive time, distractions, all in one panel.*

![Daily Dashboard](<!-- REPLACE: upload demos/demo-report.gif to dev.to and paste URL here -->)

### 2. Consistency Heatmap (`tracecli heatmap`)
*Months of productivity data in a single glance. Green squares for productive days, red for distraction-heavy ones — just like GitHub contributions.*

![Heatmap](<!-- REPLACE: upload demos/demo-heatmap.gif to dev.to and paste URL here -->)

### 3. Smart Focus Mode (`tracecli focus`)
*Watch what happens when you drift. TraceCLI locks to your work window and catches the exact moment you switch to a distraction — focus score drops in real time.*

![Focus Mode](<!-- REPLACE: upload demos/demo-focus.gif to dev.to and paste URL here -->)

### 4. Natural Language Insights (`tracecli ask`)
*No SQL needed. Ask a question in plain English, get a data-backed answer. TraceCLI generates the query, runs it, and summarizes the result.*

![AI Ask](<!-- REPLACE: upload demos/demo-ask.gif to dev.to and paste URL here -->)

### 5. Live Activity Feed (`tracecli live`)
*Every window switch, categorized and timestamped as it happens. This is what TraceCLI sees every second it's running.*

![Live Feed](<!-- REPLACE: upload demos/demo-live.gif to dev.to and paste URL here -->)

---

## My Experience with GitHub Copilot CLI

TraceCLI has 2,000+ lines of logic across categorization, database management, browser history extraction, system monitoring, and terminal rendering. Copilot CLI was a constant collaborator throughout.

### Building the Categorization Engine
The rule engine in `categorizer.py` (and `categorizer.ts`) contains 50+ process rules, 30+ regex patterns for browser title analysis, and a priority system that resolves conflicts between them. Copilot helped me rapidly scaffold these pattern lists — I'd describe a category like "research tools," and Copilot would suggest process names and URL patterns I hadn't considered (like `arxiv.org`, `crates.io`, or `GeeksforGeeks`). It turned what would have been hours of manual research into minutes of iterative refinement.

### SQLite Schema and Query Optimization
The database has 7 tables with 15 indexes. Copilot was instrumental in designing efficient queries — particularly the aggregation queries behind `tracecli stats` and `tracecli heatmap`, which need to join `daily_stats` with `activity_log` across date ranges while staying performant on months of data. It also suggested the WAL journal mode and the `UNIQUE` constraint on `daily_stats(date)` for upsert operations, which I wouldn't have reached for instinctively.

### Terminal UI Layout
I wanted the output to feel like a dashboard, not a wall of text. Copilot helped me structure the `Rich` panels, tables, and progress bars in the Python version — getting the padding, alignment, and color thresholds right so that a productivity score of 72% renders as a satisfying green bar while 38% shows an urgent red. It also helped generate the ASCII art banner and the box-drawing characters for the heatmap grid.

### Cross-Browser History Extraction
Reading browser history from locked SQLite databases (Chrome, Edge, Brave, Firefox — each with slightly different schemas and file paths) was one of the trickiest parts. Copilot provided the platform-specific paths (`Local State`, `History`, `places.sqlite`), the SQL queries for each browser's schema, and the approach of copying the locked database to a temp file before reading — a pattern I hadn't seen before but that works reliably even when the browser is running.

### Windows System Integration
The auto-start mechanism required three coordinated pieces: a registry key, a VBScript launcher to suppress the console window, and a shutdown guard that intercepts `WM_ENDSESSION` messages to flush data before power-off. Copilot helped me navigate the `winreg` module, the VBScript syntax, and the `ctypes` calls for the Windows message pump — areas where I would have spent significant time reading Microsoft documentation.

---

## Repositories & Installation

### Python (Full-Featured Version)
```bash
pip install tracecli
```
📦 [github.com/Haseeb-Arshad/trace-cli](https://github.com/Haseeb-Arshad/trace-cli)

### Node.js (Modern TypeScript Edition)
```bash
npm install -g tracecli
```
📦 [github.com/Haseeb-Arshad/tracecli-npm](https://github.com/Haseeb-Arshad/tracecli-npm)

Both versions are optimized for Windows. Start with `tracecli start`, let it run for a few hours, then explore your data with `tracecli report`. Enable `tracecli autostart` and forget about it — your terminal's black box will handle the rest.

TraceCLI turns the terminal into a mirror for your digital habits. GitHub Copilot CLI helped build every layer of it — from the database schema to the UI polish to the system-level integrations that make it invisible until you need it.
