# TraceCLI

**The terminal's black box for your digital life.**

TraceCLI is a privacy-first, AI-powered activity tracker and productivity coach that lives in your terminal. It monitors your digital habits, actively protects your focus, and provides AI-powered coaching to improve your workflow—all without your data ever leaving your machine.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![GitHub Repository](https://img.shields.io/badge/GitHub-trace--cli-blue.svg?logo=github)](https://github.com/Haseeb-Arshad/trace-cli)

## Why TraceCLI?

TraceCLI isn't just a time tracker. It's an intelligent agent designed to understand your workflow.

- **Privacy First**: All data is stored locally in `~/.tracecli/trace.db`. Your activity data stays on your machine.
- **Zero Friction**: Auto-starts with Windows. Tracks active windows, browser searches, and system resources automatically in the background.
- **AI-Powered**: Chat with your productivity data using Natural Language. Get personalized insights and weekly digests to understand where your time goes.

---

## Key Features

### Productivity Heatmap
Visualize your consistency with a GitHub-style contribution graph.
```bash
tracecli heatmap --weeks 52
```

### Focus Mode
A Pomodoro timer with active distraction detection. If you switch to a non-productive app (e.g., social media) during a session, TraceCLI alerts you immediately to get you back on track.
```bash
tracecli focus --duration 25 --goal "Core Feature Implementation"
```

### AI Insights
Get personalized productivity digests or ask questions about your habits using natural language.
```bash
tracecli insights  # Weekly coaching report
tracecli ask "What was my most used app on Monday?"
```

### Configurable Rules
Define exactly what counts as "Productive" or "Distraction" for you using simple configuration rules.

---

## Installation

You can install TraceCLI directly from PyPI (coming soon) or from source.

```bash
# Clone the repository
git clone https://github.com/Haseeb-Arshad/trace-cli.git
cd trace-cli

# Install in editable mode
pip install -e .

# Verify installation
tracecli --version
```

### AI Configuration (Optional)
Supported providers: `gemini`, `openai`, `claude`.
```bash
tracecli config --provider gemini --key YOUR_API_KEY
```

---

## Command Reference

### Core & Tracking
- `tracecli start`: Start activity tracking (use `--background` to run silently).
- `tracecli live`: View real-time activity feed.
- `tracecli status`: Check CLI and Database status.
- `tracecli autostart enable`: Enable start on Windows login.

### Analytics & Reports
- `tracecli stats`: View daily productivity summary.
- `tracecli heatmap`: GitHub-style productivity graph.
- `tracecli report`: Detailed daily report with app breakdowns.
- `tracecli timeline`: Visual daily timeline of activities.
- `tracecli app [NAME]`: Deep dive into a specific application's usage.

### System & Browsing
- `tracecli urls`: Browser history and domain breakdown.
- `tracecli searches`: Recent browser search queries.
- `tracecli system`: System resource overview (CPU/RAM snapshots).

---

## Architecture

TraceCLI is built on a modular architecture designed for performance and extensibility.

- **Tracker**: Polls the Windows API to detect active applications and measures engagement.
- **Categorizer**: Maps process names and window titles to categories (Development, Communication, Productivity, etc.) using a flexible rule engine.
- **FocusMonitor**: A dedicated background thread that enforces focus rules during active sessions.
- **BrowserBridge**: Safely reads browser history databases (Chrome/Edge) to provide context on web usage without invasive extensions.

---

## Contributing

We welcome contributions! Please see `CONTRIBUTING.md` for details on how to get started.

## License

TraceCLI is released under the [MIT License](LICENSE).
