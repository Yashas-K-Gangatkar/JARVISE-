"""
Assistant Core - Main application orchestrator and state machine.

States:
    IDLE: No user detected, waiting for face recognition
    ACTIVE: User detected and greeted, listening for commands
    LISTENING: Wake word detected, actively processing voice input
    PROCESSING: Executing a command
    ERROR: Recoverable error state
"""

import threading
import time
from enum import Enum, auto

from .event_bus import EventBus, Event, EventTypes
from .state_manager import StateManager
from .preferences import Preferences


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
    """

    def __init__(self, event_bus, config, preferences):
        self.event_bus = event_bus
        self.config = config
        self.preferences = preferences
        self.state_manager = StateManager(AssistantState.IDLE)
        self._running = False
        self._modules = {}

        # Register event handlers
        self._register_handlers()

    def _register_handlers(self):
        """Subscribe to events from input modules."""
        self.event_bus.subscribe(EventTypes.FACE_DETECTED, self._on_face_detected)
        self.event_bus.subscribe(EventTypes.FACE_RECOGNIZED, self._on_face_recognized)
        self.event_bus.subscribe(EventTypes.FACE_LOST, self._on_face_lost)
        self.event_bus.subscribe(EventTypes.GESTURE_DETECTED, self._on_gesture)
        self.event_bus.subscribe(EventTypes.WAKE_WORD_DETECTED, self._on_wake_word)
        self.event_bus.subscribe(EventTypes.VOICE_COMMAND, self._on_voice_command)
        self.event_bus.subscribe(EventTypes.VOICE_TIMEOUT, self._on_voice_timeout)

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

        # Publish system start event
        self.event_bus.publish(Event(EventTypes.SYSTEM_START))

        # Start all registered modules
        for name, module in self._modules.items():
            try:
                module.start()
                print(f"[Core] Started module: {name}")
            except Exception as e:
                print(f"[Core] Error starting module {name}: {e}")

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

        # Stop all registered modules
        for name, module in self._modules.items():
            try:
                module.stop()
                print(f"[Core] Stopped module: {name}")
            except Exception as e:
                print(f"[Core] Error stopping module {name}: {e}")

        # Stop event bus
        self.event_bus.publish(Event(EventTypes.SYSTEM_STOP))
        self.event_bus.stop_processing()

    # ── Event Handlers ──

    def _on_face_detected(self, event):
        """Handle face detected event."""
        if self.state_manager.current == AssistantState.IDLE:
            self.state_manager.transition(AssistantState.ACTIVE)
            self.event_bus.publish(
                Event(EventTypes.STATE_CHANGED, {"state": "ACTIVE"})
            )
            # Trigger greeting
            self._greet_user(event.data.get("name", None))

    def _on_face_recognized(self, event):
        """Handle face recognized event (known user)."""
        user_name = event.data.get("name", "User")
        if self.state_manager.current == AssistantState.IDLE:
            self.state_manager.transition(AssistantState.ACTIVE)
            self.event_bus.publish(
                Event(EventTypes.STATE_CHANGED, {"state": "ACTIVE"})
            )
            self._greet_user(user_name)

    def _on_face_lost(self, event):
        """Handle face lost event."""
        if self.state_manager.current in (AssistantState.ACTIVE, AssistantState.LISTENING):
            self.state_manager.transition(AssistantState.IDLE)
            self.event_bus.publish(
                Event(EventTypes.STATE_CHANGED, {"state": "IDLE"})
            )

    def _on_gesture(self, event):
        """Handle gesture detected event."""
        if self.state_manager.current in (AssistantState.ACTIVE, AssistantState.LISTENING):
            gesture = event.data.get("gesture", "unknown")
            self._process_gesture(gesture)

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
        """Generate and speak a time-appropriate greeting."""
        from datetime import datetime

        hour = datetime.now().hour
        if hour < 12:
            greeting = "Good Morning"
        elif hour < 17:
            greeting = "Good Afternoon"
        else:
            greeting = "Good Evening"

        if name:
            message = f"{greeting}, {name}!"
        else:
            message = f"{greeting}!"

        print(f"[Core] Greeting: {message}")
        self.event_bus.publish(
            Event(EventTypes.SPEAK_REQUEST, {"text": message})
        )

        # Trigger dashboard update with preferences
        self.event_bus.publish(
            Event(EventTypes.DASHBOARD_UPDATE, {
                "greeting": message,
                "show_preferences": True,
            })
        )

    def _process_gesture(self, gesture):
        """Map gesture to action."""
        gesture_map = {
            "open_palm": "pause",
            "thumbs_up": "confirm",
            "thumbs_down": "cancel",
            "victory": "switch_panel",
            "point": "select",
        }

        action = gesture_map.get(gesture, None)
        if action:
            print(f"[Core] Gesture '{gesture}' -> Action '{action}'")
            if action == "switch_panel":
                self.event_bus.publish(
                    Event(EventTypes.DASHBOARD_SWITCH_PANEL, {"direction": "next"})
                )
            elif action == "pause":
                self.event_bus.publish(
                    Event(EventTypes.SPEAK_REQUEST, {"text": "Paused. Say Jarvis to resume."})
                )

    def _execute_command(self, command, params=None):
        """Execute a recognized voice command."""
        print(f"[Core] Executing command: {command} (params: {params})")
        self.state_manager.transition(AssistantState.PROCESSING)

        command_handlers = {
            "news": self._cmd_news,
            "stocks": self._cmd_stocks,
            "project": self._cmd_project,
            "hello": self._cmd_hello,
            "help": self._cmd_help,
            "stop": self._cmd_stop,
        }

        handler = command_handlers.get(command, None)
        if handler:
            handler(params)
        else:
            self.event_bus.publish(
                Event(EventTypes.SPEAK_REQUEST, {
                    "text": f"Sorry, I don't understand the command: {command}"
                })
            )

        # Return to active state
        self.state_manager.transition(AssistantState.ACTIVE)

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
        """Handle help command."""
        self.event_bus.publish(
            Event(EventTypes.SPEAK_REQUEST, {
                "text": "You can ask me for news, stocks, project status, or say help for this menu."
            })
        )

    def _cmd_stop(self, params):
        """Handle stop command."""
        self.event_bus.publish(
            Event(EventTypes.SPEAK_REQUEST, {"text": "Goodbye!"})
        )
        self.state_manager.transition(AssistantState.IDLE)
