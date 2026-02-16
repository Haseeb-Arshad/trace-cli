"""
TraceCLI Productivity Categorizer
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Rule-based engine that classifies window activity into productivity categories.
"""

import re
from typing import Tuple

# ── Category Definitions ───────────────────────────────────────────────────

CATEGORIES = {
    "DEVELOPMENT": "💻 Development",
    "BROWSING": "🌐 Browsing",
    "RESEARCH": "📚 Research",
    "COMMUNICATION": "💬 Communication",
    "PRODUCTIVITY": "📝 Productivity",
    "DISTRACTION": "🎮 Distraction",
    "OTHER": "❓ Other",
}

# ── Process Name Rules ─────────────────────────────────────────────────────

DEV_PROCESSES = {
    "code.exe", "code - insiders.exe",
    "idea64.exe", "idea.exe",
    "pycharm64.exe", "pycharm.exe",
    "webstorm64.exe", "webstorm.exe",
    "rider64.exe",
    "devenv.exe",           # Visual Studio
    "sublime_text.exe",
    "notepad++.exe",
    "vim.exe", "nvim.exe", "gvim.exe",
    "mintty.exe",           # Git Bash
    "windowsterminal.exe",
    "powershell.exe", "pwsh.exe",
    "cmd.exe",
    "conhost.exe",
    "wt.exe",               # Windows Terminal
    "gitextensions.exe",
    "gitkraken.exe",
    "postman.exe",
    "insomnia.exe",
    "docker desktop.exe",
    "wsl.exe",
    "antigravity.exe",      # TrackCLI Agent
    "python.exe",           # Python scripts
    "pythonw.exe",
}

BROWSER_PROCESSES = {
    "chrome.exe",
    "msedge.exe",
    "firefox.exe",
    "brave.exe",
    "opera.exe",
    "vivaldi.exe",
    "arc.exe",
}

COMMUNICATION_PROCESSES = {
    "slack.exe",
    "discord.exe",
    "teams.exe",
    "zoom.exe",
    "skype.exe",
    "thunderbird.exe",
    "outlook.exe",
    "telegram.exe",
    "signal.exe",
}

PRODUCTIVITY_PROCESSES = {
    "winword.exe",      # Microsoft Word
    "excel.exe",
    "powerpnt.exe",     # PowerPoint
    "onenote.exe",
    "notion.exe",
    "obsidian.exe",
    "typora.exe",
    "figma.exe",
    "acrobat.exe",
    "acrord32.exe",
}

DISTRACTION_PROCESSES = {
    "spotify.exe",
    "vlc.exe",
    "wmplayer.exe",
    "netflix.exe",
    "steam.exe",
    "epicgameslauncher.exe",
    "battle.net.exe",
    "tiktok.exe",
    "whatsapp.exe",
}

# ── Title-Based Rules (for browsers & general) ────────────────────────────

RESEARCH_TITLE_PATTERNS = [
    re.compile(r"stack\s*overflow", re.IGNORECASE),
    re.compile(r"github\.com", re.IGNORECASE),
    re.compile(r"gitlab\.com", re.IGNORECASE),
    re.compile(r"documentation", re.IGNORECASE),
    re.compile(r"\bdocs\b", re.IGNORECASE),
    re.compile(r"developer\.mozilla", re.IGNORECASE),
    re.compile(r"MDN Web Docs", re.IGNORECASE),
    re.compile(r"learn\.microsoft", re.IGNORECASE),
    re.compile(r"w3schools", re.IGNORECASE),
    re.compile(r"geeksforgeeks", re.IGNORECASE),
    re.compile(r"tutorialspoint", re.IGNORECASE),
    re.compile(r"medium\.com", re.IGNORECASE),
    re.compile(r"dev\.to", re.IGNORECASE),
    re.compile(r"man\s+page", re.IGNORECASE),
    re.compile(r"pypi\.org", re.IGNORECASE),
    re.compile(r"npmjs\.com", re.IGNORECASE),
    re.compile(r"crates\.io", re.IGNORECASE),
    re.compile(r"wikipedia\.org", re.IGNORECASE),
    re.compile(r"arxiv\.org", re.IGNORECASE),
]

DISTRACTION_TITLE_PATTERNS = [
    re.compile(r"youtube", re.IGNORECASE),
    re.compile(r"netflix", re.IGNORECASE),
    re.compile(r"twitch\.tv", re.IGNORECASE),
    re.compile(r"disney\+", re.IGNORECASE),
    re.compile(r"prime\s*video", re.IGNORECASE),
    re.compile(r"\breddit\b", re.IGNORECASE),
    re.compile(r"twitter|x\.com", re.IGNORECASE),
    re.compile(r"facebook", re.IGNORECASE),
    re.compile(r"instagram", re.IGNORECASE),
    re.compile(r"tiktok", re.IGNORECASE),
    re.compile(r"snapchat", re.IGNORECASE),
    re.compile(r"pinterest", re.IGNORECASE),
    re.compile(r"9gag", re.IGNORECASE),
    re.compile(r"imgur", re.IGNORECASE),
    re.compile(r"buzzfeed", re.IGNORECASE),
]

