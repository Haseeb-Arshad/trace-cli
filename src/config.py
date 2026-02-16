"""
TraceCLI Configuration Manager
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Handles persistent configuration for AI settings and other preferences.
Stored in ~/.tracecli/config.json
"""

import json
import os
from pathlib import Path
from typing import Optional, Dict, List, Set, Any
from dataclasses import dataclass, field
CONFIG_DIR = Path.home() / ".tracecli"
CONFIG_PATH = CONFIG_DIR / "config.json"
RULES_PATH = CONFIG_DIR / "user_rules.json"

DEFAULT_CONFIG = {
    "ai_provider": "gemini",  # gemini, openai, claude
    "ai_api_key": "",
    "ai_model": "",  # Optional override
}


def _ensure_config():
    """Ensure the config file exists with default values."""
    if not CONFIG_DIR.exists():
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    
    if not CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(DEFAULT_CONFIG, f, indent=4)
        except OSError:
            pass


def load_config() -> Dict[str, str]:
    """Load configuration from disk."""
    _ensure_config()
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            # Merge with defaults to ensure all keys exist
            return {**DEFAULT_CONFIG, **data}
    except (json.JSONDecodeError, OSError):
        return DEFAULT_CONFIG.copy()


def save_config(config: Dict[str, str]):
    """Save configuration to disk."""
    if not CONFIG_DIR.exists():
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4)
    except OSError:
        pass


def get_ai_config() -> tuple[str, str, str]:
    """Get (provider, api_key, model)."""
    cfg = load_config()
    return cfg.get("ai_provider", "gemini"), cfg.get("ai_api_key", ""), cfg.get("ai_model", "")


def set_ai_key(key: str):
    """Set the API key."""
    cfg = load_config()
    cfg["ai_api_key"] = key
    save_config(cfg)


def set_ai_provider(provider: str):
    """Set the AI provider (gemini, openai, claude)."""
    cfg = load_config()
    cfg["ai_provider"] = provider.lower()
    save_config(cfg)


# ── Productivity Rules ─────────────────────────────────────────────────────

@dataclass
class UserRules:
    """User-defined productivity rules."""
    productive_processes: Set[str] = field(default_factory=set)
    distraction_processes: Set[str] = field(default_factory=set)
    productive_keywords: List[str] = field(default_factory=list)
    distraction_keywords: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "productive_processes": list(self.productive_processes),
            "distraction_processes": list(self.distraction_processes),
            "productive_keywords": self.productive_keywords,
            "distraction_keywords": self.distraction_keywords,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UserRules":
        return cls(
            productive_processes=set(data.get("productive_processes", [])),
            distraction_processes=set(data.get("distraction_processes", [])),
            productive_keywords=data.get("productive_keywords", []),
            distraction_keywords=data.get("distraction_keywords", []),
        )


def load_rules() -> UserRules:
    """Load user rules from the configuration file."""
    _ensure_config()
    
    if not RULES_PATH.exists():
        return UserRules()

    try:
        with open(RULES_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            return UserRules.from_dict(data)
    except (json.JSONDecodeError, OSError):
        return UserRules()


def save_rules(rules: UserRules) -> None:
    """Save user rules to the configuration file."""
    if not CONFIG_DIR.exists():
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    
    try:
        with open(RULES_PATH, "w", encoding="utf-8") as f:
            json.dump(rules.to_dict(), f, indent=4)
    except OSError:
        pass
