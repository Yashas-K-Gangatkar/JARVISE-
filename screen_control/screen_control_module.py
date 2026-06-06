"""
Screen Control Module - Desktop automation and application control.

Uses pyautogui and subprocess to provide:
- Application control (open, close, switch)
- Mouse control (move, click, scroll)
- Keyboard control (type, press keys, hotkeys, screenshot)
- Window management (maximize, minimize, close)
- System commands (volume, brightness, lock, shutdown)
- Safety features (fail-safe, confirmation, speed limits)

Integrates with the JARVIS EventBus for voice command handling.
"""

import logging
import os
import platform
import subprocess
import threading
import time

logger = logging.getLogger("jarvis.screen_control")

# ---------------------------------------------------------------------------
# OS detection
# ---------------------------------------------------------------------------

CURRENT_OS = platform.system()  # "Darwin", "Windows", "Linux"

# ---------------------------------------------------------------------------
# Application name → shell command mappings (per OS)
# ---------------------------------------------------------------------------

APP_MAPPINGS = {
    "Darwin": {
        "chrome": "open -a 'Google Chrome'",
        "google chrome": "open -a 'Google Chrome'",
        "safari": "open -a 'Safari'",
        "firefox": "open -a 'Firefox'",
        "calculator": "open -a 'Calculator'",
        "notes": "open -a 'Notes'",
        "terminal": "open -a 'Terminal'",
        "finder": "open -a 'Finder'",
        "spotify": "open -a 'Spotify'",
        "vscode": "open -a 'Visual Studio Code'",
        "visual studio code": "open -a 'Visual Studio Code'",
        "code": "open -a 'Visual Studio Code'",
        "notepad": "open -a 'TextEdit'",
        "textedit": "open -a 'TextEdit'",
        "mail": "open -a 'Mail'",
        "calendar": "open -a 'Calendar'",
        "photos": "open -a 'Photos'",
        "music": "open -a 'Music'",
        "maps": "open -a 'Maps'",
        "settings": "open -a 'System Preferences'",
        "system preferences": "open -a 'System Preferences'",
        "slack": "open -a 'Slack'",
        "discord": "open -a 'Discord'",
        "zoom": "open -a 'zoom.us'",
        "word": "open -a 'Microsoft Word'",
        "excel": "open -a 'Microsoft Excel'",
        "powerpoint": "open -a 'Microsoft PowerPoint'",
        "preview": "open -a 'Preview'",
        "activity monitor": "open -a 'Activity Monitor'",
    },
    "Windows": {
        "chrome": "start chrome",
        "google chrome": "start chrome",
        "firefox": "start firefox",
        "calculator": "start calc",
        "notepad": "start notepad",
        "notepad++": "start notepad++",
        "terminal": "start cmd",
        "command prompt": "start cmd",
        "powershell": "start powershell",
        "vscode": "start code",
        "visual studio code": "start code",
        "code": "start code",
        "explorer": "start explorer",
        "file explorer": "start explorer",
        "spotify": "start spotify:",
        "slack": "start slack:",
        "discord": "start discord:",
        "zoom": "start zoom:",
        "word": "start winword",
        "excel": "start excel",
        "powerpoint": "start powerpnt",
        "outlook": "start outlook",
        "settings": "start ms-settings:",
        "task manager": "start taskmgr",
        "paint": "start mspaint",
        "snipping tool": "start snippingtool",
    },
    "Linux": {
        "chrome": "google-chrome",
        "google chrome": "google-chrome",
        "chromium": "chromium-browser",
        "firefox": "firefox",
        "calculator": "gnome-calculator",
        "notepad": "gedit",
        "gedit": "gedit",
        "terminal": "gnome-terminal",
        "files": "nautilus",
        "nautilus": "nautilus",
        "vscode": "code",
        "visual studio code": "code",
        "code": "code",
        "spotify": "spotify",
        "slack": "slack",
        "discord": "discord",
        "settings": "gnome-control-center",
        "system monitor": "gnome-system-monitor",
    },
}

# ---------------------------------------------------------------------------
# Application name → process-name mappings (for closing, per OS)
# ---------------------------------------------------------------------------

PROCESS_MAPPINGS = {
    "Darwin": {
        "chrome": "Google Chrome",
        "google chrome": "Google Chrome",
        "safari": "Safari",
        "firefox": "Firefox",
        "calculator": "Calculator",
        "notes": "Notes",
        "terminal": "Terminal",
        "finder": "Finder",
        "spotify": "Spotify",
        "vscode": "Visual Studio Code",
        "visual studio code": "Visual Studio Code",
        "code": "Visual Studio Code",
        "notepad": "TextEdit",
        "textedit": "TextEdit",
        "mail": "Mail",
        "calendar": "Calendar",
        "slack": "Slack",
        "discord": "Discord",
        "zoom": "zoom.us",
        "word": "Microsoft Word",
        "excel": "Microsoft Excel",
        "powerpoint": "Microsoft PowerPoint",
    },
    "Windows": {
        "chrome": "chrome",
        "google chrome": "chrome",
        "firefox": "firefox",
        "calculator": "Calculator",
        "notepad": "notepad",
        "terminal": "cmd",
        "vscode": "Code",
        "visual studio code": "Code",
        "code": "Code",
        "explorer": "explorer",
        "spotify": "Spotify",
        "slack": "Slack",
        "discord": "Discord",
        "zoom": "Zoom",
        "word": "WINWORD",
        "excel": "EXCEL",
        "powerpoint": "POWERPNT",
    },
    "Linux": {
        "chrome": "google-chrome",
        "google chrome": "google-chrome",
        "chromium": "chromium-browser",
        "firefox": "firefox",
        "calculator": "gnome-calculat",
        "notepad": "gedit",
        "terminal": "gnome-terminal",
        "vscode": "code",
        "visual studio code": "code",
        "code": "code",
        "spotify": "spotify",
        "slack": "slack",
        "discord": "discord",
    },
}

