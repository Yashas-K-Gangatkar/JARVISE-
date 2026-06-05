"""
Smart Home Module - Device control, scene management, and voice integration.

Supports two operational modes:

* **Simulation** (default) — All device states are tracked in memory.
  Perfect for demos and presentations; no real hardware required.
* **Home Assistant** — Connects to a Home Assistant instance via its
  REST API and controls real IoT devices.

Voice commands are routed through the EventBus (VOICE_COMMAND events
with ``command == "home"``) and confirmations are published as
SPEAK_REQUEST / DASHBOARD_UPDATE events.
"""

import copy
import logging
import re
import threading
from typing import Any, Dict, List, Optional, Tuple

from ai_core.event_bus import Event, EventTypes

from .home_assistant_client import (
    HomeAssistantClient,
    HomeAssistantClientError,
)

logger = logging.getLogger("jarvis.smart_home")

# ======================================================================
# Device type constants
# ======================================================================

DEVICE_LIGHT = "light"
DEVICE_FAN = "fan"
DEVICE_SWITCH = "switch"
DEVICE_LOCK = "lock"
DEVICE_CURTAIN = "curtain"
DEVICE_TV = "tv"

# All supported device types
SUPPORTED_DEVICE_TYPES = {
    DEVICE_LIGHT,
    DEVICE_FAN,
    DEVICE_SWITCH,
    DEVICE_LOCK,
    DEVICE_CURTAIN,
    DEVICE_TV,
}

# Default state templates per device type
_DEFAULT_DEVICE_STATE = {
    DEVICE_LIGHT: {"on": False, "brightness": 100, "color": "white"},
    DEVICE_FAN: {"on": False, "speed": "medium"},
    DEVICE_SWITCH: {"on": False},
    DEVICE_LOCK: {"locked": False},
    DEVICE_CURTAIN: {"position": 0},  # 0 = closed, 100 = open
    DEVICE_TV: {"on": False, "volume": 50, "channel": 1},
}

# ======================================================================
# Default room / device configuration
# ======================================================================

_DEFAULT_ROOMS: Dict[str, Any] = {
    "living_room": {
        "display_name": "Living Room",
        "devices": [
            {"name": "Main Light", "type": DEVICE_LIGHT},
            {"name": "TV", "type": DEVICE_TV},
            {"name": "AC", "type": DEVICE_FAN},
            {"name": "Curtains", "type": DEVICE_CURTAIN},
        ],
    },
    "bedroom": {
        "display_name": "Bedroom",
        "devices": [
            {"name": "Light", "type": DEVICE_LIGHT},
            {"name": "Fan", "type": DEVICE_FAN},
            {"name": "Curtains", "type": DEVICE_CURTAIN},
        ],
    },
    "kitchen": {
        "display_name": "Kitchen",
        "devices": [
            {"name": "Light", "type": DEVICE_LIGHT},
        ],
    },
    "bathroom": {
        "display_name": "Bathroom",
        "devices": [
            {"name": "Light", "type": DEVICE_LIGHT},
            {"name": "Exhaust Fan", "type": DEVICE_FAN},
        ],
    },
    "office": {
        "display_name": "Office",
        "devices": [
            {"name": "Light", "type": DEVICE_LIGHT},
            {"name": "Smart Plug", "type": DEVICE_SWITCH},
        ],
    },
    "front_door": {
        "display_name": "Front Door",
        "devices": [
            {"name": "Door Lock", "type": DEVICE_LOCK},
        ],
    },
}

# ======================================================================
# Scene definitions
# ======================================================================

_SCENES: Dict[str, Dict[str, Any]] = {
    "goodnight": {
        "description": "Good night — all lights off, doors locked, AC at 24 °C",
        "actions": {
            # room → list of (device_index, action, params)
            "living_room": [
                {"device": "Main Light", "action": "turn_off"},
                {"device": "TV", "action": "turn_off"},
            ],
            "bedroom": [
                {"device": "Light", "action": "turn_off"},
                {"device": "Fan", "action": "turn_on", "params": {"speed": "low"}},
            ],
            "kitchen": [
                {"device": "Light", "action": "turn_off"},
            ],
            "bathroom": [
                {"device": "Light", "action": "turn_off"},
            ],
            "office": [
                {"device": "Light", "action": "turn_off"},
                {"device": "Smart Plug", "action": "turn_off"},
            ],
            "front_door": [
                {"device": "Door Lock", "action": "lock"},
            ],
        },
    },
    "goodmorning": {
        "description": "Good morning — bedroom light at 30 %, curtains open",
        "actions": {
            "bedroom": [
                {"device": "Light", "action": "turn_on", "params": {"brightness": 30}},
                {"device": "Curtains", "action": "open"},
            ],
            "kitchen": [
                {"device": "Light", "action": "turn_on"},
            ],
            "front_door": [
                {"device": "Door Lock", "action": "unlock"},
            ],
        },
    },
    "movie": {
        "description": "Movie mode — lights dim, TV on, curtains closed",
        "actions": {
            "living_room": [
                {"device": "Main Light", "action": "turn_on", "params": {"brightness": 15}},
                {"device": "TV", "action": "turn_on"},
                {"device": "Curtains", "action": "close"},
            ],
        },
    },
    "away": {
        "description": "Away mode — everything off, doors locked",
        "actions": {
            "living_room": [
                {"device": "Main Light", "action": "turn_off"},
                {"device": "TV", "action": "turn_off"},
                {"device": "AC", "action": "turn_off"},
                {"device": "Curtains", "action": "close"},
            ],
            "bedroom": [
                {"device": "Light", "action": "turn_off"},
                {"device": "Fan", "action": "turn_off"},
            ],
            "kitchen": [
                {"device": "Light", "action": "turn_off"},
            ],
            "bathroom": [
                {"device": "Light", "action": "turn_off"},
            ],
            "office": [
                {"device": "Light", "action": "turn_off"},
                {"device": "Smart Plug", "action": "turn_off"},
            ],
            "front_door": [
                {"device": "Door Lock", "action": "lock"},
            ],
        },
    },
}

