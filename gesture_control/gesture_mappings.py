"""
Gesture Mappings - Maps gestures to system actions.

Modify this file to customize which gestures trigger which actions.
"""

# Gesture to action mapping
GESTURE_ACTIONS = {
    "open_palm": {
        "action": "toggle_pause",
        "description": "Pause or resume the assistant",
        "voice_alternative": "Jarvis, pause",
    },
    "thumbs_up": {
        "action": "confirm",
        "description": "Confirm / Yes",
        "voice_alternative": "Yes",
    },
    "thumbs_down": {
        "action": "cancel",
        "description": "Cancel / No",
        "voice_alternative": "No",
    },
    "victory": {
        "action": "switch_panel",
        "description": "Switch to next dashboard panel",
        "voice_alternative": "Next panel",
    },
    "point": {
        "action": "select",
        "description": "Select / Highlight current item",
        "voice_alternative": "Select this",
    },
}


def get_action_for_gesture(gesture_name):
    """
    Get the action associated with a gesture.

    Args:
        gesture_name: Name of the detected gesture

    Returns:
        dict: Action info or None if gesture not mapped
    """
    return GESTURE_ACTIONS.get(gesture_name)


def get_all_gestures():
    """Return all supported gestures and their actions."""
    return dict(GESTURE_ACTIONS)
