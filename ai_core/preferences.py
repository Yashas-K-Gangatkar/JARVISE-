"""
Preferences - User preference management.
"""

import os
import json


class Preferences:
    """
    Manages user preferences for the JARVIS-AI assistant.

    Loads preferences from config and provides a simple API
    for accessing and updating user settings.
    """

    def __init__(self, config_prefs=None):
        self._prefs = {
            "user_name": "User",
            "news_categories": ["technology", "business", "science"],
            "stock_watchlist": ["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA"],
            "greeting_style": "formal",
            "voice_speed": "normal",
            "dashboard_default_panel": "greeting",
        }
        # Override with config values
        if config_prefs:
            self._prefs.update(config_prefs)

    def get(self, key, default=None):
        """Get a preference value."""
        return self._prefs.get(key, default)

    def set(self, key, value):
        """Set a preference value."""
        self._prefs[key] = value
        print(f"[Preferences] Updated: {key} = {value}")

    def get_all(self):
        """Get all preferences as a dictionary."""
        return dict(self._prefs)

    def save(self, filepath="user_preferences.json"):
        """Save preferences to a JSON file."""
        with open(filepath, "w") as f:
            json.dump(self._prefs, f, indent=2)
        print(f"[Preferences] Saved to {filepath}")

    def load(self, filepath="user_preferences.json"):
        """Load preferences from a JSON file."""
        if os.path.exists(filepath):
            with open(filepath, "r") as f:
                loaded = json.load(f)
            self._prefs.update(loaded)
            print(f"[Preferences] Loaded from {filepath}")
        else:
            print(f"[Preferences] File not found: {filepath}")