# ======================================================================
# Colour name → hex lookup
# ======================================================================

COLOR_MAP: Dict[str, str] = {
    "red": "#FF0000",
    "green": "#00FF00",
    "blue": "#0000FF",
    "white": "#FFFFFF",
    "yellow": "#FFFF00",
    "orange": "#FFA500",
    "purple": "#800080",
    "pink": "#FFC0CB",
    "cyan": "#00FFFF",
    "magenta": "#FF00FF",
    "warm white": "#FDF4E3",
    "cool white": "#E0FFFF",
}

# Fan speed presets
FAN_SPEEDS = ["low", "medium", "high"]

# ======================================================================
# Voice-command keyword tables
# ======================================================================

# Room aliases — maps lower-case keyword → canonical room key
_ROOM_ALIASES: Dict[str, str] = {
    "living room": "living_room",
    "living": "living_room",
    "bedroom": "bedroom",
    "bed": "bedroom",
    "kitchen": "kitchen",
    "bath": "bathroom",
    "bathroom": "bathroom",
    "washroom": "bathroom",
    "office": "office",
    "study": "office",
    "front door": "front_door",
    "door": "front_door",
    "entrance": "front_door",
}

# Device-type keyword aliases
_DEVICE_TYPE_ALIASES: Dict[str, str] = {
    "light": DEVICE_LIGHT,
    "lights": DEVICE_LIGHT,
    "lamp": DEVICE_LIGHT,
    "fan": DEVICE_FAN,
    "ac": DEVICE_FAN,
    "air conditioner": DEVICE_FAN,
    "aircon": DEVICE_FAN,
    "tv": DEVICE_TV,
    "television": DEVICE_TV,
    "plug": DEVICE_SWITCH,
    "smart plug": DEVICE_SWITCH,
    "socket": DEVICE_SWITCH,
    "lock": DEVICE_LOCK,
    "door lock": DEVICE_LOCK,
    "door": DEVICE_LOCK,
    "curtain": DEVICE_CURTAIN,
    "curtains": DEVICE_CURTAIN,
    "blinds": DEVICE_CURTAIN,
}


# ======================================================================
# Main module
# ======================================================================


