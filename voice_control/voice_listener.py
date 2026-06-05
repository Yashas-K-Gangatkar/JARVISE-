"""
Voice Listener - Listens for wake word and voice commands.

Uses SpeechRecognition library with Google's free API
for speech-to-text conversion.
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
    """

    def __init__(self, event_bus, config):
        self.event_bus = event_bus
        self.config = config.get("voice", {})

        self._running = False
        self._thread = None
        self._wake_word = self.config.get("wake_word", "jarvis").lower()
        self._listen_timeout = self.config.get("listen_timeout", 10)
        self._phrase_limit = self.config.get("phrase_limit", 10)

    def start(self):
        """Start the voice control module."""
        self._running = True
        self._thread = threading.Thread(
            target=self._listening_loop, daemon=True, name="VoiceControl"
        )
        self._thread.start()
        print("[VoiceControl] Started - Say 'Jarvis' to activate")

    def stop(self):
        """Stop the voice control module."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=3)
        print("[VoiceControl] Stopped")

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
                # Listen for wake word
                with microphone as source:
                    audio = recognizer.listen(source, timeout=5, phrase_time_limit=3)

                # Recognize speech
                try:
                    text = recognizer.recognize_google(audio).lower()
                    print(f"[VoiceControl] Heard: '{text}'")

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

        Args:
            recognizer: SpeechRecognition recognizer instance
            microphone: SpeechRecognition microphone instance
        """
        from ai_core.event_bus import Event, EventTypes

        print(f"[VoiceControl] Listening for command ({self._listen_timeout}s)...")

        try:
            with microphone as source:
                audio = recognizer.listen(
                    source,
                    timeout=self._listen_timeout,
                    phrase_time_limit=self._phrase_limit,
                )

            text = recognizer.recognize_google(audio).lower()
            print(f"[VoiceControl] Command: '{text}'")

            # Parse the command
            command, params = self._parse_command(text)

            self.event_bus.publish(
                Event(EventTypes.VOICE_COMMAND, {
                    "text": text,
                    "command": command,
                    "params": params,
                })
            )

        except sr.WaitTimeoutError:
            print("[VoiceControl] Command timeout - no speech detected")
            self.event_bus.publish(Event(EventTypes.VOICE_TIMEOUT))
        except sr.UnknownValueError:
            print("[VoiceControl] Could not understand command")
            self.event_bus.publish(
                Event(EventTypes.SPEAK_REQUEST, {
                    "text": "Sorry, I didn't catch that. Could you repeat?"
                })
            )
        except Exception as e:
            print(f"[VoiceControl] Command error: {e}")

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

        # Unknown command
        return "unknown", {"raw_text": text}
