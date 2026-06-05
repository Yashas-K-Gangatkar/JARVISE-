"""
JARVIS-AI: Intelligent Personal Assistant
==========================================

Main entry point — wires every module together through the EventBus,
manages the startup sequence, and handles graceful shutdown.

Startup sequence:
    1. Parse CLI arguments & load config
    2. Initialise EventBus, Preferences, AssistantCore
    3. Initialise all modules (Face, Gesture, Voice, Data, TTS, Dashboard)
    4. Wire TTS → SPEAK_REQUEST events
    5. Wire Dashboard → data-update events
    6. Start background modules in their own threads
    7. Start Dashboard in the main thread (tkinter requirement)
    8. On Dashboard close → stop everything gracefully
"""

import argparse
import logging
import os
import signal
import sys
import time

import yaml

# ---------------------------------------------------------------------------
# Logging setup (early — before anything else logs)
# ---------------------------------------------------------------------------

LOG_FMT = "%(asctime)s │ %(levelname)-7s │ %(name)-18s │ %(message)s"
LOG_DATE_FMT = "%H:%M:%S"


def _setup_logging(debug: bool = False) -> logging.Logger:
    """Configure root logger with timestamped, coloured console output."""
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(level=level, format=LOG_FMT, datefmt=LOG_DATE_FMT)

    # Silence overly chatty libraries unless in debug mode
    if not debug:
        for noisy in ("PIL", "urllib3", "requests", "mediapipe", "httpx"):
            logging.getLogger(noisy).setLevel(logging.WARNING)

    return logging.getLogger("jarvis")


# ---------------------------------------------------------------------------
# Default configuration (used when config.yaml is missing)
# ---------------------------------------------------------------------------

_DEFAULT_CONFIG: dict = {
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
    "ai_chat": {
        "provider": "local",
        "openai_api_key": "",
        "openai_model": "gpt-3.5-turbo",
        "groq_api_key": "",
        "groq_model": "llama3-8b-8192",
        "max_history": 20,
        "max_tokens": 1000,
        "temperature": 0.7,
        "rate_limit_per_minute": 30,
    },
    "reminders": {
        "data_file": "reminders/reminder_data.json",
        "check_interval_seconds": 30,
        "daily_briefing_time": "08:00",
        "sleep_hours_start": 23,
        "sleep_hours_end": 7,
        "briefing_enabled": True,
    },
    "smart_home": {
        "mode": "simulation",
        "home_assistant_url": "http://localhost:8123",
        "home_assistant_token": "",
        "rooms": {},
    },
    "screen_control": {
        "enabled": True,
        "safe_mode": True,
        "mouse_speed": 0.5,
        "fail_safe": True,
        "screenshot_dir": "screenshots",
    },
    "email_calendar": {
        "email_enabled": False,
        "calendar_enabled": True,
        "email": {
            "provider": "gmail",
            "address": "",
            "app_password": "",
            "imap_server": "imap.gmail.com",
            "smtp_server": "smtp.gmail.com",
            "smtp_port": 587,
        },
        "calendar": {
            "type": "local",
            "data_file": "calendar_events.json",
            "reminder_minutes_before": 15,
            "default_event_duration_minutes": 60,
        },
    },
}


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge *override* into *base* (base is not mutated)."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config(config_path: str = "config.yaml") -> dict:
    """Load configuration from YAML, falling back to built-in defaults."""
    log = logging.getLogger("jarvis.config")

    if os.path.exists(config_path):
        try:
            with open(config_path, "r") as fh:
                user_config = yaml.safe_load(fh) or {}
            config = _deep_merge(_DEFAULT_CONFIG, user_config)
            log.info("Configuration loaded from %s", config_path)
            return config
        except yaml.YAMLError as exc:
            log.error("Failed to parse %s: %s — using defaults", config_path, exc)
    else:
        log.warning("Config file not found: %s — using defaults", config_path)

    return dict(_DEFAULT_CONFIG)


# ---------------------------------------------------------------------------
# CLI argument parser
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="JARVIS-AI: Intelligent Personal Assistant",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
  python main.py                     # Full experience
  python main.py --no-camera         # No face/gesture detection
  python main.py --no-voice          # No voice control
  python main.py --debug             # Verbose logging
