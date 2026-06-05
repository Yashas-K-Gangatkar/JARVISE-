"""
Event Bus - Lightweight publish/subscribe event system
for inter-module communication.
"""

import threading
from collections import defaultdict
from queue import Queue


class Event:
    """Represents a system event."""

    def __init__(self, event_type, data=None):
        self.event_type = event_type
        self.data = data or {}
        self.timestamp = None  # Set when published

    def __repr__(self):
        return f"Event(type={self.event_type}, data={self.data})"


# Predefined event types
class EventTypes:
    # Face recognition events
    FACE_DETECTED = "face_detected"
    FACE_RECOGNIZED = "face_recognized"
    FACE_LOST = "face_lost"

    # Gesture events
    GESTURE_DETECTED = "gesture_detected"
    GESTURE_HOLD = "gesture_hold"

    # Voice events
    WAKE_WORD_DETECTED = "wake_word_detected"
    VOICE_COMMAND = "voice_command"
    VOICE_TIMEOUT = "voice_timeout"

    # System events
    SYSTEM_START = "system_start"
    SYSTEM_STOP = "system_stop"
    STATE_CHANGED = "state_changed"

    # Data events
    NEWS_UPDATED = "news_updated"
    STOCKS_UPDATED = "stocks_updated"
    PROJECT_UPDATED = "project_updated"

    # Output events
    SPEAK_REQUEST = "speak_request"
    DASHBOARD_UPDATE = "dashboard_update"
    DASHBOARD_SWITCH_PANEL = "dashboard_switch_panel"


class EventBus:
    """
    Thread-safe publish/subscribe event bus.

    Modules subscribe to event types and receive events when they are published.
    Events are processed sequentially to maintain order.
    """

    def __init__(self):
        self._subscribers = defaultdict(list)
        self._queue = Queue()
        self._lock = threading.Lock()
        self._running = False
        self._processor_thread = None

    def subscribe(self, event_type, callback):
        """
        Subscribe to an event type.

        Args:
            event_type: The event type to listen for (use EventTypes constants)
            callback: Function to call when event is published.
                      Signature: callback(event: Event)
        """
        with self._lock:
            self._subscribers[event_type].append(callback)
        print(f"[EventBus] Subscribed to '{event_type}': {callback.__name__}")

    def unsubscribe(self, event_type, callback):
        """Remove a subscription."""
        with self._lock:
            if callback in self._subscribers[event_type]:
                self._subscribers[event_type].remove(callback)

    def publish(self, event):
        """
        Publish an event to all subscribers.

        Args:
            event: Event object to publish
        """
        import time
        event.timestamp = time.time()
        self._queue.put(event)

    def start_processing(self):
        """Start the event processing loop in a background thread."""
        self._running = True
        self._processor_thread = threading.Thread(
            target=self._process_loop, daemon=True, name="EventBusProcessor"
        )
        self._processor_thread.start()
        print("[EventBus] Started event processing")

    def stop_processing(self):
        """Stop the event processing loop."""
        self._running = False
        # Put a sentinel event to unblock the queue
        self._queue.put(None)
        if self._processor_thread:
            self._processor_thread.join(timeout=2)
        print("[EventBus] Stopped event processing")

    def _process_loop(self):
        """Internal: Process events from the queue."""
        while self._running:
            event = self._queue.get()
            if event is None:
                continue

            with self._lock:
                subscribers = self._subscribers.get(event.event_type, [])

            for callback in subscribers:
                try:
                    callback(event)
                except Exception as e:
                    print(
                        f"[EventBus] Error in subscriber {callback.__name__} "
                        f"for event '{event.event_type}': {e}"
                    )
