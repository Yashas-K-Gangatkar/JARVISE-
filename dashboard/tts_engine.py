"""
TTS Engine - Text-to-Speech wrapper supporting both offline and online engines.

Supports:
    - pyttsx3: Offline TTS (no internet required)
    - gTTS: Online TTS with better quality (requires internet)
"""

import threading


class TTSEngine:
    """
    Text-to-Speech engine that converts text to spoken output.

    Uses pyttsx3 for offline synthesis (default) or gTTS
    for higher-quality online synthesis.
    """

    def __init__(self, config):
        self.config = config.get("tts", {})
        self._engine_type = self.config.get("engine", "pyttsx3")
        self._rate = self.config.get("rate", 180)
        self._volume = self.config.get("volume", 1.0)
        self._engine = None

        self._initialize_engine()

    def _initialize_engine(self):
        """Initialize the TTS engine."""
        if self._engine_type == "pyttsx3":
            try:
                import pyttsx3
                self._engine = pyttsx3.init()
                self._engine.setProperty("rate", self._rate)
                self._engine.setProperty("volume", self._volume)
                print("[TTS] Initialized pyttsx3 engine")
            except ImportError:
                print("[TTS] WARNING: pyttsx3 not installed, falling back to gTTS")
                self._engine_type = "gtts"
            except Exception as e:
                print(f"[TTS] ERROR initializing pyttsx3: {e}")
                self._engine_type = "gtts"

    def speak(self, text):
        """
        Convert text to speech and play it.

        Runs in a separate thread to avoid blocking the main loop.

        Args:
            text: Text to speak
        """
        if not text:
            return

        thread = threading.Thread(
            target=self._speak_thread, args=(text,), daemon=True
        )
        thread.start()

    def _speak_thread(self, text):
        """Internal: Speak text in a background thread."""
        print(f"[TTS] Speaking: '{text}'")

        if self._engine_type == "pyttsx3" and self._engine:
            try:
                self._engine.say(text)
                self._engine.runAndWait()
            except Exception as e:
                print(f"[TTS] pyttsx3 error: {e}")

        elif self._engine_type == "gtts":
            try:
                from gtts import gTTS
                import tempfile
                import os

                # Generate speech to temp file
                tts = gTTS(text=text, lang="en")
                with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                    temp_path = f.name
                tts.save(temp_path)

                # Play the audio file
                os.system(f"mpg123 {temp_path} 2>/dev/null || "
                          f"afplay {temp_path} 2>/dev/null || "
                          f"start {temp_path} 2>/dev/null")

                # Clean up
                try:
                    os.unlink(temp_path)
                except:
                    pass

            except ImportError:
                print("[TTS] WARNING: gTTS not installed")
            except Exception as e:
                print(f"[TTS] gTTS error: {e}")

    def set_rate(self, rate):
        """Set the speech rate (pyttsx3 only)."""
        self._rate = rate
        if self._engine:
            self._engine.setProperty("rate", rate)

    def set_volume(self, volume):
        """Set the speech volume (0.0 to 1.0)."""
        self._volume = volume
        if self._engine:
            self._engine.setProperty("volume", volume)

    def list_voices(self):
        """List available voices (pyttsx3 only)."""
        if self._engine:
            voices = self._engine.getProperty("voices")
            for voice in voices:
                print(f"  - {voice.id}: {voice.name}")
            return voices
        return []