# ---------------------------------------------------------------------------
# Key name mappings (voice → pyautogui key names)
# ---------------------------------------------------------------------------

KEY_MAPPINGS = {
    "enter": "enter",
    "return": "enter",
    "escape": "escape",
    "esc": "escape",
    "tab": "tab",
    "space": "space",
    "backspace": "backspace",
    "delete": "delete",
    "up": "up",
    "down": "down",
    "left": "left",
    "right": "right",
    "home": "home",
    "end": "end",
    "page up": "pageup",
    "page down": "pagedown",
    "caps lock": "capslock",
    "shift": "shift",
    "control": "ctrl",
    "ctrl": "ctrl",
    "alt": "alt",
    "command": "command",
    "cmd": "command",
    "option": "alt",
    "windows": "win",
    "super": "win",
    "f1": "f1",
    "f2": "f2",
    "f3": "f3",
    "f4": "f4",
    "f5": "f5",
    "f6": "f6",
    "f7": "f7",
    "f8": "f8",
    "f9": "f9",
    "f10": "f10",
    "f11": "f11",
    "f12": "f12",
}

# ---------------------------------------------------------------------------
# Mouse position presets (fractions of screen)
# ---------------------------------------------------------------------------

MOUSE_POSITIONS = {
    "top left": (0.0, 0.0),
    "top right": (1.0, 0.0),
    "bottom left": (0.0, 1.0),
    "bottom right": (1.0, 1.0),
    "center": (0.5, 0.5),
    "middle": (0.5, 0.5),
    "top center": (0.5, 0.0),
    "bottom center": (0.5, 1.0),
    "left center": (0.0, 0.5),
    "right center": (1.0, 0.5),
}

# ---------------------------------------------------------------------------
# Destructive actions that require confirmation
# ---------------------------------------------------------------------------

DESTRUCTIVE_ACTIONS = {"shutdown", "restart", "close_all"}


