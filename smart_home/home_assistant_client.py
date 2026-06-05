"""
Home Assistant REST API Client

Provides a thin wrapper around the Home Assistant REST API
for state queries and service calls.

Usage:
    client = HomeAssistantClient(
        url="http://localhost:8123",
        token="eyJ0eXAiOiJKV1Qi..."
    )
    states = client.get_states()
    client.call_service("light", "turn_on", "light.living_room",
                        {"brightness": 128})
"""

import json
import logging
from typing import Any, Dict, List, Optional

try:
    import requests
    _HAS_REQUESTS = True
except ImportError:
    _HAS_REQUESTS = False


logger = logging.getLogger("jarvis.smart_home.ha_client")


class HomeAssistantClientError(Exception):
    """Base exception for Home Assistant client errors."""
    pass


class HomeAssistantConnectionError(HomeAssistantClientError):
    """Raised when the client cannot connect to Home Assistant."""
    pass


class HomeAssistantAuthError(HomeAssistantClientError):
    """Raised when authentication fails."""
    pass


class HomeAssistantClient:
    """
    REST API client for Home Assistant.

    Supports:
        - Fetching all entity states
        - Fetching a single entity state
        - Calling any HA service (light.turn_on, switch.toggle, etc.)
        - Connection health check

    Args:
        url: Base URL of the Home Assistant instance
             (e.g. "http://192.168.1.50:8123").
        token: Long-lived access token generated from the HA
               user profile page.
        timeout: HTTP request timeout in seconds.
    """

    def __init__(
        self,
        url: str,
        token: str,
        timeout: int = 10,
    ):
        self.url = url.rstrip("/")
        self.token = token
        self.timeout = timeout
        self._session: Optional[requests.Session] = None

        if not _HAS_REQUESTS:
            logger.warning(
                "The 'requests' library is not installed. "
                "Home Assistant integration will not work. "
                "Install it with: pip install requests"
            )

    # ------------------------------------------------------------------
    # Session management
    # ------------------------------------------------------------------

    def _get_session(self) -> requests.Session:
        """Create or return the persistent HTTP session."""
        if self._session is None:
            if not _HAS_REQUESTS:
                raise HomeAssistantConnectionError(
                    "'requests' library is required but not installed"
                )
            self._session = requests.Session()
            self._session.headers.update(
                {
                    "Authorization": f"Bearer {self.token}",
                    "Content-Type": "application/json",
                }
            )
        return self._session

    def close(self):
        """Close the underlying HTTP session."""
        if self._session is not None:
            self._session.close()
            self._session = None

    # ------------------------------------------------------------------
    # Health check
    # ------------------------------------------------------------------

    def is_connected(self) -> bool:
        """
        Check whether Home Assistant is reachable and the token is valid.

        Returns:
            True if the /api/ endpoint responds with HTTP 200.
        """
        try:
            session = self._get_session()
            resp = session.get(
                f"{self.url}/api/",
                timeout=self.timeout,
            )
            return resp.status_code == 200
        except Exception as exc:
            logger.debug("HA connectivity check failed: %s", exc)
            return False

    # ------------------------------------------------------------------
    # State queries
    # ------------------------------------------------------------------

    def get_states(self) -> List[Dict[str, Any]]:
        """
        Fetch the current state of **all** entities.

        Returns:
            List of entity state dictionaries.  Each dict contains at
            least ``entity_id``, ``state``, and ``attributes``.

        Raises:
            HomeAssistantConnectionError: Network failure.
            HomeAssistantAuthError: Invalid or expired token.
        """
        try:
            session = self._get_session()
            resp = session.get(
                f"{self.url}/api/states",
                timeout=self.timeout,
            )
            resp.raise_for_status()
            return resp.json()
        except requests.ConnectionError as exc:
            raise HomeAssistantConnectionError(
                f"Cannot connect to Home Assistant at {self.url}: {exc}"
            ) from exc
        except requests.Timeout as exc:
            raise HomeAssistantConnectionError(
                f"Home Assistant request timed out: {exc}"
            ) from exc
        except requests.HTTPError as exc:
            if resp.status_code == 401:
                raise HomeAssistantAuthError(
                    "Authentication failed — check your long-lived access token"
                ) from exc
            raise HomeAssistantClientError(
                f"Home Assistant returned HTTP {resp.status_code}: {resp.text}"
            ) from exc

    def get_entity_state(self, entity_id: str) -> Dict[str, Any]:
        """
        Fetch the state of a single entity.

        Args:
            entity_id: Entity ID (e.g. ``"light.living_room"``).

        Returns:
            State dictionary with ``entity_id``, ``state``,
            ``attributes``, etc.

        Raises:
            HomeAssistantClientError: Entity not found or request failed.
        """
        try:
            session = self._get_session()
            resp = session.get(
                f"{self.url}/api/states/{entity_id}",
                timeout=self.timeout,
            )
            resp.raise_for_status()
            return resp.json()
        except requests.ConnectionError as exc:
            raise HomeAssistantConnectionError(
                f"Cannot connect to Home Assistant at {self.url}: {exc}"
            ) from exc
        except requests.Timeout as exc:
            raise HomeAssistantConnectionError(
                f"Home Assistant request timed out: {exc}"
            ) from exc
        except requests.HTTPError as exc:
            if resp.status_code == 401:
                raise HomeAssistantAuthError(
                    "Authentication failed — check your long-lived access token"
                ) from exc
            if resp.status_code == 404:
                raise HomeAssistantClientError(
                    f"Entity '{entity_id}' not found in Home Assistant"
                )
            raise HomeAssistantClientError(
                f"Home Assistant returned HTTP {resp.status_code}: {resp.text}"
            ) from exc

    # ------------------------------------------------------------------
    # Service calls
    # ------------------------------------------------------------------

    def call_service(
        self,
        domain: str,
        service: str,
        entity_id: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Call a Home Assistant service.

        Args:
            domain: Service domain (e.g. ``"light"``, ``"switch"``,
                    ``"lock"``, ``"fan"``).
            service: Service name (e.g. ``"turn_on"``, ``"turn_off"``,
                     ``"toggle"``, ``"lock"``, ``"unlock"``).
            entity_id: Optional entity ID to target.  If provided it
                       will be merged into the ``data`` dict.
            data: Optional dict of service data (brightness, color,
                  speed, etc.).

        Returns:
            Response body as a dictionary (may be empty for some
            services).

        Raises:
            HomeAssistantClientError: Service call failed.
        """
        payload: Dict[str, Any] = dict(data or {})

        if entity_id:
            payload["entity_id"] = entity_id

        try:
            session = self._get_session()
            resp = session.post(
                f"{self.url}/api/services/{domain}/{service}",
                json=payload,
                timeout=self.timeout,
            )
            resp.raise_for_status()

            # Some service calls return a list of changed states;
            # others return an empty body.
            try:
                return resp.json()
            except (json.JSONDecodeError, ValueError):
                return {}

        except requests.ConnectionError as exc:
            raise HomeAssistantConnectionError(
                f"Cannot connect to Home Assistant at {self.url}: {exc}"
            ) from exc
        except requests.Timeout as exc:
            raise HomeAssistantConnectionError(
                f"Home Assistant request timed out: {exc}"
            ) from exc
        except requests.HTTPError as exc:
            if resp.status_code == 401:
                raise HomeAssistantAuthError(
                    "Authentication failed — check your long-lived access token"
                ) from exc
            raise HomeAssistantClientError(
                f"Service call {domain}.{service} failed — "
                f"HTTP {resp.status_code}: {resp.text}"
            ) from exc

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------

    def turn_on(
        self,
        entity_id: str,
        brightness: Optional[int] = None,
        color_name: Optional[str] = None,
        color_temp: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Turn on a device, optionally setting brightness / color.

        Args:
            entity_id: Entity to turn on.
            brightness: Brightness 0–255 (only for lights).
            color_name: Colour name (e.g. ``"red"``, ``"blue"``).
            color_temp: Colour temperature in mireds.

        Returns:
            Service-call response.
        """
        # Determine domain from entity_id prefix
        domain = entity_id.split(".")[0]
        data: Dict[str, Any] = {}

        if brightness is not None:
            data["brightness"] = max(0, min(255, brightness))
        if color_name is not None:
            data["color_name"] = color_name
        if color_temp is not None:
            data["color_temp"] = color_temp

        return self.call_service(domain, "turn_on", entity_id, data or None)

    def turn_off(self, entity_id: str) -> Dict[str, Any]:
        """Turn off a device."""
        domain = entity_id.split(".")[0]
        return self.call_service(domain, "turn_off", entity_id)

    def toggle(self, entity_id: str) -> Dict[str, Any]:
        """Toggle a device on/off."""
        domain = entity_id.split(".")[0]
        return self.call_service(domain, "toggle", entity_id)

    def lock(self, entity_id: str) -> Dict[str, Any]:
        """Lock a lock entity."""
        return self.call_service("lock", "lock", entity_id)

    def unlock(self, entity_id: str) -> Dict[str, Any]:
        """Unlock a lock entity."""
        return self.call_service("lock", "unlock", entity_id)

    def set_fan_speed(self, entity_id: str, speed: str) -> Dict[str, Any]:
        """
        Set fan speed.

        Args:
            entity_id: Fan entity ID.
            speed: Speed preset name (e.g. ``"low"``, ``"medium"``,
                   ``"high"``).
        """
        return self.call_service(
            "fan", "set_speed", entity_id, {"speed": speed}
        )

    def open_cover(self, entity_id: str) -> Dict[str, Any]:
        """Open a cover / curtain."""
        return self.call_service("cover", "open_cover", entity_id)

    def close_cover(self, entity_id: str) -> Dict[str, Any]:
        """Close a cover / curtain."""
        return self.call_service("cover", "close_cover", entity_id)

    def set_cover_position(self, entity_id: str, position: int) -> Dict[str, Any]:
        """
        Set cover / curtain position.

        Args:
            entity_id: Cover entity ID.
            position: Position 0 (closed) to 100 (open).
        """
        return self.call_service(
            "cover", "set_cover_position", entity_id,
            {"position": max(0, min(100, position))},
        )

    def media_play_pause(self, entity_id: str) -> Dict[str, Any]:
        """Toggle play/pause on a media player."""
        return self.call_service("media_player", "media_play_pause", entity_id)

    def volume_set(self, entity_id: str, volume_level: float) -> Dict[str, Any]:
        """
        Set media-player volume.

        Args:
            entity_id: Media-player entity ID.
            volume_level: Volume 0.0 – 1.0.
        """
        return self.call_service(
            "media_player", "volume_set", entity_id,
            {"volume_level": max(0.0, min(1.0, volume_level))},
        )
