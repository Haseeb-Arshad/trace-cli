# 🔍 TraceCLI

**"The terminal's black box for your digital life."**

A privacy-first, background activity monitor that lives entirely in your terminal. TraceCLI acts as a flight recorder for your productivity — tracking window usage, categorizing activities, and extracting search intent, all stored locally in SQLite.

**No cloud. No accounts. No tracking. Every byte stays on your machine.**

---

## ✨ Features

- **🎯 Active Intent Tracking** — Doesn't just track apps; extracts window titles and search queries to understand what you were trying to solve
- **📊 Productive Timeline** — Automatically categorizes time: Development, Research, Communication, Productivity, Browsing, and Distraction
- **🔎 Search Extraction** — Pulls real search queries from Chrome, Edge, and Brave browser history (Google, Bing, DuckDuckGo, YouTube, GitHub, StackOverflow)
- **⚡ Zero-Loss Shutdown** — Windows system hooks ensure every second is saved, even on force-close
- **🔒 Privacy by Design** — Local SQLite database. No cloud, no tracking, no data leaves your machine
- **🖥️ Beautiful CLI** — Rich terminal dashboard with live activity feed, reports, timelines, and export

---

## 🛠️ Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/TrackCLI.git
cd TrackCLI

# Create a virtual environment (recommended)
python -m venv venv
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install TraceCLI in editable mode
pip install -e .
```

---

## 🚀 Usage

### Start Tracking
```bash
tracecli start
```
Starts the background tracker with a live dashboard showing your current activity. Press `Ctrl+C` to stop — all data is automatically saved.

### View Reports
```bash
# Today's detailed report
tracecli report

# Report for a specific date
tracecli report --date 2024-01-15
```

### View Timeline
```bash
tracecli timeline
```

### View Search History
```bash
tracecli searches
```

### Daily Productivity Stats
```bash
tracecli stats --days 14
```

### Live Feed (read-only)
```bash
tracecli live
```

### Export Data
```bash
tracecli export --format csv
tracecli export --format json --output my_data.json
```

### Check Status
```bash
tracecli status
```

---

## 📁 Project Structure

```
TrackCLI/
├── src/
│   ├── __init__.py        # Package init
│   ├── __main__.py        # python -m src entry point
│   ├── cli.py             # Rich CLI interface (Click + Rich)
│   ├── database.py        # SQLite schema & helpers
│   ├── tracker.py         # Windows foreground window tracker
│   ├── browser.py         # Browser search extraction
│   ├── system.py          # Shutdown hook (WM_QUERYENDSESSION)
│   └── categorizer.py     # Productivity categorization engine
├── tests/
│   ├── test_database.py
│   ├── test_categorizer.py
│   └── test_browser.py
├── main.py                # Top-level entry point
├── pyproject.toml
├── requirements.txt
└── README.md
```

---

## 🗃️ Database Schema

All data is stored in `~/.tracecli/trace.db`:

| Table | Purpose |
|---|---|
| `activity_log` | Per-window-switch records with app, title, timestamps, duration, category |
| `search_history` | Extracted search queries from browsers |
| `daily_stats` | End-of-day summary (total time, productive hours, top app) |

---

## 📂 Categories

| Category | Examples |
|---|---|
| 💻 Development | VS Code, PyCharm, Terminal, Docker |
| 📚 Research | Stack Overflow, MDN, GitHub, Documentation |
| 📝 Productivity | Word, Excel, Notion, Figma |
| 💬 Communication | Slack, Discord, Teams, Gmail |
| 🌐 Browsing | General browser usage |
| 🎮 Distraction | YouTube, Reddit, Twitter, Netflix |

---

## ⚙️ Requirements

- **Windows 10/11** (uses Windows APIs)
- **Python 3.9+**
- Dependencies: `pywin32`, `rich`, `click`, `psutil`

---

## 📄 License

MIT License — use it however you want.