class ScreenControlModule:
    """
    Desktop automation module for JARVIS AI Assistant.

    Provides application control, mouse/keyboard automation,
    window management, and system commands via pyautogui and
    platform-specific shell commands.

    Integrates with the JARVIS EventBus for voice command handling
    and publishes SPEAK_REQUEST / DASHBOARD_UPDATE events.

    Safety features:
        - pyautogui FAIL-SAFE enabled (move mouse to screen corner to abort)
        - Confirmation required for destructive actions (shutdown, restart)
        - Mouse movement speed limited by config
        - Basic password-field detection to prevent auto-typing passwords
    """

    def __init__(self, event_bus, config):
        """
        Initialise the Screen Control module.

        Args:
            event_bus: EventBus instance for inter-module communication.
            config: Full application configuration dict.  Screen-control
                    settings are read from config["screen_control"].
        """
        self.event_bus = event_bus
        self.config = config.get("screen_control", {})

        # ── Settings ────────────────────────────────────────────────
        self.enabled = self.config.get("enabled", True)
        self.safe_mode = self.config.get("safe_mode", True)
        self.mouse_speed = self.config.get("mouse_speed", 0.5)
        self.fail_safe = self.config.get("fail_safe", True)
        self.screenshot_dir = self.config.get("screenshot_dir", "screenshots")

        # ── Internal state ──────────────────────────────────────────
        self._running = False
        self._paused = False  # When paused, commands are queued
        self._command_queue = []
        self._lock = threading.Lock()
        self._pending_confirmation = None  # Holds a destructive action awaiting confirmation

        # ── OS-specific mappings ────────────────────────────────────
        self._app_mappings = APP_MAPPINGS.get(CURRENT_OS, APP_MAPPINGS["Linux"])
        self._process_mappings = PROCESS_MAPPINGS.get(CURRENT_OS, PROCESS_MAPPINGS["Linux"])

        # ── pyautogui initialisation ────────────────────────────────
        try:
            import pyautogui
            self._pyautogui = pyautogui
            pyautogui.FAILSAFE = self.fail_safe
            pyautogui.PAUSE = 0.1  # Small pause between actions for safety
            self._screen_width, self._screen_height = pyautogui.size()
            logger.info(
                "Screen Control initialised — %s %s, screen %dx%d",
                CURRENT_OS, platform.release(),
                self._screen_width, self._screen_height,
            )
        except ImportError:
            self._pyautogui = None
            logger.warning(
                "pyautogui not installed — screen control will be limited. "
                "Install with: pip install pyautogui"
            )
            self._screen_width = 1920
            self._screen_height = 1080

        # ── Ensure screenshot directory exists ──────────────────────
        os.makedirs(self.screenshot_dir, exist_ok=True)

    # ==================================================================
    # Lifecycle
    # ==================================================================

    def start(self):
        """
        Start the Screen Control module.

        Subscribes to VOICE_COMMAND events on the EventBus and
        begins processing screen-control commands.
        """
        if not self.enabled:
            logger.info("Screen Control is disabled in config")
            return

        from ai_core.event_bus import EventTypes
        self.event_bus.subscribe(EventTypes.VOICE_COMMAND, self._on_voice_command)
        self._running = True
        logger.info("Screen Control started — subscribed to VOICE_COMMAND")

    def stop(self):
        """
        Stop the Screen Control module.

        Unsubscribes from EventBus events and clears internal state.
        """
        self._running = False
        from ai_core.event_bus import EventTypes
        self.event_bus.unsubscribe(EventTypes.VOICE_COMMAND, self._on_voice_command)
        logger.info("Screen Control stopped")

    # ==================================================================
    # EventBus handlers
    # ==================================================================

    def _on_voice_command(self, event):
        """
        Handle VOICE_COMMAND events from the EventBus.

        Routes relevant commands to the appropriate handler.
        Commands with prefix "screen" or matching known screen-control
        keywords are processed; others are ignored.

        Args:
            event: Event object with data containing "text", "command", "params".
        """
        if not self._running or self._paused:
            return

        data = event.data
        text = data.get("text", "").lower().strip()
        command = data.get("command", "")

        # Check for confirmation responses first
        if self._pending_confirmation is not None:
            self._handle_confirmation(text)
            return

        # Route the command
        self._route_command(text, command)

    def _route_command(self, text, command):
        """
        Parse and dispatch a voice command to the appropriate handler.

        Args:
            text: Raw voice text (lowercase).
            command: Parsed command name from VoiceControlModule.
        """
        result = None

        # ── Open application ────────────────────────────────────────
        if text.startswith("open "):
            app_name = text[5:].strip()
            result = self.open_application(app_name)

        # ── Close application ───────────────────────────────────────
        elif text.startswith("close "):
            app_name = text[6:].strip()
            result = self.close_application(app_name)

        # ── Switch to application ───────────────────────────────────
        elif text.startswith("switch to "):
            app_name = text[10:].strip()
            result = self.switch_application(app_name)

        # ── Type text ──────────────────────────────────────────────
        elif text.startswith("type "):
            typed_text = text[5:].strip()
            result = self.type_text(typed_text)

        # ── Press key / hotkey ──────────────────────────────────────
        elif text.startswith("press "):
            key_spec = text[6:].strip()
            result = self.press_key(key_spec)

        # ── Click ───────────────────────────────────────────────────
        elif text in ("click", "left click"):
            result = self.click()

        # ── Double click ────────────────────────────────────────────
        elif text in ("double click", "doubleclick"):
            result = self.double_click()

        # ── Right click ─────────────────────────────────────────────
        elif text in ("right click", "rightclick"):
            result = self.right_click()

        # ── Scroll ──────────────────────────────────────────────────
        elif text in ("scroll up", "scroll up"):
            result = self.scroll("up")
        elif text in ("scroll down", "scrolldown"):
            result = self.scroll("down")

        # ── Move mouse ──────────────────────────────────────────────
        elif text.startswith("move mouse to "):
            position = text[14:].strip()
            result = self.move_mouse(position)

        # ── Screenshot ──────────────────────────────────────────────
        elif text in ("take a screenshot", "take screenshot", "screenshot", "screen shot"):
            result = self.take_screenshot()

        # ── Volume ──────────────────────────────────────────────────
        elif text in ("volume up", "volumeup", "turn up volume", "increase volume"):
            result = self.control_volume("up")
        elif text in ("volume down", "volumedown", "turn down volume", "decrease volume"):
            result = self.control_volume("down")
        elif text in ("mute", "unmute", "toggle mute"):
            result = self.control_volume("mute")

        # ── Brightness ──────────────────────────────────────────────
        elif text in ("brightness up", "increase brightness"):
            result = self.control_brightness("up")
        elif text in ("brightness down", "decrease brightness"):
            result = self.control_brightness("down")

        # ── Window management ───────────────────────────────────────
        elif text in ("maximize window", "maximise window", "full screen"):
            result = self.manage_window("maximize")
        elif text in ("minimize window", "minimise window"):
            result = self.manage_window("minimize")
        elif text in ("close window"):
            result = self.manage_window("close")

        # ── Lock screen ─────────────────────────────────────────────
        elif text in ("lock screen", "lock computer", "lock"):
            result = self.lock_screen()

        # ── Shutdown / restart ──────────────────────────────────────
        elif text in ("shutdown computer", "shut down computer", "shutdown", "shut down"):
            result = self._request_destructive_action("shutdown")
        elif text in ("restart computer", "restart"):
            result = self._request_destructive_action("restart")

        else:
            # Not a screen-control command — ignore silently
            return

        # Publish the result as a dashboard update and optionally speak
        if result is not None:
            self._publish_result(result)

    # ==================================================================
    # Application Control
    # ==================================================================

    def open_application(self, app_name):
        """
        Open an application by name.

        Looks up the application in the OS-specific mapping table.
        If not found, attempts to open it using the OS default mechanism.

        Args:
            app_name: Human-readable application name (e.g. "Chrome", "Calculator").

        Returns:
            dict: Result with "success" (bool), "message" (str), and optional "app" (str).
        """
        app_key = app_name.lower().strip()
        logger.info("Opening application: %s", app_name)

        # Look up in mapping table
        command = self._app_mappings.get(app_key)

        if command is None:
            # Fallback: try to open using OS default
            if CURRENT_OS == "Darwin":
                command = f"open -a '{app_name}'"
            elif CURRENT_OS == "Windows":
                command = f"start {app_name}"
            else:
                command = app_name

        try:
            if CURRENT_OS == "Windows":
                subprocess.Popen(command, shell=True)
            else:
                subprocess.Popen(command, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            message = f"Opening {app_name}"
            logger.info(message)
            return {"success": True, "message": message, "app": app_name}

        except FileNotFoundError:
            message = f"Application '{app_name}' not found"
            logger.warning(message)
            return {"success": False, "message": message, "app": app_name}
        except Exception as exc:
            message = f"Failed to open {app_name}: {exc}"
            logger.error(message)
            return {"success": False, "message": message, "app": app_name}

    def close_application(self, app_name):
        """
        Close (quit) an application by name.

        Uses OS-specific process termination commands.

        Args:
            app_name: Human-readable application name.

        Returns:
            dict: Result with "success" (bool) and "message" (str).
        """
        app_key = app_name.lower().strip()
        logger.info("Closing application: %s", app_name)

        process_name = self._process_mappings.get(app_key, app_name)

        try:
            if CURRENT_OS == "Darwin":
                subprocess.Popen(
                    ["osascript", "-e", f'tell application "{process_name}" to quit'],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
            elif CURRENT_OS == "Windows":
                subprocess.Popen(
                    ["taskkill", "/F", "/IM", f"{process_name}.exe"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
            else:  # Linux
                subprocess.Popen(
                    ["pkill", "-f", process_name],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )

            message = f"Closing {app_name}"
            logger.info(message)
            return {"success": True, "message": message, "app": app_name}

        except Exception as exc:
            message = f"Failed to close {app_name}: {exc}"
            logger.error(message)
            return {"success": False, "message": message, "app": app_name}

    def switch_application(self, app_name):
        """
        Switch to (bring to front) an application by name.

        Uses OS-specific window-focus commands.

        Args:
            app_name: Human-readable application name.

        Returns:
            dict: Result with "success" (bool) and "message" (str).
        """
        app_key = app_name.lower().strip()
        logger.info("Switching to application: %s", app_name)

        process_name = self._process_mappings.get(app_key, app_name)

        try:
            if CURRENT_OS == "Darwin":
                subprocess.Popen(
                    ["osascript", "-e", f'tell application "{process_name}" to activate'],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
            elif CURRENT_OS == "Windows":
                # Use PowerShell to bring window to front
                ps_script = (
                    f"Add-Type \"\"using System; using System.Runtime.InteropServices;"
                    f" public class Win {{ [DllImport(\\\"user32.dll\\\")] "
                    f" public static extern bool SetForegroundWindow(IntPtr hWnd); }}\"\"; "
                    f"$proc = Get-Process '{process_name}' -ErrorAction SilentlyContinue; "
                    f"if ($proc) {{ [Win]::SetForegroundWindow($proc.MainWindowHandle) }}"
                )
                subprocess.Popen(
                    ["powershell", "-Command", ps_script],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
            else:  # Linux
                subprocess.Popen(
                    ["wmctrl", "-a", process_name],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )

            message = f"Switching to {app_name}"
            logger.info(message)
            return {"success": True, "message": message, "app": app_name}

        except Exception as exc:
            message = f"Failed to switch to {app_name}: {exc}"
            logger.error(message)
            return {"success": False, "message": message, "app": app_name}

    # ==================================================================
    # Mouse Control
    # ==================================================================

    def move_mouse(self, position):
        """
        Move the mouse cursor to a named position on the screen.

        Args:
            position: Named position (e.g. "top left", "center", "bottom right")
                      or "x,y" coordinate string.

        Returns:
            dict: Result with "success" (bool) and "message" (str).
        """
        if self._pyautogui is None:
            return {"success": False, "message": "pyautogui not available"}

        logger.info("Moving mouse to: %s", position)

        try:
            # Check for named positions
            if position in MOUSE_POSITIONS:
                frac_x, frac_y = MOUSE_POSITIONS[position]
                target_x = int(self._screen_width * frac_x)
                target_y = int(self._screen_height * frac_y)
            elif "," in position:
                parts = position.split(",")
                target_x = int(parts[0].strip())
                target_y = int(parts[1].strip())
            else:
                return {"success": False, "message": f"Unknown position: {position}"}

            # Clamp to screen bounds (with a small margin to avoid triggering fail-safe)
            margin = 5
            target_x = max(margin, min(target_x, self._screen_width - margin))
            target_y = max(margin, min(target_y, self._screen_height - margin))

            duration = max(0.2, 1.0 - self.mouse_speed)  # Higher speed → shorter duration
            self._pyautogui.moveTo(target_x, target_y, duration=duration)

            message = f"Mouse moved to {position} ({target_x}, {target_y})"
            logger.info(message)
            return {"success": True, "message": message}

        except self._pyautogui.FailSafeException:
            return self._handle_failsafe()
        except Exception as exc:
            message = f"Failed to move mouse: {exc}"
            logger.error(message)
            return {"success": False, "message": message}

    def click(self):
        """
        Perform a left mouse click at the current position.

        Returns:
            dict: Result with "success" (bool) and "message" (str).
        """
        if self._pyautogui is None:
            return {"success": False, "message": "pyautogui not available"}

        try:
            self._pyautogui.click()
            logger.info("Left click performed")
            return {"success": True, "message": "Clicked"}
        except self._pyautogui.FailSafeException:
            return self._handle_failsafe()
        except Exception as exc:
            logger.error("Click failed: %s", exc)
            return {"success": False, "message": f"Click failed: {exc}"}

    def double_click(self):
        """
        Perform a double left click at the current position.

        Returns:
            dict: Result with "success" (bool) and "message" (str).
        """
        if self._pyautogui is None:
            return {"success": False, "message": "pyautogui not available"}

        try:
            self._pyautogui.doubleClick()
            logger.info("Double click performed")
            return {"success": True, "message": "Double clicked"}
        except self._pyautogui.FailSafeException:
            return self._handle_failsafe()
        except Exception as exc:
            logger.error("Double click failed: %s", exc)
            return {"success": False, "message": f"Double click failed: {exc}"}

    def right_click(self):
        """
        Perform a right mouse click at the current position.

        Returns:
            dict: Result with "success" (bool) and "message" (str).
        """
        if self._pyautogui is None:
            return {"success": False, "message": "pyautogui not available"}

        try:
            self._pyautogui.rightClick()
            logger.info("Right click performed")
            return {"success": True, "message": "Right clicked"}
        except self._pyautogui.FailSafeException:
            return self._handle_failsafe()
        except Exception as exc:
            logger.error("Right click failed: %s", exc)
            return {"success": False, "message": f"Right click failed: {exc}"}

    def scroll(self, direction, clicks=3):
        """
        Scroll the mouse wheel.

        Args:
            direction: "up" or "down".
            clicks: Number of scroll clicks (default 3).

        Returns:
            dict: Result with "success" (bool) and "message" (str).
        """
        if self._pyautogui is None:
            return {"success": False, "message": "pyautogui not available"}

        try:
            if direction == "up":
                self._pyautogui.scroll(clicks)
            else:
                self._pyautogui.scroll(-clicks)

            logger.info("Scrolled %s %d clicks", direction, clicks)
            return {"success": True, "message": f"Scrolled {direction}"}
        except self._pyautogui.FailSafeException:
            return self._handle_failsafe()
        except Exception as exc:
            logger.error("Scroll failed: %s", exc)
            return {"success": False, "message": f"Scroll failed: {exc}"}

    # ==================================================================
    # Keyboard Control
    # ==================================================================

    def type_text(self, text):
        """
        Type a string of text using the keyboard.

        Includes basic password-field detection: if the active window
        title contains "password" or "passwd", the action is blocked
        in safe_mode.

        Args:
            text: The text string to type.

        Returns:
            dict: Result with "success" (bool) and "message" (str).
        """
        if self._pyautogui is None:
            return {"success": False, "message": "pyautogui not available"}

        if self.safe_mode and self._is_password_field():
            message = "Cannot type — a password field may be active (safety restriction)"
            logger.warning(message)
            return {"success": False, "message": message}

        try:
            self._pyautogui.typewrite(text, interval=0.02)
            logger.info("Typed text: %s", text[:50] + ("..." if len(text) > 50 else ""))
            return {"success": True, "message": f"Typed: {text}"}
        except self._pyautogui.FailSafeException:
            return self._handle_failsafe()
        except Exception as exc:
            # On some systems typewrite doesn't support certain characters;
            # fall back to pyperclip + paste
            try:
                import pyperclip
                pyperclip.copy(text)
                if CURRENT_OS == "Darwin":
                    self._pyautogui.hotkey("command", "v")
                else:
                    self._pyautogui.hotkey("ctrl", "v")
                logger.info("Typed text via clipboard: %s", text[:50])
                return {"success": True, "message": f"Typed (via clipboard): {text}"}
            except Exception as fallback_exc:
                message = f"Failed to type text: {exc}; fallback also failed: {fallback_exc}"
                logger.error(message)
                return {"success": False, "message": message}

    def press_key(self, key_spec):
        """
        Press a key or key combination (hotkey).

        Supports single keys ("enter", "escape") and hotkey combos
        ("control C", "command space", "alt tab").

        Args:
            key_spec: Key name or space-separated hotkey combination.

        Returns:
            dict: Result with "success" (bool) and "message" (str).
        """
        if self._pyautogui is None:
            return {"success": False, "message": "pyautogui not available"}

        try:
            parts = key_spec.strip().split()

            if len(parts) == 1:
                # Single key
                mapped_key = KEY_MAPPINGS.get(parts[0].lower(), parts[0])
                self._pyautogui.press(mapped_key)
                logger.info("Pressed key: %s", mapped_key)
                return {"success": True, "message": f"Pressed {parts[0]}"}

            else:
                # Hotkey combination (e.g. "control C", "command space")
                mapped_keys = [KEY_MAPPINGS.get(p.lower(), p) for p in parts]
                self._pyautogui.hotkey(*mapped_keys)
                logger.info("Pressed hotkey: %s", " + ".join(mapped_keys))
                return {"success": True, "message": f"Pressed {' + '.join(parts)}"}

        except self._pyautogui.FailSafeException:
            return self._handle_failsafe()
        except Exception as exc:
            message = f"Failed to press key '{key_spec}': {exc}"
            logger.error(message)
            return {"success": False, "message": message}

    def take_screenshot(self):
        """
        Take a screenshot and save it to the configured directory.

        The filename includes a timestamp for uniqueness.

        Returns:
            dict: Result with "success" (bool), "message" (str),
                  and "path" (str) on success.
        """
        if self._pyautogui is None:
            return {"success": False, "message": "pyautogui not available"}

        try:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"screenshot_{timestamp}.png"
            filepath = os.path.join(self.screenshot_dir, filename)

            screenshot = self._pyautogui.screenshot()
            screenshot.save(filepath)

            message = f"Screenshot saved: {filepath}"
            logger.info(message)
            return {"success": True, "message": message, "path": filepath}

        except Exception as exc:
            message = f"Failed to take screenshot: {exc}"
            logger.error(message)
            return {"success": False, "message": message}

    # ==================================================================
    # Window Management
    # ==================================================================

    def manage_window(self, action):
        """
        Perform a window management action.

        Args:
            action: "maximize", "minimize", or "close".

        Returns:
            dict: Result with "success" (bool) and "message" (str).
        """
        logger.info("Window management: %s", action)

        try:
            if CURRENT_OS == "Darwin":
                if action == "maximize":
                    # macOS: Ctrl+Cmd+F to toggle fullscreen in most apps
                    self._pyautogui and self._pyautogui.hotkey("ctrl", "command", "f")
                elif action == "minimize":
                    self._pyautogui and self._pyautogui.hotkey("command", "m")
                elif action == "close":
                    self._pyautogui and self._pyautogui.hotkey("command", "w")

            elif CURRENT_OS == "Windows":
                if action == "maximize":
                    self._pyautogui and self._pyautogui.hotkey("win", "up")
                elif action == "minimize":
                    self._pyautogui and self._pyautogui.hotkey("win", "down")
                elif action == "close":
                    self._pyautogui and self._pyautogui.hotkey("alt", "f4")

            else:  # Linux
                if action == "maximize":
                    self._pyautogui and self._pyautogui.hotkey("alt", "f10")
                elif action == "minimize":
                    self._pyautogui and self._pyautogui.hotkey("alt", "f9")
                elif action == "close":
                    self._pyautogui and self._pyautogui.hotkey("alt", "f4")

            message = f"Window {action} command sent"
            logger.info(message)
            return {"success": True, "message": message}

        except Exception as exc:
            message = f"Window {action} failed: {exc}"
            logger.error(message)
            return {"success": False, "message": message}

    # ==================================================================
    # System Commands
    # ==================================================================

    def control_volume(self, direction):
        """
        Control system volume.

        Args:
            direction: "up", "down", or "mute".

        Returns:
            dict: Result with "success" (bool) and "message" (str).
        """
        logger.info("Volume control: %s", direction)

        try:
            if CURRENT_OS == "Darwin":
                if direction == "up":
                    subprocess.Popen(
                        ["osascript", "-e", "set volume output volume ((output volume of (get volume settings)) + 10)"],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    )
                elif direction == "down":
                    subprocess.Popen(
                        ["osascript", "-e", "set volume output volume ((output volume of (get volume settings)) - 10)"],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    )
                elif direction == "mute":
                    subprocess.Popen(
                        ["osascript", "-e", "set volume output muted to not (output muted of (get volume settings))"],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    )

            elif CURRENT_OS == "Windows":
                if direction == "up":
                    subprocess.Popen(
                        ["powershell", "-Command",
                         "$wshShell = New-Object -ComObject WScript.Shell; "
                         "1..3 | ForEach-Object { $wshShell.SendKeys([char]175) }"],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    )
                elif direction == "down":
                    subprocess.Popen(
                        ["powershell", "-Command",
                         "$wshShell = New-Object -ComObject WScript.Shell; "
                         "1..3 | ForEach-Object { $wshShell.SendKeys([char]174) }"],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    )
                elif direction == "mute":
                    subprocess.Popen(
                        ["powershell", "-Command",
                         "$wshShell = New-Object -ComObject WScript.Shell; "
                         "$wshShell.SendKeys([char]173)"],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    )

            else:  # Linux
                if direction == "up":
                    subprocess.Popen(
                        ["amixer", "set", "Master", "10%+"],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    )
                elif direction == "down":
                    subprocess.Popen(
                        ["amixer", "set", "Master", "10%-"],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    )
                elif direction == "mute":
                    subprocess.Popen(
                        ["amixer", "set", "Master", "toggle"],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    )

            message = f"Volume {direction}"
            logger.info(message)
            return {"success": True, "message": message}

        except FileNotFoundError:
            message = f"Volume control command not available on this system"
            logger.warning(message)
            return {"success": False, "message": message}
        except Exception as exc:
            message = f"Volume control failed: {exc}"
            logger.error(message)
            return {"success": False, "message": message}

    def control_brightness(self, direction):
        """
        Control screen brightness.

        Args:
            direction: "up" or "down".

        Returns:
            dict: Result with "success" (bool) and "message" (str).
        """
        logger.info("Brightness control: %s", direction)

        try:
            if CURRENT_OS == "Darwin":
                if direction == "up":
                    subprocess.Popen(
                        ["osascript", "-e",
                         "tell application \"System Events\" to key code 144"],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    )
                else:
                    subprocess.Popen(
                        ["osascript", "-e",
                         "tell application \"System Events\" to key code 145"],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    )

            elif CURRENT_OS == "Windows":
                if direction == "up":
                    subprocess.Popen(
                        ["powershell", "-Command",
                         "(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods).WmiSetBrightness(1, 100)"],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    )
                else:
                    subprocess.Popen(
                        ["powershell", "-Command",
                         "(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods).WmiSetBrightness(1, 30)"],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    )

            else:  # Linux
                if direction == "up":
                    subprocess.Popen(
                        ["brightnessctl", "set", "10%+"],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    )
                else:
                    subprocess.Popen(
                        ["brightnessctl", "set", "10%-"],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    )

            message = f"Brightness {direction}"
            logger.info(message)
            return {"success": True, "message": message}

        except FileNotFoundError:
            message = "Brightness control command not available on this system"
            logger.warning(message)
            return {"success": False, "message": message}
        except Exception as exc:
            message = f"Brightness control failed: {exc}"
            logger.error(message)
            return {"success": False, "message": message}

    def lock_screen(self):
        """
        Lock the screen.

        Returns:
            dict: Result with "success" (bool) and "message" (str).
        """
        logger.info("Locking screen")

        try:
            if CURRENT_OS == "Darwin":
                subprocess.Popen(
                    ["/System/Library/CoreServices/Menu Extras/User.menu/Contents/Resources/CGSession", "-suspend"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
            elif CURRENT_OS == "Windows":
                subprocess.Popen(
                    ["rundll32.exe", "user32.dll,LockWorkStation"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
            else:  # Linux
                subprocess.Popen(
                    ["loginctl", "lock-session"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )

            message = "Screen locked"
            logger.info(message)
            return {"success": True, "message": message}

        except FileNotFoundError:
            message = "Lock screen command not available on this system"
            logger.warning(message)
            return {"success": False, "message": message}
        except Exception as exc:
            message = f"Lock screen failed: {exc}"
            logger.error(message)
            return {"success": False, "message": message}

    # ==================================================================
    # Destructive Actions (with confirmation)
    # ==================================================================

    def _request_destructive_action(self, action):
        """
        Request a destructive action that requires user confirmation.

        Instead of executing immediately, publishes a SPEAK_REQUEST
        asking for confirmation and stores the pending action.

        Args:
            action: The destructive action name ("shutdown" or "restart").

        Returns:
            dict: Result indicating confirmation is pending.
        """
        if self.safe_mode:
            self._pending_confirmation = action
            confirm_message = (
                f"Are you sure you want to {action} the computer? "
                f"Please say 'yes' to confirm or 'no' to cancel."
            )
            logger.warning("Requesting confirmation for: %s", action)
            self._publish_speak(confirm_message)
            return {"success": True, "message": f"Confirmation required for {action}", "pending": action}
        else:
            # Safe mode disabled — execute directly
            return self._execute_destructive_action(action)

    def _handle_confirmation(self, text):
        """
        Handle a user's confirmation or cancellation of a pending destructive action.

        Args:
            text: The voice text response from the user.
        """
        action = self._pending_confirmation
        self._pending_confirmation = None

        if any(word in text for word in ("yes", "yeah", "yep", "confirm", "sure", "okay", "ok")):
            result = self._execute_destructive_action(action)
            self._publish_result(result)
        else:
            message = f"{action} cancelled"
            logger.info(message)
            self._publish_speak(message)
            self._publish_result({"success": False, "message": message})

    def _execute_destructive_action(self, action):
        """
        Execute a destructive system action (shutdown or restart).

        Args:
            action: "shutdown" or "restart".

        Returns:
            dict: Result with "success" (bool) and "message" (str).
        """
        logger.warning("Executing destructive action: %s", action)

        try:
            if action == "shutdown":
                if CURRENT_OS == "Darwin":
                    subprocess.Popen(
                        ["osascript", "-e", 'tell app "System Events" to shut down'],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    )
                elif CURRENT_OS == "Windows":
                    subprocess.Popen(
                        ["shutdown", "/s", "/t", "30"],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    )
                else:
                    subprocess.Popen(
                        ["shutdown", "-h", "now"],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    )

            elif action == "restart":
                if CURRENT_OS == "Darwin":
                    subprocess.Popen(
                        ["osascript", "-e", 'tell app "System Events" to restart'],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    )
                elif CURRENT_OS == "Windows":
                    subprocess.Popen(
                        ["shutdown", "/r", "/t", "30"],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    )
                else:
                    subprocess.Popen(
                        ["shutdown", "-r", "now"],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    )

            message = f"Computer {action} initiated"
            logger.warning(message)
            return {"success": True, "message": message}

        except Exception as exc:
            message = f"Failed to {action}: {exc}"
            logger.error(message)
            return {"success": False, "message": message}

    # ==================================================================
    # Safety Features
    # ==================================================================

    def _is_password_field(self):
        """
        Attempt basic detection of whether the current focus is on a
        password input field.

        Uses heuristics:
        - On macOS: AppleScript to check the focused UI element's description.
        - On other platforms: always returns False (no reliable method).

        Returns:
            bool: True if a password field is likely focused, False otherwise.
        """
        if CURRENT_OS != "Darwin":
            # No reliable cross-platform method — only block on macOS
            return False

        try:
            result = subprocess.run(
                ["osascript", "-e",
                 'tell application "System Events" to get description of '
                 '(every UI element of every window of every process whose focused is true)'],
                capture_output=True, text=True, timeout=3,
            )
            output = result.stdout.lower()
            if "password" in output or "passwd" in output:
                return True
        except Exception:
            pass

        return False

    def _handle_failsafe(self):
        """
        Handle a pyautogui FailSafeException.

        Called when the mouse is moved to a screen corner (emergency stop).

        Returns:
            dict: Result indicating the fail-safe was triggered.
        """
        message = (
            "Fail-safe triggered! Mouse moved to screen corner. "
            "Screen control paused. Move mouse away and try again."
        )
        logger.warning(message)
        self._publish_speak("Fail safe triggered. Screen control paused.")
        return {"success": False, "message": message, "failsafe": True}

    # ==================================================================
    # EventBus helpers
    # ==================================================================

    def _publish_result(self, result):
        """
        Publish the result of a screen-control action.

        Sends a DASHBOARD_UPDATE with the result data, and a
        SPEAK_REQUEST with a human-readable message if the action
        was significant.

        Args:
            result: dict with "success" (bool) and "message" (str).
        """
        from ai_core.event_bus import Event, EventTypes

        # Dashboard update
        self.event_bus.publish(
            Event(EventTypes.DASHBOARD_UPDATE, {
                "source": "screen_control",
                "result": result,
            })
        )

        # Speak confirmation for important actions
        if result.get("success") and result.get("message"):
            # Don't speak for routine mouse/keyboard actions
            message = result["message"]
            significant = any(
                keyword in message.lower()
                for keyword in ("opening", "closing", "switching", "screenshot", "locked", "shutdown", "restart", "typed", "volume", "brightness", "window")
            )
            if significant:
                self._publish_speak(message)

        # Speak failures
        elif not result.get("success") and result.get("message"):
            self._publish_speak(result["message"])

    def _publish_speak(self, text):
        """
        Publish a SPEAK_REQUEST event to have JARVIS speak a message.

        Args:
            text: The text to speak.
        """
        from ai_core.event_bus import Event, EventTypes

        self.event_bus.publish(
            Event(EventTypes.SPEAK_REQUEST, {"text": text})
        )

    # ==================================================================
    # Utility / Status
    # ==================================================================

    def get_status(self):
        """
        Return the current status of the Screen Control module.

        Returns:
            dict: Status information.
        """
        return {
            "enabled": self.enabled,
            "running": self._running,
            "os": CURRENT_OS,
            "safe_mode": self.safe_mode,
            "fail_safe": self.fail_safe,
            "mouse_speed": self.mouse_speed,
            "screen_resolution": f"{self._screen_width}x{self._screen_height}",
            "screenshot_dir": self.screenshot_dir,
            "pyautogui_available": self._pyautogui is not None,
            "pending_confirmation": self._pending_confirmation,
            "supported_apps": list(self._app_mappings.keys()),
        }

    def get_supported_commands(self):
        """
        Return a list of supported voice commands.

        Returns:
            list: Human-readable command descriptions.
        """
        return [
            "open [application] — Open an application by name",
            "close [application] — Close an application by name",
            "switch to [application] — Switch to an application window",
            "type [text] — Type text using the keyboard",
            "press [key] — Press a key (e.g. 'enter', 'escape')",
            "press [modifier] [key] — Press a hotkey (e.g. 'control C')",
            "click — Left click the mouse",
            "double click — Double click the mouse",
            "right click — Right click the mouse",
            "scroll up / scroll down — Scroll the mouse wheel",
            "move mouse to [position] — Move mouse to named position",
            "take a screenshot — Capture the screen",
            "volume up / volume down / mute — Control system volume",
            "brightness up / brightness down — Control screen brightness",
            "maximize window / minimise window / close window — Window management",
            "lock screen — Lock the computer screen",
            "shutdown computer / restart computer — System power (requires confirmation)",
        ]
