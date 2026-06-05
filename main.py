"""
JARVIS-AI: Intelligent Personal Assistant
Main entry point for the application.
"""

import sys
import os
import threading
import time
import yaml

from ai_core.assistant_core import AssistantCore
from ai_core.event_bus import EventBus
from ai_core.preferences import Preferences


def load_config(config_path="config.yaml"):
    """Load configuration from YAML file."""
    if not os.path.exists(config_path):
        print(f"[WARNING] Config file not found: {config_path}")
        print("[INFO] Using default configuration...")
        return get_default_config()

    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
    print(f"[INFO] Configuration loaded from {config_path}")
    return config


def get_default_config():
    """Return default configuration."""
    return {
        "camera": {"device_index": 0, "fps": 30},
        "face_recognition": {
            "model": "hog",
            "tolerance": 0.6,
            "greeting_cooldown_seconds": 300,
            "known_faces_dir": "known_faces",
        },
        "gesture": {
            "hold_duration_seconds": 0.5,
            "confidence_threshold": 0.8,
            "max_num_hands": 1,
        },
        "voice": {
            "wake_word": "jarvis",
            "listen_timeout": 10,
            "phrase_limit": 10,
            "recognizer_engine": "google",
        },
        "tts": {
            "engine": "pyttsx3",
            "rate": 180,
            "volume": 1.0,
        },
        "dashboard": {
            "type": "tkinter",
            "refresh_interval_seconds": 30,
        },
        "data": {
            "news_api_key": "",
            "stock_symbols": ["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA"],
            "project_status_file": "project_status.json",
            "cache_duration_minutes": 30,
        },
        "preferences": {
            "user_name": "User",
            "news_categories": ["technology", "business", "science"],
            "greeting_style": "formal",
        },
    }


def main():
    """Main application entry point."""
    print("=" * 60)
    print("  JARVIS-AI: Intelligent Personal Assistant")
    print("  Initializing system...")
    print("=" * 60)

    # Load configuration
    config = load_config()

    # Initialize preferences
    preferences = Preferences(config.get("preferences", {}))

    # Create event bus
    event_bus = EventBus()

    # Initialize the AI assistant core
    assistant = AssistantCore(event_bus, config, preferences)

    # Start the assistant
    try:
        assistant.start()
    except KeyboardInterrupt:
        print("\n[INFO] Shutting down JARVIS-AI...")
        assistant.stop()
    except Exception as e:
        print(f"[ERROR] Unexpected error: {e}")
        assistant.stop()
        sys.exit(1)

    print("[INFO] JARVIS-AI shut down complete.")


if __name__ == "__main__":
    main()
