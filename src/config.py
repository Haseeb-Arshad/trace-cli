"""
TraceCLI Configuration Manager
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Handles persistent configuration for AI settings and other preferences.
Stored in ~/.tracecli/config.json
"""

import json
import os
from pathlib import Path
from typing import Optional, Dict

CONFIG_DIR = Path.home() / ".tracecli"
CONFIG_PATH = CONFIG_DIR / "config.json"

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