class SmartHomeModule:
    """
    Smart home control module for the JARVIS AI Assistant.

    Features:
        * Simulation mode (no real devices) and Home Assistant mode.
        * Per-room device management.
        * Voice-command parsing (via EventBus VOICE_COMMAND).
        * Scene execution (goodnight, goodmorning, movie, away).
        * SPEAK_REQUEST confirmations and DASHBOARD_UPDATE events.

    Args:
        event_bus: The application EventBus instance.
        config: Full application config dict; ``config["smart_home"]``
                is used for module-specific settings.
    """

    def __init__(self, event_bus, config: dict):
        self.event_bus = event_bus
        self.config = config.get("smart_home", {})
        self._running = False
        self._lock = threading.Lock()

        # ── Mode ───────────────────────────────────────────────────────
        self._mode = self.config.get("mode", "simulation")

        # ── Rooms & devices ────────────────────────────────────────────
        # Merge user config rooms into defaults
        self._rooms: Dict[str, Any] = self._build_rooms()

        # Runtime state per device  {room_key: {device_name: {...state}}}
        self._device_states: Dict[str, Dict[str, Dict[str, Any]]] = {}
        self._init_device_states()

        # ── Home Assistant client (lazy) ───────────────────────────────
        self._ha_client: Optional[HomeAssistantClient] = None

        # ── Scenes ─────────────────────────────────────────────────────
        self._scenes: Dict[str, Dict[str, Any]] = copy.deepcopy(_SCENES)

        # ── EventBus subscription ──────────────────────────────────────
        self.event_bus.subscribe(
            EventTypes.VOICE_COMMAND, self._on_voice_command
        )
        logger.info(
            "SmartHomeModule created (mode=%s, rooms=%s)",
            self._mode,
            list(self._rooms.keys()),
        )

    # ==================================================================
    # Room / device initialisation helpers
    # ==================================================================

    def _build_rooms(self) -> Dict[str, Any]:
        """Merge user-supplied room config into defaults."""
        rooms = copy.deepcopy(_DEFAULT_ROOMS)
        user_rooms = self.config.get("rooms", {})

        for room_key, room_cfg in user_rooms.items():
            if room_key in rooms:
                # Merge — user devices override defaults for this room
                if "devices" in room_cfg:
                    rooms[room_key]["devices"] = room_cfg["devices"]
                if "display_name" in room_cfg:
                    rooms[room_key]["display_name"] = room_cfg["display_name"]
            else:
                # New room from user config
                rooms[room_key] = {
                    "display_name": room_cfg.get("display_name", room_key.replace("_", " ").title()),
                    "devices": room_cfg.get("devices", []),
                }

        return rooms

    def _init_device_states(self):
        """Populate the in-memory device state map from room definitions."""
        self._device_states = {}
        for room_key, room_data in self._rooms.items():
            self._device_states[room_key] = {}
            for dev_cfg in room_data.get("devices", []):
                name = dev_cfg["name"]
                dtype = dev_cfg.get("type", DEVICE_SWITCH)
                # Start with the default template for this device type
                default = copy.deepcopy(_DEFAULT_DEVICE_STATE.get(dtype, {"on": False}))
                # If the device config includes an entity_id (for HA mode),
                # store it alongside the state
                default["_type"] = dtype
                if "entity_id" in dev_cfg:
                    default["_entity_id"] = dev_cfg["entity_id"]
                self._device_states[room_key][name] = default

    # ==================================================================
    # Public lifecycle
    # ==================================================================

    def start(self):
        """Start the smart-home module."""
        self._running = True

        if self._mode == "home_assistant":
            self._init_ha_client()

        logger.info("SmartHomeModule started (mode=%s)", self._mode)
        print(f"[SmartHome] Started — mode: {self._mode}")

    def stop(self):
        """Stop the smart-home module and release resources."""
        self._running = False

        if self._ha_client is not None:
            try:
                self._ha_client.close()
            except Exception:
                pass
            self._ha_client = None

        logger.info("SmartHomeModule stopped")
        print("[SmartHome] Stopped")

    # ==================================================================
    # Home Assistant client initialisation
    # ==================================================================

    def _init_ha_client(self):
        """Create (or re-create) the Home Assistant REST client."""
        url = self.config.get("home_assistant_url", "http://localhost:8123")
        token = self.config.get("home_assistant_token", "")

        if not token:
            logger.warning(
                "Home Assistant mode selected but no token configured. "
                "Falling back to simulation mode."
            )
            self._mode = "simulation"
            return

        self._ha_client = HomeAssistantClient(url=url, token=token)

        # Verify connectivity
        try:
            if self._ha_client.is_connected():
                logger.info("Connected to Home Assistant at %s", url)
                print(f"[SmartHome] Connected to Home Assistant at {url}")
                # Sync initial states from HA
                self._sync_ha_states()
            else:
                logger.warning(
                    "Home Assistant at %s is reachable but returned "
                    "an unexpected response. Falling back to simulation.",
                    url,
                )
                self._mode = "simulation"
        except Exception as exc:
            logger.warning(
                "Cannot reach Home Assistant at %s: %s — "
                "falling back to simulation mode.",
                url,
                exc,
            )
            self._mode = "simulation"

    def _sync_ha_states(self):
        """
        Pull current states from Home Assistant and update the
        in-memory state map for entities whose entity_id is known.
        """
        if self._ha_client is None:
            return

        try:
            all_states = self._ha_client.get_states()
            # Build an entity_id → state dict
            ha_state_map: Dict[str, Dict[str, Any]] = {
                s["entity"]: s for s in all_states if "entity" in s
            }
            # Also try the "entity_id" key (older HA versions)
            for s in all_states:
                eid = s.get("entity_id") or s.get("entity")
                if eid:
                    ha_state_map[eid] = s

            for room_key, devices in self._device_states.items():
                for dev_name, dev_state in devices.items():
                    entity_id = dev_state.get("_entity_id")
                    if entity_id and entity_id in ha_state_map:
                        ha_data = ha_state_map[entity_id]
                        self._apply_ha_state(dev_state, ha_data)
        except Exception as exc:
            logger.error("Failed to sync HA states: %s", exc)

    def _apply_ha_state(self, dev_state: dict, ha_data: dict):
        """Map a Home Assistant state dict into our internal state."""
        ha_state_val = ha_data.get("state", "")
        attrs = ha_data.get("attributes", {})
        dtype = dev_state.get("_type", DEVICE_SWITCH)

        if dtype == DEVICE_LIGHT:
            dev_state["on"] = ha_state_val == "on"
            dev_state["brightness"] = attrs.get("brightness", 255) // 255 * 100
            # Color is complex; just store the HA attribute if present
            if "rgb_color" in attrs:
                dev_state["color"] = f"rgb{tuple(attrs['rgb_color'])}"
        elif dtype == DEVICE_FAN:
            dev_state["on"] = ha_state_val == "on"
            dev_state["speed"] = attrs.get("speed", "medium")
        elif dtype == DEVICE_SWITCH:
            dev_state["on"] = ha_state_val == "on"
        elif dtype == DEVICE_LOCK:
            dev_state["locked"] = ha_state_val == "locked"
        elif dtype == DEVICE_CURTAIN:
            dev_state["position"] = attrs.get("current_position", 0)
        elif dtype == DEVICE_TV:
            dev_state["on"] = ha_state_val == "on"
            dev_state["volume"] = int(attrs.get("volume_level", 0.5) * 100)
            dev_state["channel"] = attrs.get("source", "1")

    # ==================================================================
    # Core device control
    # ==================================================================

    def control_device(
        self,
        room: str,
        device: str,
        action: str,
        params: Optional[dict] = None,
    ) -> dict:
        """
        Control a single device.

        Args:
            room: Room key (e.g. ``"living_room"``) or ``"all"`` to
                  target matching devices in every room.
            device: Device name (e.g. ``"Main Light"``) or a device-type
                    keyword (e.g. ``"lights"``).
            action: One of ``"turn_on"``, ``"turn_off"``, ``"toggle"``,
                    ``"lock"``, ``"unlock"``, ``"open"``, ``"close"``,
                    ``"set_brightness"``, ``"set_color"``, ``"set_speed"``.
            params: Action-specific parameters (brightness %, color, speed).

        Returns:
            Dict with ``"success"`` (bool) and a ``"message"`` (str).
        """
        params = params or {}

        if room == "all":
            return self._control_all_rooms(device, action, params)

        # Normalise room key
        room_key = self._normalise_room_key(room)
        if room_key is None:
            msg = f"Room '{room}' not found"
            logger.warning(msg)
            return {"success": False, "message": msg}

        # Resolve device name(s)
        device_names = self._resolve_device_names(room_key, device)
        if not device_names:
            msg = f"Device '{device}' not found in {self._rooms[room_key]['display_name']}"
            logger.warning(msg)
            return {"success": False, "message": msg}

        results: List[dict] = []
        for dev_name in device_names:
            res = self._execute_device_action(room_key, dev_name, action, params)
            results.append(res)

        # Build a combined response
        if all(r["success"] for r in results):
            combined_msg = "; ".join(r["message"] for r in results)
            self._speak(combined_msg)
            self._publish_dashboard_update()
            return {"success": True, "message": combined_msg}
        else:
            errors = [r["message"] for r in results if not r["success"]]
            combined_msg = "; ".join(errors)
            return {"success": False, "message": combined_msg}

    def _control_all_rooms(
        self, device: str, action: str, params: dict
    ) -> dict:
        """Apply an action to matching devices across all rooms."""
        results: List[dict] = []
        for room_key in self._rooms:
            device_names = self._resolve_device_names(room_key, device)
            for dev_name in device_names:
                res = self._execute_device_action(room_key, dev_name, action, params)
                results.append(res)

        if not results:
            msg = f"No matching devices found for '{device}'"
            return {"success": False, "message": msg}

        if all(r["success"] for r in results):
            self._speak(results[0]["message"])
            self._publish_dashboard_update()
            return {"success": True, "message": results[0]["message"]}
        else:
            errors = [r["message"] for r in results if not r["success"]]
            return {"success": False, "message": "; ".join(errors)}

    def _execute_device_action(
        self,
        room_key: str,
        device_name: str,
        action: str,
        params: dict,
    ) -> dict:
        """Execute a single action on a single device (simulation or HA)."""
        with self._lock:
            dev_state = self._device_states.get(room_key, {}).get(device_name)
            if dev_state is None:
                return {"success": False, "message": f"Device '{device_name}' not found"}

            dtype = dev_state.get("_type", DEVICE_SWITCH)
            display_room = self._rooms[room_key]["display_name"]

            if self._mode == "home_assistant" and self._ha_client is not None:
                return self._execute_ha_action(
                    room_key, device_name, dev_state, dtype, action, params, display_room
                )
            else:
                return self._execute_sim_action(
                    room_key, device_name, dev_state, dtype, action, params, display_room
                )

    # ------------------------------------------------------------------
    # Simulation-mode execution
    # ------------------------------------------------------------------

    def _execute_sim_action(
        self,
        room_key: str,
        device_name: str,
        dev_state: dict,
        dtype: str,
        action: str,
        params: dict,
        display_room: str,
    ) -> dict:
        """Simulate a device action in memory."""

        if action == "turn_on":
            dev_state["on"] = True
            if "brightness" in params and dtype == DEVICE_LIGHT:
                dev_state["brightness"] = self._clamp_brightness(params["brightness"])
            if "speed" in params and dtype == DEVICE_FAN:
                dev_state["speed"] = params["speed"]
            if "color" in params and dtype == DEVICE_LIGHT:
                dev_state["color"] = params["color"]
            msg = f"{device_name} in {display_room} turned on"
            logger.info("[SIM] %s", msg)

        elif action == "turn_off":
            if dtype == DEVICE_LOCK:
                dev_state["locked"] = False
                msg = f"{device_name} in {display_room} unlocked"
            elif dtype == DEVICE_CURTAIN:
                dev_state["position"] = 0
                msg = f"{device_name} in {display_room} closed"
            else:
                dev_state["on"] = False
                msg = f"{device_name} in {display_room} turned off"
            logger.info("[SIM] %s", msg)

        elif action == "toggle":
            if dtype == DEVICE_LOCK:
                dev_state["locked"] = not dev_state.get("locked", False)
                state_word = "locked" if dev_state["locked"] else "unlocked"
                msg = f"{device_name} in {display_room} {state_word}"
            elif dtype == DEVICE_CURTAIN:
                dev_state["position"] = 0 if dev_state.get("position", 0) > 0 else 100
                state_word = "opened" if dev_state["position"] > 0 else "closed"
                msg = f"{device_name} in {display_room} {state_word}"
            else:
                dev_state["on"] = not dev_state.get("on", False)
                state_word = "on" if dev_state["on"] else "off"
                msg = f"{device_name} in {display_room} turned {state_word}"
            logger.info("[SIM] %s", msg)

        elif action == "lock":
            dev_state["locked"] = True
            msg = f"{device_name} in {display_room} locked"
            logger.info("[SIM] %s", msg)

        elif action == "unlock":
            dev_state["locked"] = False
            msg = f"{device_name} in {display_room} unlocked"
            logger.info("[SIM] %s", msg)

        elif action == "open":
            if dtype == DEVICE_CURTAIN:
                dev_state["position"] = 100
                msg = f"{device_name} in {display_room} opened"
            else:
                dev_state["on"] = True
                msg = f"{device_name} in {display_room} turned on"
            logger.info("[SIM] %s", msg)

        elif action == "close":
            if dtype == DEVICE_CURTAIN:
                dev_state["position"] = 0
                msg = f"{device_name} in {display_room} closed"
            else:
                dev_state["on"] = False
                msg = f"{device_name} in {display_room} turned off"
            logger.info("[SIM] %s", msg)

        elif action == "set_brightness":
            if dtype != DEVICE_LIGHT:
                return {"success": False, "message": f"{device_name} does not support brightness"}
            brightness = self._clamp_brightness(params.get("brightness", 50))
            dev_state["brightness"] = brightness
            msg = f"{device_name} brightness set to {brightness}%"
            logger.info("[SIM] %s", msg)

        elif action == "set_color":
            if dtype != DEVICE_LIGHT:
                return {"success": False, "message": f"{device_name} does not support color"}
            color = params.get("color", "white")
            dev_state["color"] = color
            msg = f"{device_name} color set to {color}"
            logger.info("[SIM] %s", msg)

        elif action == "set_speed":
            if dtype != DEVICE_FAN:
                return {"success": False, "message": f"{device_name} does not support speed"}
            speed = params.get("speed", "medium")
            if speed not in FAN_SPEEDS:
                speed = "medium"
            dev_state["speed"] = speed
            msg = f"{device_name} speed set to {speed}"
            logger.info("[SIM] %s", msg)

        elif action == "set_volume":
            if dtype != DEVICE_TV:
                return {"success": False, "message": f"{device_name} does not support volume"}
            volume = max(0, min(100, params.get("volume", 50)))
            dev_state["volume"] = volume
            msg = f"{device_name} volume set to {volume}%"
            logger.info("[SIM] %s", msg)

        else:
            return {"success": False, "message": f"Unknown action: {action}"}

        return {"success": True, "message": msg}

    # ------------------------------------------------------------------
    # Home-Assistant-mode execution
    # ------------------------------------------------------------------

    def _execute_ha_action(
        self,
        room_key: str,
        device_name: str,
        dev_state: dict,
        dtype: str,
        action: str,
        params: dict,
        display_room: str,
    ) -> dict:
        """Execute a device action through Home Assistant."""

        entity_id = dev_state.get("_entity_id")
        if not entity_id:
            # No HA entity mapped — fall back to simulation for this device
            logger.warning(
                "No entity_id for %s/%s — falling back to simulation",
                room_key, device_name,
            )
            return self._execute_sim_action(
                room_key, device_name, dev_state, dtype, action, params, display_room
            )

        try:
            if action == "turn_on":
                ha_params = {}
                if "brightness" in params and dtype == DEVICE_LIGHT:
                    ha_params["brightness"] = int(params["brightness"] * 255 / 100)
                if "color" in params and dtype == DEVICE_LIGHT:
                    color_hex = COLOR_MAP.get(params["color"].lower(), params["color"])
                    ha_params["color_name"] = params["color"]
                if "speed" in params and dtype == DEVICE_FAN:
                    ha_params["speed"] = params["speed"]
                self._ha_client.turn_on(entity_id, **ha_params)
                msg = f"{device_name} in {display_room} turned on"

            elif action == "turn_off":
                self._ha_client.turn_off(entity_id)
                if dtype == DEVICE_LOCK:
                    msg = f"{device_name} in {display_room} unlocked"
                else:
                    msg = f"{device_name} in {display_room} turned off"

            elif action == "toggle":
                self._ha_client.toggle(entity_id)
                msg = f"{device_name} in {display_room} toggled"

            elif action == "lock":
                self._ha_client.lock(entity_id)
                msg = f"{device_name} in {display_room} locked"

            elif action == "unlock":
                self._ha_client.unlock(entity_id)
                msg = f"{device_name} in {display_room} unlocked"

            elif action == "open":
                if dtype == DEVICE_CURTAIN:
                    self._ha_client.open_cover(entity_id)
                    msg = f"{device_name} in {display_room} opened"
                else:
                    self._ha_client.turn_on(entity_id)
                    msg = f"{device_name} in {display_room} turned on"

            elif action == "close":
                if dtype == DEVICE_CURTAIN:
                    self._ha_client.close_cover(entity_id)
                    msg = f"{device_name} in {display_room} closed"
                else:
                    self._ha_client.turn_off(entity_id)
                    msg = f"{device_name} in {display_room} turned off"

            elif action == "set_brightness":
                if dtype != DEVICE_LIGHT:
                    return {"success": False, "message": f"{device_name} does not support brightness"}
                brightness_pct = params.get("brightness", 50)
                ha_brightness = int(brightness_pct * 255 / 100)
                self._ha_client.turn_on(entity_id, brightness=ha_brightness)
                msg = f"{device_name} brightness set to {brightness_pct}%"

            elif action == "set_color":
                if dtype != DEVICE_LIGHT:
                    return {"success": False, "message": f"{device_name} does not support color"}
                color = params.get("color", "white")
                self._ha_client.turn_on(entity_id, color_name=color)
                msg = f"{device_name} color set to {color}"

            elif action == "set_speed":
                if dtype != DEVICE_FAN:
                    return {"success": False, "message": f"{device_name} does not support speed"}
                speed = params.get("speed", "medium")
                self._ha_client.set_fan_speed(entity_id, speed)
                msg = f"{device_name} speed set to {speed}"

            elif action == "set_volume":
                if dtype != DEVICE_TV:
                    return {"success": False, "message": f"{device_name} does not support volume"}
                volume = max(0, min(100, params.get("volume", 50)))
                self._ha_client.volume_set(entity_id, volume / 100.0)
                msg = f"{device_name} volume set to {volume}%"

            else:
                return {"success": False, "message": f"Unknown action: {action}"}

            # Update local state mirror after HA call
            self._execute_sim_action(
                room_key, device_name, dev_state, dtype, action, params, display_room
            )
            return {"success": True, "message": msg}

        except HomeAssistantClientError as exc:
            msg = f"Home Assistant error for {device_name}: {exc}"
            logger.error(msg)
            return {"success": False, "message": msg}

    # ==================================================================
    # Scene execution
    # ==================================================================

    def execute_scene(self, scene_name: str) -> dict:
        """
        Execute a pre-defined scene.

        Args:
            scene_name: Scene key (e.g. ``"goodnight"``, ``"movie"``).

        Returns:
            Dict with ``"success"`` and ``"message"``.
        """
        scene_name = scene_name.lower().replace(" ", "").replace("-", "")
        scene = self._scenes.get(scene_name)
        if scene is None:
            msg = f"Unknown scene: {scene_name}"
            logger.warning(msg)
            self._speak(msg)
            return {"success": False, "message": msg}

        logger.info("Executing scene: %s", scene_name)
        results: List[dict] = []

        for room_key, actions in scene.get("actions", {}).items():
            for action_cfg in actions:
                device_name = action_cfg["device"]
                action = action_cfg["action"]
                params = action_cfg.get("params", {})
                res = self.control_device(room_key, device_name, action, params)
                results.append(res)

        successes = sum(1 for r in results if r["success"])
        total = len(results)

        if successes == total:
            msg = f"Scene '{scene_name}' activated — {total} actions executed"
            logger.info(msg)
            # Scene already speaks per-device; just give a summary
            self._speak(f"{scene_name.replace('_', ' ').title()} mode activated")
            self._publish_dashboard_update()
            return {"success": True, "message": msg}
        else:
            msg = (
                f"Scene '{scene_name}' partially executed — "
                f"{successes}/{total} actions succeeded"
            )
            logger.warning(msg)
            self._speak(f"Some devices failed in {scene_name} mode")
            return {"success": False, "message": msg}

    # ==================================================================
    # State queries
    # ==================================================================

    def get_device_states(self) -> Dict[str, Dict[str, Dict[str, Any]]]:
        """
        Return the full device-state map.

        Returns:
            ``{room_key: {device_name: {state_dict}}}``
            The internal ``_type`` and ``_entity_id`` keys are stripped
            from the returned copy.
        """
        result: Dict[str, Dict[str, Dict[str, Any]]] = {}
        for room_key, devices in self._device_states.items():
            result[room_key] = {}
            for dev_name, state in devices.items():
                result[room_key][dev_name] = {
                    k: v for k, v in state.items() if not k.startswith("_")
                }
        return result

    def get_room_states(self, room: str) -> Dict[str, Dict[str, Any]]:
        """
        Return device states for a single room.

        Args:
            room: Room key or display name.

        Returns:
            ``{device_name: {state_dict}}`` or empty dict if room not found.
        """
        room_key = self._normalise_room_key(room)
        if room_key is None:
            return {}

        devices = self._device_states.get(room_key, {})
        return {
            dev_name: {k: v for k, v in state.items() if not k.startswith("_")}
            for dev_name, state in devices.items()
        }

    # ==================================================================
    # Voice-command handling
    # ==================================================================

    def _on_voice_command(self, event: Event):
        """
        Handle VOICE_COMMAND events from the EventBus.

        We only process commands whose ``command`` field is ``"home"``
        or whose ``text`` field contains smart-home-related keywords.
        """
        data = event.data or {}
        command = data.get("command", "")
        raw_text = data.get("text", "") or data.get("params", {}).get("raw_text", "")

        # Route: command == "home" OR text contains home keywords
        if command != "home" and not self._text_is_home_command(raw_text):
            return

        logger.info("Smart-home voice command: '%s'", raw_text)
        self._process_voice_text(raw_text)

    @staticmethod
    def _text_is_home_command(text: str) -> bool:
        """Quick heuristic to decide if a voice text is a home command."""
        text_lower = text.lower()
        home_keywords = [
            "turn on", "turn off", "switch on", "switch off",
            "brightness", "dim", "brighten",
            "lock", "unlock",
            "open the", "close the",
            "set", "color", "speed",
            "goodnight", "good night", "good morning",
            "movie mode", "away mode",
            "home status", "device status",
            "curtain", "curtains", "blinds",
            "light", "lights", "fan", "ac",
            "tv", "plug",
        ]
        return any(kw in text_lower for kw in home_keywords)

    def _process_voice_text(self, text: str):
        """Parse a raw voice string and execute the appropriate action."""
        text_lower = text.lower().strip()

        # ── Scene shortcuts ────────────────────────────────────────────
        if text_lower in ("goodnight", "good night"):
            self.execute_scene("goodnight")
            return
        if text_lower in ("good morning", "goodmorning"):
            self.execute_scene("goodmorning")
            return
        if "movie" in text_lower and ("mode" in text_lower or "scene" in text_lower):
            self.execute_scene("movie")
            return
        if "away" in text_lower and ("mode" in text_lower or "scene" in text_lower):
            self.execute_scene("away")
            return

        # ── Status command ─────────────────────────────────────────────
        if "status" in text_lower or ("show" in text_lower and "home" in text_lower):
            self._report_status()
            return

        # ── "Turn off everything" ──────────────────────────────────────
        if "everything" in text_lower and ("off" in text_lower or "turn off" in text_lower):
            self._turn_off_everything()
            return

        # ── Structured parsing ─────────────────────────────────────────
        parsed = self._parse_voice_command(text_lower)
        if parsed is None:
            self._speak("I didn't understand that home command. Could you repeat?")
            return

        room, device, action, params = parsed
        self.control_device(room, device, action, params)

    def _parse_voice_command(
        self, text: str
    ) -> Optional[Tuple[str, str, str, dict]]:
        """
        Parse a voice command string into (room, device, action, params).

        Returns None if the command cannot be understood.
        """
        params: Dict[str, Any] = {}

        # ── Detect room ────────────────────────────────────────────────
        room_key: Optional[str] = None
        for alias, canonical in _ROOM_ALIASES.items():
            if alias in text:
                room_key = canonical
                break

        # ── Detect action ──────────────────────────────────────────────
        action: Optional[str] = None

        # Lock / unlock
        if re.search(r"\block\b", text) or "lock the" in text:
            action = "lock"
        elif re.search(r"\bunlock\b", text) or "unlock the" in text:
            action = "unlock"
        # Open / close (curtains, etc.)
        elif re.search(r"\bopen\b", text) or "open the" in text:
            action = "open"
        elif re.search(r"\bclose\b", text) or "close the" in text:
            action = "close"
        # Turn on / off
        elif re.search(r"\bturn\s+on\b", text) or "switch on" in text:
            action = "turn_on"
        elif re.search(r"\bturn\s+off\b", text) or "switch off" in text:
            action = "turn_off"

        # ── Brightness ─────────────────────────────────────────────────
        brightness_match = re.search(
            r"brightness\s+(?:to\s+)?(\d+)\s*%?", text
        )
        if brightness_match:
            params["brightness"] = int(brightness_match.group(1))
            if action is None:
                action = "set_brightness"

        # ── Dim / brighten ─────────────────────────────────────────────
        if "dim" in text and action is None:
            action = "set_brightness"
            params["brightness"] = 20
        if "brighten" in text and action is None:
            action = "set_brightness"
            params["brightness"] = 100

        # ── Color ──────────────────────────────────────────────────────
        for color_name in COLOR_MAP:
            if color_name in text and "color" in text:
                params["color"] = color_name
                if action is None:
                    action = "set_color"
                break
        # Also try: "set [device] to [color]" without "color" keyword
        if "color" not in params:
            color_match = re.search(r"\bto\s+(\w+)\s*$", text)
            if color_match:
                maybe_color = color_match.group(1)
                if maybe_color in COLOR_MAP:
                    params["color"] = maybe_color
                    if action is None:
                        action = "set_color"

        # ── Speed ──────────────────────────────────────────────────────
        for speed in FAN_SPEEDS:
            if speed in text and ("speed" in text or "fan" in text or "ac" in text):
                params["speed"] = speed
                if action is None:
                    action = "set_speed"
                break

        # ── Volume ─────────────────────────────────────────────────────
        volume_match = re.search(r"volume\s+(?:to\s+)?(\d+)\s*%?", text)
        if volume_match:
            params["volume"] = int(volume_match.group(1))
            if action is None:
                action = "set_volume"

        if action is None:
            return None

        # ── Detect device ──────────────────────────────────────────────
        device: Optional[str] = None

        # Try matching by device type alias first
        for alias, dtype in sorted(
            _DEVICE_TYPE_ALIASES.items(), key=lambda x: -len(x[0])
        ):
            if alias in text:
                device = dtype  # use the type as the device selector
                break

        # If we got a device type alias, use it.  Otherwise try exact
        # device names from the target room.
        if device is None and room_key is not None:
            for dev_cfg in self._rooms.get(room_key, {}).get("devices", []):
                if dev_cfg["name"].lower() in text:
                    device = dev_cfg["name"]
                    break

        if device is None:
            # Last resort: use the device type we may have matched
            device = "lights"  # generic fallback

        # If no room detected, try "all"
        if room_key is None:
            # Check if text says "all" explicitly
            if "all" in text:
                room_key = "all"
            else:
                # Try to infer from device context
                room_key = "all"

        return (room_key, device, action, params)

    # ==================================================================
    # Helper actions
    # ==================================================================

    def _turn_off_everything(self):
        """Turn off all controllable devices and lock doors."""
        for room_key, room_data in self._rooms.items():
            for dev_cfg in room_data.get("devices", []):
                dtype = dev_cfg.get("type", DEVICE_SWITCH)
                dev_name = dev_cfg["name"]
                if dtype == DEVICE_LOCK:
                    self.control_device(room_key, dev_name, "lock")
                elif dtype == DEVICE_CURTAIN:
                    self.control_device(room_key, dev_name, "close")
                else:
                    self.control_device(room_key, dev_name, "turn_off")
        self._speak("Everything has been turned off and doors are locked")
        self._publish_dashboard_update()

    def _report_status(self):
        """Speak a summary of all device states."""
        lines: List[str] = []
        for room_key, room_data in self._rooms.items():
            display_room = room_data["display_name"]
            states = self._device_states.get(room_key, {})
            room_parts: List[str] = []
            for dev_name, state in states.items():
                dtype = state.get("_type", DEVICE_SWITCH)
                if dtype == DEVICE_LIGHT:
                    status = "on" if state.get("on") else "off"
                    brightness = state.get("brightness", 0)
                    room_parts.append(f"{dev_name} {status} at {brightness}%")
                elif dtype == DEVICE_FAN:
                    status = "on" if state.get("on") else "off"
                    speed = state.get("speed", "medium")
                    room_parts.append(f"{dev_name} {status} speed {speed}")
                elif dtype == DEVICE_SWITCH:
                    status = "on" if state.get("on") else "off"
                    room_parts.append(f"{dev_name} {status}")
                elif dtype == DEVICE_LOCK:
                    status = "locked" if state.get("locked") else "unlocked"
                    room_parts.append(f"{dev_name} {status}")
                elif dtype == DEVICE_CURTAIN:
                    pos = state.get("position", 0)
                    status = "open" if pos > 0 else "closed"
                    room_parts.append(f"{dev_name} {status}")
                elif dtype == DEVICE_TV:
                    status = "on" if state.get("on") else "off"
                    room_parts.append(f"{dev_name} {status}")

            if room_parts:
                lines.append(f"{display_room}: " + ", ".join(room_parts))

        if lines:
            report = ". ".join(lines)
        else:
            report = "No devices configured"

        self._speak(report)
        self._publish_dashboard_update()

    # ==================================================================
    # EventBus helpers
    # ==================================================================

    def _speak(self, text: str):
        """Publish a SPEAK_REQUEST event."""
        self.event_bus.publish(
            Event(EventTypes.SPEAK_REQUEST, {"text": text})
        )

    def _publish_dashboard_update(self):
        """Publish a DASHBOARD_UPDATE with current device states."""
        self.event_bus.publish(
            Event(EventTypes.DASHBOARD_UPDATE, {
                "panel": "smart_home",
                "devices": self.get_device_states(),
            })
        )

    # ==================================================================
    # Internal utilities
    # ==================================================================

    def _normalise_room_key(self, room: str) -> Optional[str]:
        """
        Convert a room string (key, display name, or alias) to the
        canonical room key.

        Returns None if the room cannot be resolved.
        """
        room_lower = room.lower().strip()

        # Direct key match
        if room_lower in self._rooms:
            return room_lower

        # Alias match
        if room_lower in _ROOM_ALIASES:
            return _ROOM_ALIASES[room_lower]

        # Display-name match
        for room_key, room_data in self._rooms.items():
            if room_data["display_name"].lower() == room_lower:
                return room_key

        return None

    def _resolve_device_names(self, room_key: str, device: str) -> List[str]:
        """
        Given a device identifier (exact name, type, or alias),
        return matching device names in the specified room.
        """
        room_devices = self._device_states.get(room_key, {})
        device_lower = device.lower().strip()

        # 1. Exact name match
        for dev_name in room_devices:
            if dev_name.lower() == device_lower:
                return [dev_name]

        # 2. Partial name match
        for dev_name in room_devices:
            if device_lower in dev_name.lower():
                return [dev_name]

        # 3. Device-type alias match — return ALL devices of that type
        target_type = _DEVICE_TYPE_ALIASES.get(device_lower)
        if target_type:
            matches = [
                dev_name
                for dev_name, state in room_devices.items()
                if state.get("_type") == target_type
            ]
            return matches

        # 4. Type name direct match
        if device_lower in SUPPORTED_DEVICE_TYPES:
            matches = [
                dev_name
                for dev_name, state in room_devices.items()
                if state.get("_type") == device_lower
            ]
            return matches

        return []

    @staticmethod
    def _clamp_brightness(value: int) -> int:
        """Clamp a brightness percentage to 0–100."""
        return max(0, min(100, int(value)))
