"""
AI Chat Module - ChatGPT-like brain for the JARVIS AI Assistant.

Supports multiple AI backends (OpenAI, Groq) with a local rule-based
fallback when no API key is configured. Integrates with the EventBus
for seamless voice-command-driven conversations.

Features:
    - OpenAI API (GPT-3.5 / GPT-4) — primary backend
    - Groq API — free, fast alternative
    - Local fallback — rule-based responses (no API key needed)
    - Conversation memory (configurable history length)
    - Dynamic system prompt with time, date, user name, weather context
    - Rate limiting (requests per minute)
    - Non-blocking API calls via threading
    - EventBus integration (VOICE_COMMAND → chat → SPEAK_REQUEST)
"""

import logging
import re
import threading
import time
from collections import deque
from datetime import datetime

from ai_core.event_bus import Event, EventTypes

from .prompts import (
    JOKES,
    QUICK_PROMPTS,
    build_system_message,
)

logger = logging.getLogger(__name__)


class RateLimiter:
    """Simple sliding-window rate limiter."""

    def __init__(self, max_requests: int, window_seconds: int = 60):
        self._max = max_requests
        self._window = window_seconds
        self._timestamps: deque = deque()
        self._lock = threading.Lock()

    def allow(self) -> bool:
        """Return True if the request is within rate limits."""
        now = time.time()
        with self._lock:
            # Evict timestamps outside the window
            while self._timestamps and self._timestamps[0] <= now - self._window:
                self._timestamps.popleft()
            if len(self._timestamps) >= self._max:
                return False
            self._timestamps.append(now)
            return True


