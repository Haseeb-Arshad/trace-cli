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
