"""
Voice Listener - Listens for wake word and voice commands.

Uses SpeechRecognition library with Google's free API
for speech-to-text conversion.

Features:
    - Wake word detection
    - Continuous listening in background thread
    - Command parsing with keyword matching
    - Configurable listen timeout
    - TTS feedback loop prevention (mutes mic while JARVIS speaks)
"""

import threading
import time


class VoiceControlModule:
    """
    Listens for the wake word 'Jarvis' and processes voice commands.

    Features:
    - Wake word detection
    - Continuous listening in background thread
    - Command parsing with keyword matching
    - Configurable listen timeout
    - TTS feedback loop prevention: ignores microphone input while
      JARVIS is speaking, so the mic doesn't pick up its own TTS
      output and mistake it for a command.
    """

    # Phrases that JARVIS itself speaks — if the mic picks these up,
    # they should be ignored to prevent the feedback loop.
    _TTS_OWN_PHRASES = [
        "yes how can i help you",
        "how can i help you",
        "i can help you",
        "fetching today's news",
        "checking stock market",
        "loading project status",
        "hello how can i help",
        "good morning",
        "good afternoon",
        "good evening",
        "jarvis is online",
        "at your service",
        "confirmed",
        "cancelled",
        "paused",
        "volume up",
        "volume down",
        "microphone muted",
        "i encountered a problem",
        "sorry i didn't catch that",
        "user left going to standby",
        "which application would you like",
        "i'm sorry i don't know how to open",
        "i couldn't find",
        "i had trouble opening",
    ]

    def __init__(self, event_bus, config):
        self.event_bus = event_bus
        self.config = config.get("voice", {})

        self._running = False
        self._thread = None
        self._wake_word = self.config.get("wake_word", "jarvis").lower()
        self._listen_timeout = self.config.get("listen_timeout", 10)
        self._phrase_limit = self.config.get("phrase_limit", 10)

        # ── TTS Feedback Loop Prevention ──────────────────────────────
        # When JARVIS speaks, we set _tts_speaking = True so the mic
        # listener ignores any audio during that time.  A timer resets
        # the flag after the estimated speech duration has elapsed.
        self._tts_speaking = False
        self._tts_lock = threading.Lock()
        self._tts_timer = None

        # Post-speech cooldown: after TTS finishes, wait a short gap
        # before resuming mic listening.  This prevents the tail-end of
        # the TTS output from being captured.
        self._post_speech_cooldown = 0.8  # seconds

    def start(self):
        """Start the voice control module."""
        self._running = True
        self._thread = threading.Thread(
            target=self._listening_loop, daemon=True, name="VoiceControl"
        )
        self._thread.start()

        # Subscribe to SPEAK_REQUEST events to track when JARVIS is speaking
        from ai_core.event_bus import EventTypes
        self.event_bus.subscribe(EventTypes.SPEAK_REQUEST, self._on_speak_request)

        print("[VoiceControl] Started - Say 'Jarvis' to activate")

    def stop(self):
        """Stop the voice control module."""
        self._running = False
        if self._tts_timer is not None:
            self._tts_timer.cancel()
            self._tts_timer = None
        if self._thread:
            self._thread.join(timeout=3)
        print("[VoiceControl] Stopped")

    # ── TTS Feedback Loop Prevention ─────────────────────────────────

    def _on_speak_request(self, event):
        """
        Handle SPEAK_REQUEST events from the EventBus.

        When JARVIS is about to speak, we mute the microphone listener
        for the estimated duration of the speech plus a small cooldown.
        This prevents the mic from picking up JARVIS's own voice and
        treating it as a user command (the feedback loop problem).
        """
        text = event.data.get("text", "")
        if not text:
            return

        # Estimate speech duration: average ~150 words/min + buffer
        word_count = len(text.split())
        duration = max(2.0, (word_count / 150.0) * 60.0 + 1.5)

        with self._tts_lock:
            self._tts_speaking = True
            # Cancel any existing timer
            if self._tts_timer is not None:
                self._tts_timer.cancel()
            # Set a timer to unmute after speech finishes + cooldown
            self._tts_timer = threading.Timer(
                duration + self._post_speech_cooldown,
                self._tts_speaking_finished
            )
            self._tts_timer.daemon = True
            self._tts_timer.start()

    def _tts_speaking_finished(self):
        """Called when the estimated TTS speech duration has elapsed."""
        with self._tts_lock:
            self._tts_speaking = False
            self._tts_timer = None

    def _is_tts_speaking(self) -> bool:
        """Check if TTS is currently speaking (mic should be muted)."""
        with self._tts_lock:
            return self._tts_speaking

    def _is_tts_own_phrase(self, text: str) -> bool:
        """
        Check if the recognized text matches something JARVIS itself said.

        This is a second line of defense against the feedback loop — even
        if the timing-based mute doesn't perfectly cover the TTS output,
        known TTS phrases are filtered out.
        """
        text_lower = text.lower().strip()
        for phrase in self._TTS_OWN_PHRASES:
            if phrase in text_lower:
                return True
        return False

    # ── Main Listening Loop ──────────────────────────────────────────

    def _listening_loop(self):
        """Main listening loop."""
        try:
            import speech_recognition as sr
        except ImportError:
            print("[VoiceControl] Cannot start: SpeechRecognition not installed")
            print("[VoiceControl] Install with: pip install SpeechRecognition PyAudio")
            return

        recognizer = sr.Recognizer()
        microphone = sr.Microphone()

        # Adjust for ambient noise
        print("[VoiceControl] Adjusting for ambient noise...")
        with microphone as source:
            recognizer.adjust_for_ambient_noise(source, duration=2)
        print("[VoiceControl] Ready! Say 'Jarvis' to activate.")

        while self._running:
            try:
                # ── Skip listening while JARVIS is speaking ───────────
                # This is the primary feedback-loop prevention: we simply
                # don't listen to the mic at all while TTS is active.
                if self._is_tts_speaking():
                    time.sleep(0.3)
                    continue

                # Listen for wake word
                with microphone as source:
                    audio = recognizer.listen(source, timeout=5, phrase_time_limit=3)

                # Recognize speech
                try:
                    text = recognizer.recognize_google(audio).lower()
                    print(f"[VoiceControl] Heard: '{text}'")

                    # Filter out TTS own phrases (feedback loop defense #2)
                    if self._is_tts_own_phrase(text):
                        print(f"[VoiceControl] Ignoring TTS feedback: '{text}'")
                        continue

                    # Check for wake word
                    if self._wake_word in text:
                        from ai_core.event_bus import Event, EventTypes

                        print(f"[VoiceControl] Wake word detected!")
                        self.event_bus.publish(
                            Event(EventTypes.WAKE_WORD_DETECTED, {
                                "text": text,
                            })
                        )

                        # Now listen for the actual command
                        self._listen_for_command(recognizer, microphone)

                except sr.UnknownValueError:
                    # Speech not understood - ignore
                    pass
                except sr.RequestError as e:
                    print(f"[VoiceControl] API error: {e}")
                    time.sleep(1)

            except sr.WaitTimeoutError:
                # No speech detected - continue listening
                continue
            except Exception as e:
                print(f"[VoiceControl] Error: {e}")
                time.sleep(0.5)

    def _listen_for_command(self, recognizer, microphone):
        """
        Listen for a command after wake word is detected.

        Waits for JARVIS's "Yes, how can I help you?" TTS to finish,
        then listens for the user's actual command.  If the mic picks
        up JARVIS's own TTS output, it retries up to 3 times instead
        of giving up.

        Args:
            recognizer: SpeechRecognition recognizer instance
            microphone: SpeechRecognition microphone instance
        """
        import speech_recognition as sr
        from ai_core.event_bus import Event, EventTypes

        max_retries = 3  # how many times to retry after TTS feedback

        for attempt in range(max_retries + 1):
            print(f"[VoiceControl] Listening for command ({self._listen_timeout}s)...")

            try:
                # ── Wait for TTS to finish before listening ──────────
                # After the wake word, JARVIS says "Yes, how can I help you?"
                # We need to wait for that TTS to complete before we start
                # listening for the actual command.
                #
                # IMPORTANT: There's a race condition — the SPEAK_REQUEST
                # event might not have been published yet when we first
                # check _is_tts_speaking().  So we do an initial fixed
                # delay to give the event bus time to deliver the event,
                # THEN check the flag.
                if attempt == 0:
                    # First attempt: give the event bus time to publish
                    # the SPEAK_REQUEST and set _tts_speaking = True.
                    time.sleep(0.5)

                tts_wait = 0
                while self._is_tts_speaking() and tts_wait < 10:
                    time.sleep(0.3)
                    tts_wait += 0.3

                # Extra pause after TTS finishes to let the mic settle
                if tts_wait > 0:
                    time.sleep(0.5)

                with microphone as source:
                    audio = recognizer.listen(
                        source,
                        timeout=self._listen_timeout,
                        phrase_time_limit=self._phrase_limit,
                    )

                text = recognizer.recognize_google(audio).lower()
                print(f"[VoiceControl] Command: '{text}'")

                # Filter out TTS own phrases (feedback loop defense #2)
                if self._is_tts_own_phrase(text):
                    print(f"[VoiceControl] Ignoring TTS feedback in command: '{text}' — retrying...")
                    # Don't return — loop back and listen again for the
                    # user's real command.
                    time.sleep(0.5)
                    continue

                # Parse the command
                command, params = self._parse_command(text)

                self.event_bus.publish(
                    Event(EventTypes.VOICE_COMMAND, {
                        "text": text,
                        "command": command,
                        "params": params,
                    })
                )
                return  # command processed, we're done

            except sr.WaitTimeoutError:
                print("[VoiceControl] Command timeout - no speech detected")
                self.event_bus.publish(Event(EventTypes.VOICE_TIMEOUT))
                return
            except sr.UnknownValueError:
                print("[VoiceControl] Could not understand command")
                # Only ask the user to repeat on the last attempt
                if attempt >= max_retries:
                    self.event_bus.publish(
                        Event(EventTypes.SPEAK_REQUEST, {
                            "text": "Sorry, I didn't catch that. Could you repeat?"
                        })
                    )
                else:
                    print("[VoiceControl] Retrying...")
                    continue
                return
            except Exception as e:
                print(f"[VoiceControl] Command error: {e}")
                return

        # All retries exhausted
        print("[VoiceControl] Max retries reached — returning to wake word listening")

    def _parse_command(self, text):
        """
        Parse voice text into command and parameters.

        Uses keyword matching to determine user intent.

        Args:
            text: Recognized speech text (lowercase)

        Returns:
            tuple: (command, params) where command is a string
                   and params is a dict
        """
        from .command_mappings import COMMAND_KEYWORDS

        text_words = text.split()

        for command, keywords in COMMAND_KEYWORDS.items():
            for keyword in keywords:
                if keyword in text_words or keyword in text:
                    return command, {"raw_text": text}

        # Unknown command → will be routed to AI Chat by AssistantCore
        return "unknown", {"raw_text": text}