COMMUNICATION_TITLE_PATTERNS = [
    re.compile(r"gmail", re.IGNORECASE),
    re.compile(r"outlook\.live", re.IGNORECASE),
    re.compile(r"mail\.yahoo", re.IGNORECASE),
    re.compile(r"whatsapp", re.IGNORECASE),
    re.compile(r"messenger", re.IGNORECASE),
    re.compile(r"slack", re.IGNORECASE),
    re.compile(r"discord", re.IGNORECASE),
    re.compile(r"microsoft\s+teams", re.IGNORECASE),
]

PRODUCTIVITY_TITLE_PATTERNS = [
    re.compile(r"google\s+docs", re.IGNORECASE),
    re.compile(r"google\s+sheets", re.IGNORECASE),
    re.compile(r"google\s+slides", re.IGNORECASE),
    re.compile(r"notion\.so", re.IGNORECASE),
    re.compile(r"trello", re.IGNORECASE),
    re.compile(r"asana", re.IGNORECASE),
    re.compile(r"jira", re.IGNORECASE),
    re.compile(r"confluence", re.IGNORECASE),
    re.compile(r"linear\.app", re.IGNORECASE),
    re.compile(r"figma\.com", re.IGNORECASE),
]


# ── Main Categorizer ──────────────────────────────────────────────────────

def categorize(app_name: str, window_title: str) -> str:
    """
    Categorize an activity based on process name and window title.

    Returns a category string like "💻 Development" or "🎮 Distraction".

    Priority order:
      1. Process-based dev tools (always productive)
      2. Process-based communication apps
      3. Process-based productivity apps
      4. Process-based distraction apps
      5. Browser → title-based sub-categorization
      6. General title-based patterns
      7. Fallback to "Other"
    """
    app_lower = app_name.lower().strip()
    title = window_title.strip()

    # 1. Development tools (by process)
    if app_lower in DEV_PROCESSES:
        return CATEGORIES["DEVELOPMENT"]

    # 2. Communication apps (by process)
    if app_lower in COMMUNICATION_PROCESSES:
        return CATEGORIES["COMMUNICATION"]

    # 3. Productivity apps (by process)
    if app_lower in PRODUCTIVITY_PROCESSES:
        return CATEGORIES["PRODUCTIVITY"]

    # 4. Distraction apps (by process)
    if app_lower in DISTRACTION_PROCESSES:
        return CATEGORIES["DISTRACTION"]

    # 5. Browser-based: deeper title analysis
    if app_lower in BROWSER_PROCESSES:
        return _categorize_browser_title(title)

    # 6. General title-based fallback
    return _categorize_by_title(title)


def _categorize_browser_title(title: str) -> str:
    """Sub-categorize a browser window by its title."""
    # Check productivity patterns first (Google Docs, Notion, Jira, etc.)
    # Must come before research, as 'Google Docs' would match \bdocs\b
    for pattern in PRODUCTIVITY_TITLE_PATTERNS:
        if pattern.search(title):
            return CATEGORIES["PRODUCTIVITY"]

    # Check distraction patterns
    for pattern in DISTRACTION_TITLE_PATTERNS:
        if pattern.search(title):
            return CATEGORIES["DISTRACTION"]

    # Check communication patterns
    for pattern in COMMUNICATION_TITLE_PATTERNS:
        if pattern.search(title):
            return CATEGORIES["COMMUNICATION"]

    # Check research patterns (Stack Overflow, MDN, docs, etc.)
    for pattern in RESEARCH_TITLE_PATTERNS:
        if pattern.search(title):
            return CATEGORIES["RESEARCH"]

    # Generic browsing
    return CATEGORIES["BROWSING"]


def _categorize_by_title(title: str) -> str:
    """Last-resort title-based categorization for unknown processes."""
    for pattern in RESEARCH_TITLE_PATTERNS:
        if pattern.search(title):
            return CATEGORIES["RESEARCH"]

    for pattern in DISTRACTION_TITLE_PATTERNS:
        if pattern.search(title):
            return CATEGORIES["DISTRACTION"]

    for pattern in COMMUNICATION_TITLE_PATTERNS:
        if pattern.search(title):
            return CATEGORIES["COMMUNICATION"]

    for pattern in PRODUCTIVITY_TITLE_PATTERNS:
        if pattern.search(title):
            return CATEGORIES["PRODUCTIVITY"]

    return CATEGORIES["OTHER"]


def is_productive(category: str) -> bool:
    """Check if a category is considered productive."""
    return category in {
        CATEGORIES["DEVELOPMENT"],
        CATEGORIES["RESEARCH"],
        CATEGORIES["PRODUCTIVITY"],
    }


