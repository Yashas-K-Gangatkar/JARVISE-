"""
State Manager - Tracks and transitions application state.
"""

import threading


class StateManager:
    """
    Thread-safe state manager with transition validation.

    Ensures that state transitions follow the defined rules,
    preventing invalid transitions (e.g., IDLE -> PROCESSING).
    """

    # Valid state transitions
    VALID_TRANSITIONS = {
        "IDLE": ["ACTIVE"],
        "ACTIVE": ["IDLE", "LISTENING", "PROCESSING", "ERROR"],
        "LISTENING": ["IDLE", "ACTIVE", "PROCESSING", "ERROR"],
        "PROCESSING": ["ACTIVE", "IDLE", "ERROR"],
        "ERROR": ["IDLE", "ACTIVE"],
    }

    def __init__(self, initial_state):
        self._state = initial_state
        self._lock = threading.Lock()
        self._listeners = []

    @property
    def current(self):
        """Get the current state."""
        return self._state

    def transition(self, new_state):
        """
        Attempt to transition to a new state.

        Args:
            new_state: The target state

        Returns:
            bool: True if transition was successful, False otherwise
        """
        with self._lock:
            current_name = self._state.name
            new_name = new_state.name

            valid_targets = self.VALID_TRANSITIONS.get(current_name, [])

            if new_name in valid_targets:
                old_state = self._state
                self._state = new_state
                print(f"[StateManager] {old_state.name} -> {new_state.name}")
                self._notify_listeners(old_state, new_state)
                return True
            else:
                print(
                    f"[StateManager] Invalid transition: "
                    f"{current_name} -> {new_name} "
                    f"(valid: {valid_targets})"
                )
                return False

    def add_listener(self, callback):
        """
        Add a state change listener.

        Args:
            callback: Function called on state change.
                      Signature: callback(old_state, new_state)
        """
        self._listeners.append(callback)

    def _notify_listeners(self, old_state, new_state):
        """Notify all listeners of a state change."""
        for listener in self._listeners:
            try:
                listener(old_state, new_state)
            except Exception as e:
                print(f"[StateManager] Listener error: {e}")
