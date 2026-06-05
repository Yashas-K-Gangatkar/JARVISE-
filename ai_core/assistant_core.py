"""
Assistant Core - Main application orchestrator and state machine.

States:
    IDLE: No user detected, waiting for face recognition
    ACTIVE: User detected and greeted, listening for commands
    LISTENING: Wake word detected, actively processing voice input
    PROCESSING: Executing a command
    ERROR: Recoverable error state

Enhanced features:
    - Time, weather, date, and open application commands
    - GreetingEngine integration for natural greetings with date summary
    - Delayed face-lost transition (30-second grace period)
    - Startup sequence with initial data fetching
    - Extended gesture-to-action mapping
    - Command history tracking (last 10 commands)
    - Graceful error recovery
"""

import subprocess
import threading
import time
import logging
from collections import deque
from datetime import datetime
from enum import Enum, auto

import requests

from .event_bus import EventBus, Event, EventTypes
from .state_manager import StateManager
from .preferences import Preferences
from face_engine.greeting_engine import GreetingEngine

logger = logging.getLogger(__name__)


class AssistantState(Enum):
    """Possible states of the AI assistant."""
    IDLE = auto()
    ACTIVE = auto()
    LISTENING = auto()
    PROCESSING = auto()
    ERROR = auto()


class AssistantCore:
    """
    Central orchestrator that ties all modules together.

    Manages the application state machine, routes events between modules,
    and implements the decision logic for how the assistant responds.

    Enhanced with time/weather/date/open commands, GreetingEngine-based
    greetings, delayed face-lost handling, startup data fetching,
    extended gesture mappings, command history, and error recovery.
    """

    # How long to wait after face lost before transitioning to IDLE (seconds)
    FACE_LOST_GRACE_PERIOD = 30

    # Maximum number of commands to keep in history
    COMMAND_HISTORY_MAX = 10

    # Known applications that can be opened via the "open" command
    APP_LAUNCHERS = {
        # Generic cross-platform entries (resolved per-OS at launch time)
        "notepad":    {"windows": ["notepad.exe"],                  "linux": ["xdg-open", "gedit"],       "darwin": ["open", "-a", "TextEdit"]},
        "chrome":     {"windows": ["start", "chrome"],             "linux": ["google-chrome", "chromium-browser"], "darwin": ["open", "-a", "Google Chrome"]},
        "calculator": {"windows": ["calc.exe"],                    "linux": ["gnome-calculator"],        "darwin": ["open", "-a", "Calculator"]},
        "terminal":   {"windows": ["wt", "cmd.exe"],              "linux": ["gnome-terminal"],          "darwin": ["open", "-a", "Terminal"]},
        "browser":    {"windows": ["start", "https://www.google.com"], "linux": ["xdg-open", "https://www.google.com"], "darwin": ["open", "https://www.google.com"]},
        "file_manager": {"windows": ["explorer.exe"],             "linux": ["nautilus"],                "darwin": ["open", "."]},
        "spotify":    {"windows": ["start", "spotify"],           "linux": ["spotify"],                 "darwin": ["open", "-a", "Spotify"]},
        "code":       {"windows": ["code"],                       "linux": ["code"],                    "darwin": ["open", "-a", "Visual Studio Code"]},
    }

    def __init__(self, event_bus, config, preferences):
        self.event_bus = event_bus
        self.config = config
        self.preferences = preferences
        self.state_manager = StateManager(AssistantState.IDLE)
        self._running = False
        self._modules = {}

        # Greeting engine – picks up style from user preferences
        greeting_style = preferences.get("greeting_style", "formal")
        self.greeting_engine = GreetingEngine(style=greeting_style)

        # Command history (most-recent-first via deque rotated on append)
        self._command_history = deque(maxlen=self.COMMAND_HISTORY_MAX)

        # Face-lost grace period tracking
        self._face_lost_time = None
        self._face_lost_timer = None
        self._face_lost_lock = threading.Lock()

        # Startup data fetched flag
        self._startup_data_fetched = False

        # Gesture cooldown — ignore the same gesture if it fires again
        # within this many seconds (prevents rapid-fire spam)
        self._gesture_cooldown_seconds = 5.0
        self._last_gesture_time = 0.0
        self._last_gesture_name = ""

        # Detect current OS for app launching
        import platform
        self._os_name = platform.system().lower()  # 'windows', 'linux', 'darwin'

        # Register event handlers
        self._register_handlers()

    # ── Public Interface ──

    def register_module(self, name, module):
        """Register a module with the core."""
        self._modules[name] = module
        print(f"[Core] Registered module: {name}")

    def start(self):
        """Start the assistant and all registered modules."""
        print("[Core] Starting JARVIS-AI...")
        self._running = True

        # Start event bus processing
        self.event_bus.start_processing()

        # Publish system start event (triggers startup sequence)
        self.event_bus.publish(Event(EventTypes.SYSTEM_START))

        # Start all registered modules
        for name, module in self._modules.items():
            try:
                module.start()
                print(f"[Core] Started module: {name}")
            except Exception as e:
                logger.exception("Error starting module %s", name)
                print(f"[Core] Error starting module {name}: {e}")
                self._attempt_error_recovery(f"module_start_{name}", e)

        # Main loop (keeps the application running)
        try:
            while self._running:
                time.sleep(0.1)
        except KeyboardInterrupt:
            self.stop()

    def stop(self):
        """Stop the assistant and all registered modules."""
        print("[Core] Stopping JARVIS-AI...")
        self._running = False

        # Cancel any pending face-lost timer
        self._cancel_face_lost_timer()

        # Stop all registered modules
        for name, module in self._modules.items():
            try:
                module.stop()
                print(f"[Core] Stopped module: {name}")
            except Exception as e:
                logger.exception("Error stopping module %s", name)
                print(f"[Core] Error stopping module {name}: {e}")

        # Stop event bus
        self.event_bus.publish(Event(EventTypes.SYSTEM_STOP))
        self.event_bus.stop_processing()

    # ── Event Registration ──

    def _register_handlers(self):
        """Subscribe to events from input modules."""
        self.event_bus.subscribe(EventTypes.FACE_DETECTED, self._on_face_detected)
        self.event_bus.subscribe(EventTypes.FACE_RECOGNIZED, self._on_face_recognized)
        self.event_bus.subscribe(EventTypes.FACE_LOST, self._on_face_lost)
        self.event_bus.subscribe(EventTypes.GESTURE_DETECTED, self._on_gesture)
        self.event_bus.subscribe(EventTypes.WAKE_WORD_DETECTED, self._on_wake_word)
        self.event_bus.subscribe(EventTypes.VOICE_COMMAND, self._on_voice_command)
        self.event_bus.subscribe(EventTypes.VOICE_TIMEOUT, self._on_voice_timeout)
        self.event_bus.subscribe(EventTypes.SYSTEM_START, self._on_system_start)

    # ── System Lifecycle Handlers ──

    def _on_system_start(self, event):
        """
        Handle SYSTEM_START event.

        Fetches initial data (news, stocks) and prepares the dashboard
        so that information is ready before the user even interacts.
        """
        if self._startup_data_fetched:
            return
        self._startup_data_fetched = True

        print("[Core] Running startup sequence...")

        # Kick off data fetches in background threads so we don't block
        threading.Thread(target=self._startup_fetch_data, daemon=True, name="StartupDataFetch").start()

        # Prepare dashboard with initial state
        self.event_bus.publish(
            Event(EventTypes.DASHBOARD_UPDATE, {
                "state": "IDLE",
                "message": "JARVIS Online. Waiting for user...",
            })
        )

        print("[Core] Startup sequence complete.")

    def _startup_fetch_data(self):
        """Background thread: trigger data manager to fetch news & stocks."""
        dm = self._modules.get("data_manager")
        if dm and hasattr(dm, "_fetch_all"):
            try:
                dm._fetch_all()
                print("[Core] Startup: initial data fetched.")
            except Exception as e:
                logger.warning("Startup data fetch failed: %s", e)
                print(f"[Core] Startup data fetch warning: {e}")
        else:
            print("[Core] Startup: no data_manager module registered; skipping initial fetch.")

    # ── Face Recognition Handlers ──

    def _on_face_detected(self, event):
        """Handle face detected event."""
        # Cancel any pending face-lost timer (user came back)
        self._cancel_face_lost_timer()

        if self.state_manager.current == AssistantState.IDLE:
            self.state_manager.transition(AssistantState.ACTIVE)
            self.event_bus.publish(
                Event(EventTypes.STATE_CHANGED, {"state": "ACTIVE"})
            )
            # Trigger enhanced greeting
            self._greet_user(event.data.get("name", None))

    def _on_face_recognized(self, event):
        """Handle face recognized event (known user)."""
        # Cancel any pending face-lost timer
        self._cancel_face_lost_timer()

        user_name = event.data.get("name", "User")
        if self.state_manager.current == AssistantState.IDLE:
            self.state_manager.transition(AssistantState.ACTIVE)
            self.event_bus.publish(
                Event(EventTypes.STATE_CHANGED, {"state": "ACTIVE"})
            )
            self._greet_user(user_name)

    def _on_face_lost(self, event):
        """
        Handle face lost event.

        Instead of transitioning to IDLE immediately, start a grace-period
        timer.  If the face reappears within FACE_LOST_GRACE_PERIOD seconds
        the timer is cancelled and the state is preserved.  Otherwise the
        state transitions to IDLE after the timer fires.
        """
        if self.state_manager.current not in (AssistantState.ACTIVE, AssistantState.LISTENING):
            return

        with self._face_lost_lock:
            self._face_lost_time = time.time()
            # Cancel any existing timer before starting a new one
            if self._face_lost_timer is not None:
                self._face_lost_timer.cancel()

            self._face_lost_timer = threading.Timer(
                self.FACE_LOST_GRACE_PERIOD,
                self._face_lost_timeout
            )
            self._face_lost_timer.daemon = True
            self._face_lost_timer.start()

        print(f"[Core] Face lost – starting {self.FACE_LOST_GRACE_PERIOD}s grace timer.")

    def _face_lost_timeout(self):
        """Callback executed when the face-lost grace period expires."""
        with self._face_lost_lock:
            self._face_lost_timer = None

        if self.state_manager.current in (AssistantState.ACTIVE, AssistantState.LISTENING):
            print("[Core] Face lost grace period expired – transitioning to IDLE.")
            self.state_manager.transition(AssistantState.IDLE)
            self.event_bus.publish(
                Event(EventTypes.STATE_CHANGED, {"state": "IDLE"})
            )
            self.event_bus.publish(
                Event(EventTypes.SPEAK_REQUEST, {"text": "User left. Going to standby."})
            )

    def _cancel_face_lost_timer(self):
        """Cancel the pending face-lost grace-period timer, if any."""
        with self._face_lost_lock:
            if self._face_lost_timer is not None:
                self._face_lost_timer.cancel()
                self._face_lost_timer = None
                self._face_lost_time = None
                print("[Core] Face-lost timer cancelled.")

    # ── Gesture Handler ──

    def _on_gesture(self, event):
        """Handle gesture detected event."""
        if self.state_manager.current in (AssistantState.ACTIVE, AssistantState.LISTENING):
            gesture = event.data.get("gesture", "unknown")

            # Cooldown: ignore the same gesture if it fired very recently.
            # This prevents the MediaPipe detector from spamming "Confirmed."
            # or "Cancelled." every frame when a hand is held in view.
            now = time.time()
            if (gesture == self._last_gesture_name
                    and now - self._last_gesture_time < self._gesture_cooldown_seconds):
                return  # skip — same gesture too soon
            self._last_gesture_time = now
            self._last_gesture_name = gesture

            self._process_gesture(gesture)

    # ── Voice Handlers ──

    def _on_wake_word(self, event):
        """Handle wake word detected event."""
        if self.state_manager.current == AssistantState.ACTIVE:
            self.state_manager.transition(AssistantState.LISTENING)
            self.event_bus.publish(
                Event(EventTypes.STATE_CHANGED, {"state": "LISTENING"})
            )
            self.event_bus.publish(
                Event(EventTypes.SPEAK_REQUEST, {"text": "Yes, how can I help you?"})
            )

    def _on_voice_command(self, event):
        """Handle voice command event."""
        if self.state_manager.current in (AssistantState.ACTIVE, AssistantState.LISTENING):
            command = event.data.get("command", "")
            params = event.data.get("params", {})
            self._execute_command(command, params)

    def _on_voice_timeout(self, event):
        """Handle voice listening timeout."""
        if self.state_manager.current == AssistantState.LISTENING:
            self.state_manager.transition(AssistantState.ACTIVE)
            self.event_bus.publish(
                Event(EventTypes.STATE_CHANGED, {"state": "ACTIVE"})
            )

    # ── Internal Methods ──

    def _greet_user(self, name=None):
        """
        Generate and speak a natural greeting using the GreetingEngine.

        Includes a date summary for context (e.g. "Today is Monday, March 3, 2025.").
        """
        user_name = name or self.preferences.get("user_name", "User")

        # Use GreetingEngine for the primary greeting
        greeting_message = self.greeting_engine.get_greeting(name=user_name)

        # Append date summary for context
        date_summary = self.greeting_engine.get_date_summary()

        full_message = f"{greeting_message} {date_summary}"

        print(f"[Core] Greeting: {full_message}")
        self.event_bus.publish(
            Event(EventTypes.SPEAK_REQUEST, {"text": full_message})
        )

        # Trigger dashboard update with preferences
        self.event_bus.publish(
            Event(EventTypes.DASHBOARD_UPDATE, {
                "greeting": greeting_message,
                "date_summary": date_summary,
                "show_preferences": True,
            })
        )

    def _process_gesture(self, gesture):
        """
        Map gesture to action.

        Extended mapping includes volume up/down, scroll, and home actions
        beyond the original set.
        """
        gesture_map = {
            "open_palm":   "pause",
            "thumbs_up":   "confirm",
            "thumbs_down":  "cancel",
            "victory":     "switch_panel",
            "point":       "select",
            # ── New gesture mappings ──
            "fist":        "mute",
            "swipe_left":  "previous_panel",
            "swipe_right": "next_panel",
            "swipe_up":    "volume_up",
            "swipe_down":  "volume_down",
            "ok_sign":     "scroll_down",
            "rock":        "home",
        }

        action = gesture_map.get(gesture, None)
        if action is None:
            print(f"[Core] Gesture '{gesture}' not mapped – ignoring.")
            return

        print(f"[Core] Gesture '{gesture}' -> Action '{action}'")

        # ── Action dispatch ──
        if action == "switch_panel":
            self.event_bus.publish(
                Event(EventTypes.DASHBOARD_SWITCH_PANEL, {"direction": "next"})
            )
        elif action == "previous_panel":
            self.event_bus.publish(
                Event(EventTypes.DASHBOARD_SWITCH_PANEL, {"direction": "previous"})
            )
        elif action == "next_panel":
            self.event_bus.publish(
                Event(EventTypes.DASHBOARD_SWITCH_PANEL, {"direction": "next"})
            )
        elif action == "pause":
            self.event_bus.publish(
                Event(EventTypes.SPEAK_REQUEST, {"text": "Paused. Say Jarvis to resume."})
            )
        elif action == "mute":
            self.event_bus.publish(
                Event(EventTypes.SPEAK_REQUEST, {"text": "Microphone muted."})
            )
        elif action == "confirm":
            self.event_bus.publish(
                Event(EventTypes.SPEAK_REQUEST, {"text": "Confirmed."})
            )
        elif action == "cancel":
            self.event_bus.publish(
                Event(EventTypes.SPEAK_REQUEST, {"text": "Cancelled."})
            )
        elif action == "volume_up":
            self.event_bus.publish(
                Event(EventTypes.SPEAK_REQUEST, {"text": "Volume up."})
            )
        elif action == "volume_down":
            self.event_bus.publish(
                Event(EventTypes.SPEAK_REQUEST, {"text": "Volume down."})
            )
        elif action == "home":
            self.event_bus.publish(
                Event(EventTypes.DASHBOARD_SWITCH_PANEL, {"panel": "greeting"})
            )
        elif action == "scroll_down":
            self.event_bus.publish(
                Event(EventTypes.SPEAK_REQUEST, {"text": "Scrolling down."})
            )
        elif action == "select":
            self.event_bus.publish(
                Event(EventTypes.SPEAK_REQUEST, {"text": "Selected."})
            )

    # ── Command Execution ──

    def _execute_command(self, command, params=None):
        """
        Execute a recognized voice command.

        Wraps execution in error recovery so that a failing command
        never crashes the assistant.
        """
        print(f"[Core] Executing command: {command} (params: {params})")

        # Record in command history
        self._command_history.append({
            "command": command,
            "params": params or {},
            "timestamp": datetime.now().isoformat(),
        })

        self.state_manager.transition(AssistantState.PROCESSING)

        command_handlers = {
            "news":    self._cmd_news,
            "stocks":  self._cmd_stocks,
            "project": self._cmd_project,
            "hello":   self._cmd_hello,
            "help":    self._cmd_help,
            "stop":    self._cmd_stop,
            # ── New command handlers ──
            "time":    self._cmd_time,
            "weather": self._cmd_weather,
            "date":    self._cmd_date,
            "open":    self._cmd_open,
        }

        handler = command_handlers.get(command, None)
        if handler:
            try:
                handler(params)
            except Exception as e:
                logger.exception("Command '%s' failed", command)
                print(f"[Core] Command '{command}' failed: {e}")
                self._attempt_error_recovery(command, e)
        else:
            # Unknown command → route to AI chat so the user's question
            # still gets answered instead of getting "I don't understand".
            # Re-publish as a "chat" VOICE_COMMAND which the AIChatModule
            # will pick up.
            raw_text = (params or {}).get("raw_text", command)
            if raw_text:
                self.event_bus.publish(
                    Event(EventTypes.VOICE_COMMAND, {
                        "text": raw_text,
                        "command": "chat",
                        "params": {"raw_text": raw_text},
                    })
                )

        # Return to active state (unless stop was requested)
        if command != "stop" and self.state_manager.current == AssistantState.PROCESSING:
            self.state_manager.transition(AssistantState.ACTIVE)

    # ── Original Command Handlers ──

    def _cmd_news(self, params):
        """Handle news command."""
        self.event_bus.publish(
            Event(EventTypes.SPEAK_REQUEST, {"text": "Fetching today's news..."})
        )
        self.event_bus.publish(
            Event(EventTypes.DASHBOARD_SWITCH_PANEL, {"panel": "news"})
        )

    def _cmd_stocks(self, params):
        """Handle stocks command."""
        self.event_bus.publish(
            Event(EventTypes.SPEAK_REQUEST, {"text": "Checking stock market data..."})
        )
        self.event_bus.publish(
            Event(EventTypes.DASHBOARD_SWITCH_PANEL, {"panel": "stocks"})
        )

    def _cmd_project(self, params):
        """Handle project status command."""
        self.event_bus.publish(
            Event(EventTypes.SPEAK_REQUEST, {"text": "Loading project status..."})
        )
        self.event_bus.publish(
            Event(EventTypes.DASHBOARD_SWITCH_PANEL, {"panel": "project"})
        )

    def _cmd_hello(self, params):
        """Handle hello command."""
        self.event_bus.publish(
            Event(EventTypes.SPEAK_REQUEST, {"text": "Hello! How can I help you today?"})
        )

    def _cmd_help(self, params):
        """Handle help command – list all available commands."""
        self.event_bus.publish(
            Event(EventTypes.SPEAK_REQUEST, {
                "text": (
                    "You can ask me for: news, stocks, project status, "
                    "the current time, today's date, the weather, "
                    "or ask me to open an application like notepad, "
                    "chrome, or calculator. Say stop to end the session."
                )
            })
        )

    def _cmd_stop(self, params):
        """Handle stop command."""
        self.event_bus.publish(
            Event(EventTypes.SPEAK_REQUEST, {"text": "Goodbye!"})
        )
        self.state_manager.transition(AssistantState.IDLE)

    # ── New Command Handlers ──

    def _cmd_time(self, params):
        """Speak the current time."""
        now = datetime.now()
        time_str = now.strftime("%I:%M %p")
        # Strip leading zero for natural speech (e.g. "09:15 PM" → "9:15 PM")
        time_str = time_str.lstrip("0")
        message = f"The current time is {time_str}."
        print(f"[Core] Time: {message}")
        self.event_bus.publish(
            Event(EventTypes.SPEAK_REQUEST, {"text": message})
        )

    def _cmd_weather(self, params):
        """
        Fetch weather using the wttr.in API (no API key required) and speak it.

        Uses a short timeout so the assistant doesn't hang if the network is
        unavailable.  Falls back to a graceful message on any failure.
        """
        # Allow city override via params or preferences
        city = None
        if params and isinstance(params, dict):
            city = params.get("city")
        if not city:
            city = self.preferences.get("city", None)

        try:
            url = "https://wttr.in/"
            if city:
                url = f"https://wttr.in/{city}"
            # Request simple one-line format
            url += "?format=%C+%t+%h+%w"

            response = requests.get(url, timeout=8)
            response.raise_for_status()
            weather_str = response.text.strip()

            if not weather_str:
                raise ValueError("Empty weather response")

            location = f"in {city}" if city else "in your area"
            message = f"The weather {location} is currently: {weather_str}."
        except requests.Timeout:
            message = "I'm sorry, the weather service timed out. Please try again later."
            print("[Core] Weather: request timed out.")
        except requests.RequestException as e:
            message = "I'm sorry, I couldn't fetch the weather right now."
            print(f"[Core] Weather: network error – {e}")
        except Exception as e:
            message = "I'm sorry, something went wrong getting the weather."
            print(f"[Core] Weather: unexpected error – {e}")

        print(f"[Core] Weather: {message}")
        self.event_bus.publish(
            Event(EventTypes.SPEAK_REQUEST, {"text": message})
        )

    def _cmd_date(self, params):
        """Speak today's date."""
        date_summary = self.greeting_engine.get_date_summary()
        message = date_summary
        print(f"[Core] Date: {message}")
        self.event_bus.publish(
            Event(EventTypes.SPEAK_REQUEST, {"text": message})
        )

    def _cmd_open(self, params):
        """
        Try to open a common application.

        The application name is expected in params["app"].
        Supported apps: notepad, chrome, calculator, terminal, browser,
                        file_manager, spotify, code.
        """
        if not params or not isinstance(params, dict):
            self.event_bus.publish(
                Event(EventTypes.SPEAK_REQUEST, {
                    "text": "Which application would you like me to open?"
                })
            )
            return

        app_name = params.get("app", "").lower().strip()
        if not app_name:
            self.event_bus.publish(
                Event(EventTypes.SPEAK_REQUEST, {
                    "text": "Which application would you like me to open?"
                })
            )
            return

        launcher_info = self.APP_LAUNCHERS.get(app_name)
        if launcher_info is None:
            self.event_bus.publish(
                Event(EventTypes.SPEAK_REQUEST, {
                    "text": f"I'm sorry, I don't know how to open {app_name}."
                })
            )
            return

        # Pick the right command list for the current OS
        os_key = self._os_name  # 'windows', 'linux', or 'darwin'
        cmd_list = launcher_info.get(os_key)
        if cmd_list is None:
            # Fallback: try linux commands on unknown OS
            cmd_list = launcher_info.get("linux", [])

        try:
            subprocess.Popen(cmd_list, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            message = f"Opening {app_name}."
        except FileNotFoundError:
            message = f"I couldn't find {app_name} on this system."
            print(f"[Core] Open: executable not found for {app_name} – tried {cmd_list}")
        except Exception as e:
            message = f"I had trouble opening {app_name}."
            print(f"[Core] Open: error launching {app_name} – {e}")

        print(f"[Core] Open: {message}")
        self.event_bus.publish(
            Event(EventTypes.SPEAK_REQUEST, {"text": message})
        )

    # ── Command History ──

    def get_command_history(self):
        """
        Return the last N commands executed.

        Returns:
            list[dict]: Most recent commands, newest last.
        """
        return list(self._command_history)

    # ── Error Recovery ──

    def _attempt_error_recovery(self, context, error):
        """
        Attempt to recover from an error gracefully.

        Strategies:
            1. If we're in PROCESSING state, return to ACTIVE so the user
               isn't stuck.
            2. If we're in ERROR state, try to go back to IDLE or ACTIVE.
            3. Always inform the user that something went wrong.
        """
        print(f"[Core] Error recovery triggered for context '{context}': {error}")

        # Inform the user
        self.event_bus.publish(
            Event(EventTypes.SPEAK_REQUEST, {
                "text": "I encountered a problem, but I'm still here. How can I help?"
            })
        )

        # State cleanup
        current = self.state_manager.current
        if current == AssistantState.PROCESSING:
            self.state_manager.transition(AssistantState.ACTIVE)
            self.event_bus.publish(
                Event(EventTypes.STATE_CHANGED, {"state": "ACTIVE"})
            )
        elif current == AssistantState.ERROR:
            # Try to go back to IDLE; if that's invalid, try ACTIVE
            if not self.state_manager.transition(AssistantState.IDLE):
                self.state_manager.transition(AssistantState.ACTIVE)
            self.event_bus.publish(
                Event(EventTypes.STATE_CHANGED, {"state": self.state_manager.current.name})
            )

        logger.info("Error recovery completed – state is now %s", self.state_manager.current.name)