def get_category_emoji(category: str) -> str:
    """Extract just the emoji from a category string."""
    if category and len(category) >= 2:
        return category.split(" ")[0]
    return "❓"


# ── App Role Descriptions ─────────────────────────────────────────────────

APP_ROLES = {
    # Development
    "code.exe": "Text Editor & IDE (Visual Studio Code)",
    "code - insiders.exe": "Text Editor & IDE (VS Code Insiders)",
    "idea64.exe": "Java/Kotlin IDE (IntelliJ IDEA)",
    "pycharm64.exe": "Python IDE (PyCharm)",
    "webstorm64.exe": "JavaScript IDE (WebStorm)",
    "devenv.exe": "IDE (Visual Studio)",
    "sublime_text.exe": "Text Editor (Sublime Text)",
    "notepad++.exe": "Text Editor (Notepad++)",
    "vim.exe": "Terminal Text Editor (Vim)",
    "nvim.exe": "Terminal Text Editor (Neovim)",
    "windowsterminal.exe": "Terminal Emulator (Windows Terminal)",
    "wt.exe": "Terminal Emulator (Windows Terminal)",
    "powershell.exe": "Command Shell (PowerShell)",
    "pwsh.exe": "Command Shell (PowerShell Core)",
    "cmd.exe": "Command Shell (Command Prompt)",
    "mintty.exe": "Terminal Emulator (Git Bash)",
    "postman.exe": "API Testing Tool (Postman)",
    "insomnia.exe": "API Testing Tool (Insomnia)",
    "docker desktop.exe": "Container Platform (Docker)",
    "gitkraken.exe": "Git GUI Client (GitKraken)",
    "gitextensions.exe": "Git GUI Client (Git Extensions)",
    # Browsers
    "chrome.exe": "Web Browser (Google Chrome)",
    "msedge.exe": "Web Browser (Microsoft Edge)",
    "firefox.exe": "Web Browser (Mozilla Firefox)",
    "brave.exe": "Web Browser (Brave)",
    "opera.exe": "Web Browser (Opera)",
    "vivaldi.exe": "Web Browser (Vivaldi)",
    "arc.exe": "Web Browser (Arc)",
    # Communication
    "slack.exe": "Team Messaging (Slack)",
    "discord.exe": "Chat & Voice (Discord)",
    "teams.exe": "Team Collaboration (Microsoft Teams)",
    "zoom.exe": "Video Conferencing (Zoom)",
    "skype.exe": "Voice & Video Calls (Skype)",
    "telegram.exe": "Messaging App (Telegram)",
    "thunderbird.exe": "Email Client (Thunderbird)",
    "outlook.exe": "Email & Calendar (Outlook)",
    # Productivity
    "winword.exe": "Word Processor (Microsoft Word)",
    "excel.exe": "Spreadsheet (Microsoft Excel)",
    "powerpnt.exe": "Presentations (Microsoft PowerPoint)",
    "onenote.exe": "Note-Taking (OneNote)",
    "notion.exe": "Workspace & Notes (Notion)",
    "obsidian.exe": "Knowledge Base (Obsidian)",
    "figma.exe": "UI/UX Design (Figma)",
    "acrobat.exe": "PDF Editor (Adobe Acrobat)",
    # Media
    "spotify.exe": "Music Streaming (Spotify)",
    "vlc.exe": "Media Player (VLC)",
    # System
    "explorer.exe": "File Manager (Windows Explorer)",
    "taskmgr.exe": "System Monitor (Task Manager)",
    "mmc.exe": "System Administration Console",
    "regedit.exe": "Registry Editor",
    "svchost.exe": "Windows Service Host",
    "csrss.exe": "Windows Runtime Process",
    "dwm.exe": "Desktop Window Manager",
    "searchhost.exe": "Windows Search Indexer",
    "runtimebroker.exe": "Windows Runtime Broker",
    "systemsettings.exe": "Windows Settings",
}


def get_app_role(app_name: str) -> str:
    """
    Get a human-readable description of an application's role.

    Args:
        app_name: Process name (e.g., "chrome.exe")

    Returns:
        Role description string, or generic description if unknown.
    """
    app_lower = app_name.lower().strip()

    if app_lower in APP_ROLES:
        return APP_ROLES[app_lower]

    # Infer from category
    if app_lower in DEV_PROCESSES:
        return "Development Tool"
    if app_lower in BROWSER_PROCESSES:
        return "Web Browser"
    if app_lower in COMMUNICATION_PROCESSES:
        return "Communication App"
    if app_lower in PRODUCTIVITY_PROCESSES:
        return "Productivity App"
    if app_lower in DISTRACTION_PROCESSES:
        return "Entertainment / Media"

    # Check for common Windows system processes
    if app_lower.endswith(".exe"):
        return "Application"
    return "Unknown Process"