""",
    )
    p.add_argument(
        "--no-camera",
        action="store_true",
        help="Disable camera-dependent modules (face detection, gesture detection)",
    )
    p.add_argument(
        "--no-voice",
        action="store_true",
        help="Disable voice control module",
    )
    p.add_argument(
        "--no-dashboard",
        action="store_true",
        help="Run headless without the tkinter dashboard",
    )
    p.add_argument(
        "--debug",
        action="store_true",
        help="Enable verbose debug logging",
    )
    p.add_argument(
        "--config",
        default="config.yaml",
        help="Path to configuration file (default: config.yaml)",
    )
    return p.parse_args()


# ---------------------------------------------------------------------------
# Startup banner
# ---------------------------------------------------------------------------

_BANNER_LINES = r"""
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│      ██╗██████╗  █████╗ ███████╗███████╗██╗  ██╗           │
│      ██║██╔══██╗██╔══██╗██╔════╝██╔════╝██║  ██║           │
│      ██║██████╔╝███████║███████╗███████╗███████║           │
│      ██║██╔═══╝ ██╔══██║╚════██║╚════██║██╔══██║           │
│      ██║██║     ██║  ██║███████║███████║██║  ██║           │
│      ╚═╝╚═╝     ╚═╝  ╚═╝╚══════╝╚══════╝╚═╝  ╚═╝           │
│                                                             │
│          A. I.   A S S I S T A N T                         │
│                                                             │
│          v1.0.0  ─  "At your service, sir."                │
│                                                             │
└─────────────────────────────────────────────────────────────┘
"""

_STATUS_ICONS = {
    "ok": "✔",
    "skip": "○",
    "fail": "✘",
}


def _print_banner() -> None:
    """Print the JARVIS ASCII banner with an animation effect."""
    # Quick "typing" animation for the banner
    for i, line in enumerate(_BANNER_LINES.splitlines()):
        print(line)
        if i < 8:  # slow down the top part for effect
            time.sleep(0.02)
    print()


def _print_status(module_name: str, status: str, detail: str = "") -> None:
    """Print a colourised module-initialisation status line."""
    icon = _STATUS_ICONS.get(status, "·")
    color = {"ok": "\033[92m", "skip": "\033[33m", "fail": "\033[91m"}.get(
        status, "\033[0m"
    )
    reset = "\033[0m"
    suffix = f"  ({detail})" if detail else ""
    print(f"  {color}{icon}{reset}  {module_name:<26s}{suffix}")


# ---------------------------------------------------------------------------
# TTS ↔ EventBus bridge
# ---------------------------------------------------------------------------

class TTSBridge:
    """
    Connects the EventBus SPEAK_REQUEST events to the TTSEngine.

    This lightweight adapter subscribes to ``EventTypes.SPEAK_REQUEST``
    on the bus and forwards every event's ``text`` field to
    ``TTSEngine.speak()``.
    """

    def __init__(self, event_bus, tts_engine, log=None):
        self.event_bus = event_bus
        self.tts_engine = tts_engine
        self.log = log or logging.getLogger("jarvis.tts_bridge")
        self._subscribe()

    # -- public ----------------------------------------------------------

    def _subscribe(self):
        """Register the event-bus subscription."""
        from ai_core.event_bus import EventTypes

        self.event_bus.subscribe(EventTypes.SPEAK_REQUEST, self._on_speak_request)
        self.log.debug("TTSBridge subscribed to SPEAK_REQUEST")

    def _on_speak_request(self, event):
        """Handle a SPEAK_REQUEST event and forward to TTS."""
        text = event.data.get("text", "")
        if text:
            self.log.info("Speaking: %s", text[:80])
            try:
                self.tts_engine.speak(text)
            except Exception as exc:
                self.log.error("TTS speak error: %s", exc)


# ---------------------------------------------------------------------------
# Application orchestrator
# ---------------------------------------------------------------------------

class JarvisApp:
    """
    Top-level orchestrator that owns every module, the event bus,
    and the application lifecycle.
    """

    def __init__(self, config: dict, args: argparse.Namespace):
        self.config = config
        self.args = args
        self.log = logging.getLogger("jarvis.app")

        # ── Core infrastructure ──────────────────────────────────────
        from ai_core.event_bus import EventBus
        from ai_core.preferences import Preferences
        from ai_core.assistant_core import AssistantCore

        self.event_bus = EventBus()
        self.preferences = Preferences(config.get("preferences", {}))
        self.assistant_core = AssistantCore(
            self.event_bus, config, self.preferences
        )

        # ── Module containers (populated during init) ────────────────
        self.face_module = None
        self.gesture_module = None
        self.voice_module = None
        self.data_manager = None
        self.ai_chat_module = None
        self.reminder_module = None
        self.smart_home_module = None
        self.screen_control_module = None
        self.email_calendar_module = None
        self.tts_engine = None
        self.tts_bridge = None
        self.dashboard = None

        # ── Shutdown coordination ────────────────────────────────────
        self._shutting_down = False

    # ==================================================================
    # Initialisation
    # ==================================================================

    def init_modules(self) -> None:
        """Create and wire all modules based on config & CLI flags."""

        # ── TTS Engine (always initialised — it's lightweight) ───────
        try:
            from dashboard.tts_engine import TTSEngine
            self.tts_engine = TTSEngine(self.config)
            self.tts_bridge = TTSBridge(self.event_bus, self.tts_engine, self.log)
            _print_status("TTS Engine", "ok", self.config.get("tts", {}).get("engine", "pyttsx3"))
        except Exception as exc:
            self.log.warning("TTS init failed: %s", exc)
            _print_status("TTS Engine", "fail", str(exc))

        # ── Face Detection ──────────────────────────────────────────
        if self.args.no_camera:
            _print_status("Face Detection", "skip", "--no-camera flag")
        else:
            try:
                from face_engine.face_detection import FaceDetectionModule
                self.face_module = FaceDetectionModule(self.event_bus, self.config)
                self.assistant_core.register_module("face_detection", self.face_module)
                _print_status("Face Detection", "ok")
            except Exception as exc:
                self.log.warning("FaceDetection init failed: %s", exc)
                _print_status("Face Detection", "fail", str(exc))

        # ── Gesture Detection ───────────────────────────────────────
        if self.args.no_camera:
            _print_status("Gesture Detection", "skip", "--no-camera flag")
        else:
            try:
                from gesture_control.gesture_detector import GestureDetectionModule
                self.gesture_module = GestureDetectionModule(self.event_bus, self.config)
                self.assistant_core.register_module("gesture_detection", self.gesture_module)
                _print_status("Gesture Detection", "ok")
            except Exception as exc:
                self.log.warning("GestureDetection init failed: %s", exc)
                _print_status("Gesture Detection", "fail", str(exc))

        # ── Voice Control ───────────────────────────────────────────
        if self.args.no_voice:
            _print_status("Voice Control", "skip", "--no-voice flag")
        else:
            try:
                from voice_control.voice_listener import VoiceControlModule
                self.voice_module = VoiceControlModule(self.event_bus, self.config)
                self.assistant_core.register_module("voice_control", self.voice_module)
                _print_status("Voice Control", "ok", f"wake: '{self.config.get('voice', {}).get('wake_word', 'jarvis')}'")
            except Exception as exc:
                self.log.warning("VoiceControl init failed: %s", exc)
                _print_status("Voice Control", "fail", str(exc))

        # ── Data Manager ────────────────────────────────────────────
        try:
            from data_integration.data_manager import DataManager
            self.data_manager = DataManager(self.event_bus, self.config)
            self.assistant_core.register_module("data_manager", self.data_manager)
            _print_status("Data Manager", "ok")
        except Exception as exc:
            self.log.warning("DataManager init failed: %s", exc)
            _print_status("Data Manager", "fail", str(exc))

        # ── AI Chat ────────────────────────────────────────────────
        try:
            from ai_chat import AIChatModule
            self.ai_chat_module = AIChatModule(self.event_bus, self.config)
            self.assistant_core.register_module("ai_chat", self.ai_chat_module)
            _print_status("AI Chat", "ok", self.config.get("ai_chat", {}).get("provider", "local"))
        except Exception as exc:
            self.log.warning("AIChat init failed: %s", exc)
            _print_status("AI Chat", "fail", str(exc))

        # ── Reminders & Alerts ──────────────────────────────────────
        try:
            from reminders import ReminderModule
            self.reminder_module = ReminderModule(self.event_bus, self.config)
            self.assistant_core.register_module("reminders", self.reminder_module)
            _print_status("Reminders & Alerts", "ok")
        except Exception as exc:
            self.log.warning("ReminderModule init failed: %s", exc)
            _print_status("Reminders & Alerts", "fail", str(exc))

        # ── Smart Home Control ──────────────────────────────────────
        try:
            from smart_home import SmartHomeModule
            self.smart_home_module = SmartHomeModule(self.event_bus, self.config)
            self.assistant_core.register_module("smart_home", self.smart_home_module)
            _print_status("Smart Home", "ok", self.config.get("smart_home", {}).get("mode", "simulation"))
        except Exception as exc:
            self.log.warning("SmartHomeModule init failed: %s", exc)
            _print_status("Smart Home", "fail", str(exc))

        # ── Screen Control ──────────────────────────────────────────
        try:
            from screen_control import ScreenControlModule
            self.screen_control_module = ScreenControlModule(self.event_bus, self.config)
            self.assistant_core.register_module("screen_control", self.screen_control_module)
            _print_status("Screen Control", "ok")
        except Exception as exc:
            self.log.warning("ScreenControlModule init failed: %s", exc)
            _print_status("Screen Control", "fail", str(exc))

        # ── Email & Calendar ────────────────────────────────────────
        try:
            from email_calendar import EmailCalendarModule
            self.email_calendar_module = EmailCalendarModule(self.event_bus, self.config)
            self.assistant_core.register_module("email_calendar", self.email_calendar_module)
            _print_status("Email & Calendar", "ok", "demo" if not self.config.get("email_calendar", {}).get("email_enabled") else "live")
        except Exception as exc:
            self.log.warning("EmailCalendarModule init failed: %s", exc)
            _print_status("Email & Calendar", "fail", str(exc))

        # ── Dashboard ───────────────────────────────────────────────
        if self.args.no_dashboard:
            _print_status("Dashboard", "skip", "--no-dashboard flag")
        else:
            try:
                from dashboard.dashboard_tkinter import DashboardModule
                self.dashboard = DashboardModule(self.event_bus, self.config)
                _print_status("Dashboard", "ok", "tkinter")
            except Exception as exc:
                self.log.warning("Dashboard init failed: %s", exc)
                _print_status("Dashboard", "fail", str(exc))

    # ==================================================================
    # Startup sequence
    # ==================================================================

    def start(self) -> None:
        """
        Execute the full startup sequence and block until shutdown.

        Sequence:
            1. Start EventBus processing
            2. Publish SYSTEM_START
            3. Start background modules (face, gesture, voice, data)
            4. Speak startup greeting (TTS)
            5. Start Dashboard in main thread (blocks until window closes)
               — OR — run a simple main loop in headless mode
            6. On exit → shutdown()
        """
        self.log.info("Starting JARVIS-AI…")
        print()

        # 1. Start EventBus
        self.event_bus.start_processing()

        # 2. Publish system-start
        from ai_core.event_bus import Event, EventTypes
        self.event_bus.publish(Event(EventTypes.SYSTEM_START))
        self.log.debug("Published SYSTEM_START")

        # 3. Start all background modules (non-dashboard)
        self._start_background_modules()

        # 4. Startup greeting via TTS
        self._startup_greeting()

        print()
        self.log.info("All modules running. JARVIS is online.")

        # 5. Block: Dashboard (main thread) or headless loop
        if self.dashboard is not None:
            self.log.info("Launching Dashboard (main thread)…")
            try:
                self.dashboard.start()  # blocks on tkinter mainloop
            except KeyboardInterrupt:
                self.log.info("KeyboardInterrupt received while Dashboard was running")
        else:
            self._headless_loop()

        # 6. Shutdown
        self.shutdown()

    # ------------------------------------------------------------------

    def _start_background_modules(self) -> None:
        """Start all non-dashboard modules in their own threads."""
        modules = [
            ("Face Detection", self.face_module),
            ("Gesture Detection", self.gesture_module),
            ("Voice Control", self.voice_module),
            ("Data Manager", self.data_manager),
            ("AI Chat", self.ai_chat_module),
            ("Reminders", self.reminder_module),
            ("Smart Home", self.smart_home_module),
            ("Screen Control", self.screen_control_module),
            ("Email & Calendar", self.email_calendar_module),
        ]

        for name, module in modules:
            if module is None:
                continue
            try:
                module.start()
                self.log.info("%s started", name)
            except Exception as exc:
                self.log.error("Failed to start %s: %s", name, exc)

    def _startup_greeting(self) -> None:
        """Speak a brief greeting after all modules are online."""
        from datetime import datetime

        hour = datetime.now().hour
        if hour < 12:
            greeting = "Good morning"
        elif hour < 17:
            greeting = "Good afternoon"
        else:
            greeting = "Good evening"

        user = self.preferences.get("user_name", "Sir")
        message = f"{greeting}, {user}. JARVIS is online and at your service."

        if self.tts_engine:
            try:
                self.tts_engine.speak(message)
            except Exception as exc:
                self.log.warning("Startup greeting TTS error: %s", exc)

        # Also publish so the dashboard status bar picks it up
        from ai_core.event_bus import Event, EventTypes
        self.event_bus.publish(
            Event(EventTypes.DASHBOARD_UPDATE, {"greeting": message})
        )
        self.log.info("Startup greeting: %s", message)

    def _headless_loop(self) -> None:
        """Simple blocking loop for headless (no-dashboard) mode."""
        self.log.info("Running in headless mode (Ctrl+C to quit)")
        try:
            while not self._shutting_down:
                time.sleep(0.5)
        except KeyboardInterrupt:
            self.log.info("KeyboardInterrupt — shutting down")

    # ==================================================================
    # Shutdown
    # ==================================================================

    def shutdown(self) -> None:
        """
        Gracefully stop every module in reverse order, then stop the
        EventBus.
        """
        if self._shutting_down:
            return  # prevent double-shutdown
        self._shutting_down = True

        self.log.info("Shutting down JARVIS-AI…")
        print()

        # Stop modules in reverse-startup order
        shutdown_order = [
            ("Voice Control", self.voice_module),
            ("Gesture Detection", self.gesture_module),
            ("Face Detection", self.face_module),
            ("Reminders", self.reminder_module),
            ("Smart Home", self.smart_home_module),
            ("Screen Control", self.screen_control_module),
            ("Email & Calendar", self.email_calendar_module),
            ("Data Manager", self.data_manager),
            ("AI Chat", self.ai_chat_module),
            ("Dashboard", self.dashboard),
        ]

        for name, module in shutdown_order:
            if module is None:
                continue
            try:
                module.stop()
                _print_status(name, "ok", "stopped")
            except Exception as exc:
                _print_status(name, "fail", str(exc))

        # Stop the AssistantCore (publishes SYSTEM_STOP)
        try:
            self.assistant_core.stop()
            _print_status("Assistant Core", "ok", "stopped")
        except Exception as exc:
            _print_status("Assistant Core", "fail", str(exc))

        # Stop EventBus last
        try:
            self.event_bus.stop_processing()
            _print_status("EventBus", "ok", "stopped")
        except Exception as exc:
            _print_status("EventBus", "fail", str(exc))

        print()
        self.log.info("JARVIS-AI shutdown complete. Goodbye!")


# ---------------------------------------------------------------------------
# Signal handler for clean Ctrl+C
# ---------------------------------------------------------------------------

_app: JarvisApp | None = None  # module-level ref so the signal handler can reach it


def _signal_handler(signum, frame):
    """Handle SIGINT / SIGTERM by initiating graceful shutdown."""
    log = logging.getLogger("jarvis")
    log.info("Signal %s received — initiating graceful shutdown…", signum)
    if _app is not None and not _app._shutting_down:
        # If the dashboard is running, destroy the tkinter root to
        # unblock the main thread; otherwise the headless loop will
        # catch the flag on its next iteration.
        if _app.dashboard is not None and _app.dashboard._root is not None:
            try:
                _app.dashboard._root.destroy()
            except Exception:
                pass
        _app._shutting_down = True


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Application entry point."""

    # 1. Parse CLI arguments
    args = _parse_args()

    # 2. Set up logging (respects --debug)
    log = _setup_logging(debug=args.debug)
    log.debug("CLI args: %s", args)

    # 3. Print the startup banner
    _print_banner()

    # 4. Load configuration
    config = load_config(args.config)
    log.debug("Active config keys: %s", list(config.keys()))

    # 5. Create the application orchestrator
    app = JarvisApp(config, args)

    # 6. Wire up signal handlers for graceful shutdown
    global _app
    _app = app
    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    # 7. Initialise all modules
    print("  Initialising modules…")
    print("  ─" * 30)
    app.init_modules()
    print("  ─" * 30)
    print()

    # 8. Start the system (blocks until shutdown)
    try:
        app.start()
    except KeyboardInterrupt:
        log.info("KeyboardInterrupt at top level — forcing shutdown")
        app.shutdown()
    except Exception as exc:
        log.critical("Unrecoverable error: %s", exc, exc_info=True)
        app.shutdown()
        sys.exit(1)


if __name__ == "__main__":
    main()