class AIChatModule:
    """
    AI chat module that provides conversational intelligence to JARVIS.

    Subscribes to VOICE_COMMAND events (command == "chat" or "unknown") and
    responds by sending the user's text to the configured AI backend, then
    publishing the response via SPEAK_REQUEST and DASHBOARD_UPDATE events.

    Supported providers:
        - "gemini":  Google Gemini API (free tier: 15 RPM, generous quota)
        - "openai": OpenAI ChatGPT (gpt-3.5-turbo, gpt-4, etc.)
        - "groq":   Groq API (llama3-8b-8192, etc.)
        - "local":  Built-in rule-based fallback (no API key required)
    """

    # Default configuration values
    _DEFAULTS = {
        "provider": "gemini",
        "gemini_api_key": "",
        "gemini_model": "gemini-2.0-flash",
        "openai_api_key": "",
        "openai_model": "gpt-3.5-turbo",
        "groq_api_key": "",
        "groq_model": "llama3-8b-8192",
        "max_history": 20,
        "max_tokens": 1000,
        "temperature": 0.7,
        "rate_limit_per_minute": 30,
    }

    # API call timeout in seconds
    API_TIMEOUT = 15

    def __init__(self, event_bus, config):
        """
        Initialize AI chat module with config.

        Args:
            event_bus: The shared EventBus instance.
            config:    Full application config dict; the 'ai_chat' key is used.
        """
        self.event_bus = event_bus
        self._raw_config = config
        self._config = {**self._DEFAULTS, **config.get("ai_chat", {})}

        # Active provider — may be downgraded to "local" at init
        self._provider = self._config["provider"]

        # Conversation history: list of {"role": ..., "content": ...}
        self._history: list = []
        self._history_lock = threading.Lock()

        # Rate limiter
        self._rate_limiter = RateLimiter(
            max_requests=self._config["rate_limit_per_minute"],
            window_seconds=60,
        )

        # Context extras (set by the application at runtime)
        self._user_name: str = "User"
        self._last_command: str = ""
        self._weather_info: str = ""

        # Running flag
        self._running = False

        # Client instances (lazy-initialised)
        self._openai_client = None
        self._groq_client = None

        # Validate provider availability on init
        self._validate_provider()

    # ── Public Interface ───────────────────────────────────────────────

    def start(self):
        """Start the module — subscribe to EventBus events."""
        if self._running:
            return

        self._running = True
        self.event_bus.subscribe(EventTypes.VOICE_COMMAND, self._on_voice_command)
        self.event_bus.subscribe(EventTypes.SYSTEM_START, self._on_system_start)
        logger.info(
            "AIChatModule started (provider=%s, model=%s)",
            self._provider,
            self._get_active_model(),
        )
        print(f"[AIChat] Started — provider: {self._provider}, model: {self._get_active_model()}")

    def stop(self):
        """Stop the module."""
        self._running = False
        logger.info("AIChatModule stopped")
        print("[AIChat] Stopped")

    def chat(self, message: str) -> None:
        """
        Send a message to the AI and get a response. Non-blocking.

        The response is published as SPEAK_REQUEST and DASHBOARD_UPDATE
        events on the EventBus.

        Args:
            message: The user's message text.
        """
        if not message or not message.strip():
            return

        message = message.strip()

        # Check for clear-history meta-command
        if message.lower().strip() in ("clear history", "clear chat", "reset chat", "reset history"):
            self.clear_history()
            self._publish_response(
                "Conversation history cleared. Starting fresh.",
                user_message=message,
            )
            return

        # Rate-limit check
        if not self._rate_limiter.allow():
            self._publish_response(
                "I'm receiving too many requests at the moment. "
                "Please give me a moment and try again.",
                user_message=message,
            )
            logger.warning("Rate limit hit for chat request")
            return

        # Dispatch to the correct backend in a background thread
        thread = threading.Thread(
            target=self._process_chat,
            args=(message,),
            daemon=True,
            name="AIChat-Request",
        )
        thread.start()

    def clear_history(self):
        """Clear conversation history."""
        with self._history_lock:
            self._history.clear()
        logger.info("Chat history cleared")
        print("[AIChat] History cleared")

    def get_history(self) -> list:
        """
        Get conversation history.

        Returns:
            A list of message dicts ({"role": ..., "content": ...}).
        """
        with self._history_lock:
            return list(self._history)

    # ── Configuration Helpers ──────────────────────────────────────────

    def set_context(self, user_name: str = None, last_command: str = None,
                    weather_info: str = None):
        """
        Update dynamic context used in the system prompt.

        Args:
            user_name:     The user's display name.
            last_command:  The last voice command string.
            weather_info:  Current weather summary string.
        """
        if user_name is not None:
            self._user_name = user_name
        if last_command is not None:
            self._last_command = last_command
        if weather_info is not None:
            self._weather_info = weather_info

    # ── Private: Provider Validation ───────────────────────────────────

    def _validate_provider(self):
        """Validate that the chosen provider has the required API key."""
        if self._provider == "gemini":
            if not self._config.get("gemini_api_key"):
                logger.warning(
                    "No Gemini API key configured — falling back to local mode"
                )
                print("[AIChat] No Gemini API key — falling back to local mode")
                self._provider = "local"
        elif self._provider == "openai":
            if not self._config.get("openai_api_key"):
                logger.warning(
                    "No OpenAI API key configured — falling back to local mode"
                )
                print("[AIChat] No OpenAI API key — falling back to local mode")
                self._provider = "local"
        elif self._provider == "groq":
            if not self._config.get("groq_api_key"):
                logger.warning(
                    "No Groq API key configured — falling back to local mode"
                )
                print("[AIChat] No Groq API key — falling back to local mode")
                self._provider = "local"

    def _get_active_model(self) -> str:
        """Return the model name for the active provider."""
        if self._provider == "gemini":
            return self._config["gemini_model"]
        elif self._provider == "openai":
            return self._config["openai_model"]
        elif self._provider == "groq":
            return self._config["groq_model"]
        return "local"

    # ── Private: Client Initialization ─────────────────────────────────

    def _init_gemini_client(self):
        """Lazily initialise the Google Gemini client."""
        if hasattr(self, '_gemini_configured') and self._gemini_configured:
            return True
        try:
            import google.generativeai as genai
            genai.configure(api_key=self._config["gemini_api_key"])
            self._gemini_configured = True
            self._gemini_model = genai.GenerativeModel(
                model_name=self._config["gemini_model"],
                system_instruction=build_system_message(
                    user_name=self._user_name,
                    last_command=self._last_command or None,
                    weather_info=self._weather_info or None,
                ),
            )
            logger.info("Gemini client initialised (model=%s)", self._config["gemini_model"])
            return True
        except ImportError:
            logger.error("google-generativeai package not installed — run: pip install google-generativeai")
            print("[AIChat] ERROR: google-generativeai package not installed. Run: pip install google-generativeai")
            return False
        except Exception as exc:
            logger.error("Failed to init Gemini client: %s", exc)
            print(f"[AIChat] ERROR: Gemini client init failed — {exc}")
            return False

    def _init_openai_client(self):
        """Lazily initialise the OpenAI client."""
        if self._openai_client is not None:
            return True
        try:
            import openai
            self._openai_client = openai.OpenAI(
                api_key=self._config["openai_api_key"],
                timeout=self.API_TIMEOUT,
            )
            logger.info("OpenAI client initialised (model=%s)", self._config["openai_model"])
            return True
        except ImportError:
            logger.error("openai package not installed — run: pip install openai")
            print("[AIChat] ERROR: openai package not installed. Run: pip install openai")
            return False
        except Exception as exc:
            logger.error("Failed to init OpenAI client: %s", exc)
            print(f"[AIChat] ERROR: OpenAI client init failed — {exc}")
            return False

    def _init_groq_client(self):
        """Lazily initialise the Groq client."""
        if self._groq_client is not None:
            return True
        try:
            import groq
            self._groq_client = groq.Groq(
                api_key=self._config["groq_api_key"],
                timeout=self.API_TIMEOUT,
            )
            logger.info("Groq client initialised (model=%s)", self._config["groq_model"])
            return True
        except ImportError:
            logger.error("groq package not installed — run: pip install groq")
            print("[AIChat] ERROR: groq package not installed. Run: pip install groq")
            return False
        except Exception as exc:
            logger.error("Failed to init Groq client: %s", exc)
            print(f"[AIChat] ERROR: Groq client init failed — {exc}")
            return False

    # ── Private: Core Chat Processing ──────────────────────────────────

    def _process_chat(self, message: str):
        """
        Process a chat message through the active backend (blocking).

        This runs in a background thread. On success or failure it
        publishes a response via the EventBus.
        """
        try:
            # Add user message to history
            self._append_to_history("user", message)

            if self._provider == "gemini":
                response = self._call_gemini()
            elif self._provider == "openai":
                response = self._call_openai()
            elif self._provider == "groq":
                response = self._call_groq()
            else:
                response = self._call_local(message)

            # Add assistant response to history
            self._append_to_history("assistant", response)

            # Publish the response
            self._publish_response(response, user_message=message)

        except Exception as exc:
            logger.exception("Chat processing error")
            error_msg = (
                "I encountered an issue processing your request. "
                "Let me try that again."
            )
            self._publish_response(error_msg, user_message=message)

    # ── Private: Gemini Backend ───────────────────────────────────────

    def _call_gemini(self) -> str:
        """Call the Google Gemini API."""
        if not self._init_gemini_client():
            return self._call_local("(Gemini unavailable — local fallback)")

        try:
            import google.generativeai as genai

            # Build conversation history for Gemini
            gemini_history = []
            with self._history_lock:
                for msg in self._history[:-1]:  # all except the last (which is the current user msg)
                    role = "user" if msg["role"] == "user" else "model"
                    gemini_history.append({"role": role, "parts": [msg["content"]]})

            # Start a chat with history
            chat = self._gemini_model.start_chat(history=gemini_history)

            # Send the latest user message
            user_msg = self._history[-1]["content"] if self._history else "Hello"
            response = chat.send_message(
                user_msg,
                generation_config=genai.types.GenerationConfig(
                    max_output_tokens=self._config["max_tokens"],
                    temperature=self._config["temperature"],
                ),
            )
            content = response.text.strip()
            logger.debug("Gemini response: %s", content[:100])
            return content
        except Exception as exc:
            logger.error("Gemini API error: %s", exc)
            print(f"[AIChat] Gemini API error: {exc}")
            return self._call_local("(Gemini error — local fallback)")

    # ── Private: OpenAI Backend ────────────────────────────────────────

    def _call_openai(self) -> str:
        """Call the OpenAI Chat Completions API."""
        if not self._init_openai_client():
            return self._call_local("(OpenAI unavailable — local fallback)")

        try:
            messages = self._build_messages()
            response = self._openai_client.chat.completions.create(
                model=self._config["openai_model"],
                messages=messages,
                max_tokens=self._config["max_tokens"],
                temperature=self._config["temperature"],
            )
            content = response.choices[0].message.content.strip()
            logger.debug("OpenAI response: %s", content[:100])
            return content
        except Exception as exc:
            logger.error("OpenAI API error: %s", exc)
            print(f"[AIChat] OpenAI API error: {exc}")
            return self._call_local("(OpenAI error — local fallback)")

    # ── Private: Groq Backend ──────────────────────────────────────────

    def _call_groq(self) -> str:
        """Call the Groq Chat Completions API."""
        if not self._init_groq_client():
            return self._call_local("(Groq unavailable — local fallback)")

        try:
            messages = self._build_messages()
            response = self._groq_client.chat.completions.create(
                model=self._config["groq_model"],
                messages=messages,
                max_tokens=self._config["max_tokens"],
                temperature=self._config["temperature"],
            )
            content = response.choices[0].message.content.strip()
            logger.debug("Groq response: %s", content[:100])
            return content
        except Exception as exc:
            logger.error("Groq API error: %s", exc)
            print(f"[AIChat] Groq API error: {exc}")
            return self._call_local("(Groq error — local fallback)")

    # ── Private: Local Fallback Backend ────────────────────────────────

    def _call_local(self, message: str) -> str:
        """
        Rule-based local fallback when no API key is available.

        Handles greetings, time, date, math, jokes, identity, and more.
        """
        msg_lower = message.lower().strip()

        # Try each quick-prompt pattern
        for pattern, template in QUICK_PROMPTS.items():
            if re.search(pattern, msg_lower):
                # Handle special placeholder tokens
                if template == "__TIME__":
                    now = datetime.now()
                    time_str = now.strftime("%I:%M %p").lstrip("0")
                    return f"The current time is {time_str}."

                if template == "__DATE__":
                    now = datetime.now()
                    date_str = now.strftime("%A, %B %d, %Y")
                    return f"Today is {date_str}."

                if template == "__JOKE__":
                    import random
                    return random.choice(JOKES)

                return template

        # Try to evaluate simple math expressions
        math_result = self._try_math(msg_lower)
        if math_result is not None:
            return f"The answer is {math_result}."

        # Default fallback
        return (
            "I'm currently in offline mode. For full AI conversation, "
            "please add an OpenAI or Groq API key to your config."
        )

    @staticmethod
    def _try_math(text: str):
        """
        Attempt to evaluate a simple math expression from natural text.

        Returns the result as a number, or None if not parseable.
        Only allows digits, basic operators, parentheses, and spaces
        for safety.
        """
        # Strip common natural-language prefixes
        prefixes = [
            "what is ", "what's ", "calculate ", "compute ",
            "how much is ", "solve ", "evaluate ",
        ]
        expr = text
        for prefix in prefixes:
            if expr.startswith(prefix):
                expr = expr[len(prefix):]
                break

        # Remove trailing punctuation
        expr = expr.rstrip("?.!")

        # Safety: only allow safe characters
        if not re.match(r'^[\d\s\+\-\*/\(\)\.\,]+$', expr):
            return None

        # Replace comma separators (e.g. "1,000" → "1000")
        expr = expr.replace(",", "")

        if not expr.strip():
            return None

        try:
            result = eval(expr)  # noqa: S307 — input is sanitised above
            # Return int or float, keeping it clean
            if isinstance(result, float) and result.is_integer():
                return int(result)
            return result
        except Exception:
            return None

    # ── Private: History Management ────────────────────────────────────

    def _append_to_history(self, role: str, content: str):
        """Append a message to conversation history, enforcing max length."""
        with self._history_lock:
            self._history.append({"role": role, "content": content})
            max_hist = self._config["max_history"]
            # Keep only the last max_hist messages
            if len(self._history) > max_hist:
                self._history = self._history[-max_hist:]

    def _build_messages(self) -> list:
        """
        Build the full messages list for an API call.

        Includes the dynamic system prompt and conversation history.
        """
        system_content = build_system_message(
            user_name=self._user_name,
            last_command=self._last_command or None,
            weather_info=self._weather_info or None,
        )
        messages = [{"role": "system", "content": system_content}]

        with self._history_lock:
            messages.extend(list(self._history))

        return messages

    # ── Private: EventBus Publishing ───────────────────────────────────

    def _publish_response(self, response_text: str, user_message: str = ""):
        """
        Publish an AI response through the EventBus.

        Sends a SPEAK_REQUEST event (for TTS) and a DASHBOARD_UPDATE
        event (for visual display in the dashboard).
        """
        # Speak the response
        self.event_bus.publish(
            Event(EventTypes.SPEAK_REQUEST, {"text": response_text})
        )

        # Update dashboard with the conversation
        self.event_bus.publish(
            Event(EventTypes.DASHBOARD_UPDATE, {
                "panel": "chat",
                "type": "chat_message",
                "user_message": user_message,
                "assistant_response": response_text,
                "provider": self._provider,
                "timestamp": datetime.now().isoformat(),
            })
        )

        logger.info(
            "Chat response published (provider=%s, len=%d)",
            self._provider,
            len(response_text),
        )

    # ── Private: Event Handlers ────────────────────────────────────────

    def _on_voice_command(self, event):
        """
        Handle VOICE_COMMAND events.

        Processes commands with type "chat" or "unknown". This ensures
        that ANY question the user asks gets routed to the AI, not just
        those starting with the "chat" keyword.  The user's text is
        taken from event.data["text"] (the raw recognised speech).
        """
        if not self._running:
            return

        command = event.data.get("command", "")

        # Route both "chat" and "unknown" commands to the AI.
        # "unknown" means the voice parser didn't match any keyword,
        # which is exactly the case when the user asks a free-form
        # question like "What is the capital of France?"
        if command in ("chat", "unknown"):
            text = event.data.get("text", "")
            if not text:
                # Try params as a fallback source
                params = event.data.get("params", {})
                text = params.get("raw_text", "")

            if text:
                # Strip leading command keywords if present
                cleaned = re.sub(r'^\s*(chat|ask|talk|question)\s+', '', text, flags=re.IGNORECASE)
                self.chat(cleaned)
            else:
                self.event_bus.publish(
                    Event(EventTypes.SPEAK_REQUEST, {
                        "text": "What would you like to talk about?"
                    })
                )

    def _on_system_start(self, event):
        """Handle SYSTEM_START — enrich context from preferences."""
        # Try to read user name from config preferences
        prefs = self._raw_config.get("preferences", {})
        if prefs.get("user_name"):
            self._user_name = prefs["user_name"]

        logger.info(
            "AIChatModule system-start: user=%s, provider=%s",
            self._user_name,
            self._provider,
        )
