"""
TTS Engine - Enhanced Text-to-Speech wrapper for the JARVIS AI Assistant.

Supports:
    - pyttsx3: Offline TTS (no internet required, default)
    - gTTS: Online TTS with better quality (requires internet)

Features:
    - EventBus integration: subscribes to SPEAK_REQUEST events
    - Speak queue: serialises multiple requests so they never overlap
    - Stop current speech mid-utterance
    - Voice selection (male / female when the engine provides it)
    - Speech rate and volume control
    - Thread-safe: all synthesis and playback runs on a background worker
    - Graceful fallbacks: pyttsx3 -> gTTS -> console print
"""

import os
import signal
import subprocess
import tempfile
import threading
from queue import Empty, Queue


class TTSEngine:
    """
    Text-to-Speech engine that converts text to spoken output.

    Uses pyttsx3 for offline synthesis (default) or gTTS for higher-quality
    online synthesis.  A dedicated worker thread drains a thread-safe queue
    so that multiple *speak()* calls never overlap.
    """

    # ── Construction / Initialisation ──────────────────────────────────

    def __init__(self, config):
        """
        Initialise the TTS engine with the given configuration.

        Args:
            config: Full application config dict.  The ``tts`` sub-dict is
                    used here and supports these keys:

                    * ``engine``  – ``"pyttsx3"`` (default) or ``"gtts"``
                    * ``rate``    – Words per minute for pyttsx3 (default 180)
                    * ``volume``  – 0.0 … 1.0 (default 1.0)
                    * ``voice``   – ``"male"`` or ``"female"`` (best-effort)
        """
        self.config = config.get("tts", {})
        self._engine_type = self.config.get("engine", "pyttsx3")
        self._rate = self.config.get("rate", 180)
        self._volume = self.config.get("volume", 1.0)
        self._voice_preference = self.config.get("voice", None)  # "male"/"female"

        # pyttsx3 engine instance (only when using pyttsx3)
        self._engine = None

        # Speak queue and worker thread
        self._queue: Queue = Queue()
        self._worker_thread: threading.Thread | None = None
        self._running = False

        # Track the current gTTS subprocess so we can kill it on stop
        self._current_process: subprocess.Popen | None = None
        self._process_lock = threading.Lock()

        # Active-speech flag (for informational queries)
        self._speaking = False
        self._speaking_lock = threading.Lock()

        # EventBus reference (set later via connect_event_bus)
        self._event_bus = None

        # Initialise the underlying engine
        self._initialize_engine()

        # Start the worker thread
        self._start_worker()

    # ── Engine Initialisation (with fallback chain) ────────────────────

    def _initialize_engine(self):
        """Initialise the chosen TTS backend, falling back gracefully."""
        if self._engine_type == "pyttsx3":
            if not self._try_init_pyttsx3():
                print("[TTS] WARNING: pyttsx3 unavailable, falling back to gTTS")
                self._engine_type = "gtts"

        if self._engine_type == "gtts":
            if not self._check_gtts_available():
                print("[TTS] WARNING: gTTS unavailable, falling back to console output")
                self._engine_type = "console"

        print(f"[TTS] Active engine: {self._engine_type}")

    def _try_init_pyttsx3(self) -> bool:
        """Attempt to initialise pyttsx3.  Returns True on success."""
        try:
            import pyttsx3

            self._engine = pyttsx3.init()
            self._engine.setProperty("rate", self._rate)
            self._engine.setProperty("volume", self._volume)

            # Apply voice preference if given
            if self._voice_preference:
                self._apply_voice_preference(self._voice_preference)

            print("[TTS] Initialized pyttsx3 engine")
            return True

        except ImportError:
            print("[TTS] pyttsx3 package not installed")
        except Exception as exc:
            print(f"[TTS] ERROR initializing pyttsx3: {exc}")

        return False

    def _check_gtts_available(self) -> bool:
        """Return True if the gTTS package can be imported."""
        try:
            import gtts  # noqa: F401
            return True
        except ImportError:
            print("[TTS] gTTS package not installed")
            return False

    # ── Voice Selection ────────────────────────────────────────────────

    def _apply_voice_preference(self, preference: str):
        """
        Try to set a male or female voice on the pyttsx3 engine.

        This is best-effort: voice naming is platform-dependent so we use
        simple heuristics (check for keywords in the voice name / id).
        """
        if not self._engine:
            return

        voices = self._engine.getProperty("voices")
        if not voices:
            return

        preference = preference.lower()
        target_keywords = {
            "male": ["male", "david", "mark", "james", "daniel", "alex"],
            "female": ["female", "zira", "hazel", "samantha", "karen", "victoria",
                        "susan", "fiona", "tessa"],
        }
        keywords = target_keywords.get(preference, [])

        for voice in voices:
            voice_info = f"{voice.id} {voice.name}".lower()
            for kw in keywords:
                if kw in voice_info:
                    self._engine.setProperty("voice", voice.id)
                    print(f"[TTS] Voice set to '{voice.name}' ({preference})")
                    return

        # Could not find a matching voice – keep the default
        print(f"[TTS] No {preference} voice found; using default")

    # ── Worker Thread ──────────────────────────────────────────────────

    def _start_worker(self):
        """Start (or restart) the speech-worker thread."""
        self._running = True
        self._worker_thread = threading.Thread(
            target=self._worker_loop, daemon=True, name="TTSWorker"
        )
        self._worker_thread.start()
        print("[TTS] Worker thread started")

    def _worker_loop(self):
        """Main loop: dequeue texts and speak them one at a time."""
        while self._running:
            try:
                text = self._queue.get(timeout=0.5)
            except Empty:
                continue

            if text is None:
                # Sentinel – shut down
                break

            with self._speaking_lock:
                self._speaking = True

            try:
                self._speak_sync(text)
            except Exception as exc:
                print(f"[TTS] Error speaking '{text[:50]}…': {exc}")
            finally:
                with self._speaking_lock:
                    self._speaking = False
                self._queue.task_done()

    # ── Public API ─────────────────────────────────────────────────────

    def connect_event_bus(self, event_bus):
        """
        Connect to the application EventBus and subscribe to SPEAK_REQUEST.

        When a ``SPEAK_REQUEST`` event is received the engine reads
        ``event.data["text"]`` and queues it for speaking.

        Args:
            event_bus: An :class:`EventBus` instance.
        """
        self._event_bus = event_bus
        from ai_core.event_bus import EventTypes

        event_bus.subscribe(EventTypes.SPEAK_REQUEST, self._on_speak_request)
        print("[TTS] Connected to EventBus (subscribed to SPEAK_REQUEST)")

    def _on_speak_request(self, event):
        """EventBus callback – queue the text from a SPEAK_REQUEST event."""
        text = event.data.get("text", "")
        if text:
            self.speak(text)

    def speak(self, text: str):
        """
        Queue *text* for speaking (non-blocking).

        The text is appended to an internal queue and will be spoken as
        soon as any previously queued utterance finishes.

        Args:
            text: The text to speak.
        """
        if not text:
            return
        self._queue.put(text)
        print(f"[TTS] Queued: '{text[:80]}{'…' if len(text) > 80 else ''}'")

    def stop_speaking(self):
        """
        Stop the current utterance immediately and clear the queue.

        * For **pyttsx3**: calls ``engine.stop()``.
        * For **gTTS**: terminates the audio playback subprocess.
        * Any pending items in the speak queue are discarded.
        """
        # Clear the queue
        cleared = 0
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
                self._queue.task_done()
                cleared += 1
            except Empty:
                break

        # Stop the active engine
        if self._engine_type == "pyttsx3" and self._engine:
            try:
                self._engine.stop()
            except Exception as exc:
                print(f"[TTS] Error stopping pyttsx3: {exc}")

        # Kill any gTTS playback process
        with self._process_lock:
            if self._current_process is not None:
                try:
                    self._current_process.terminate()
                    self._current_process.wait(timeout=1)
                except Exception:
                    try:
                        self._current_process.kill()
                    except Exception:
                        pass
                self._current_process = None

        with self._speaking_lock:
            self._speaking = False

        print(f"[TTS] Stopped speaking (cleared {cleared} queued items)")

    def set_rate(self, rate: int):
        """
        Set the speech rate.

        For pyttsx3 this maps to words-per-minute (typical range 100–300).
        The value is stored and applied even if the engine is initialised
        later (e.g. after a fallback).

        Args:
            rate: Speech rate in words per minute.
        """
        self._rate = max(50, min(500, rate))
        if self._engine_type == "pyttsx3" and self._engine:
            try:
                self._engine.setProperty("rate", self._rate)
            except Exception as exc:
                print(f"[TTS] Error setting rate: {exc}")
        print(f"[TTS] Rate set to {self._rate}")

    def set_volume(self, volume: float):
        """
        Set the speech volume.

        Args:
            volume: Volume level from 0.0 (silent) to 1.0 (max).
        """
        self._volume = max(0.0, min(1.0, volume))
        if self._engine_type == "pyttsx3" and self._engine:
            try:
                self._engine.setProperty("volume", self._volume)
            except Exception as exc:
                print(f"[TTS] Error setting volume: {exc}")
        print(f"[TTS] Volume set to {self._volume:.2f}")

    def list_voices(self):
        """
        List available voices.

        Returns a list of dicts with keys ``id``, ``name``, and
        ``gender`` (best-guess).  Returns an empty list for non-pyttsx3
        engines.

        Returns:
            list[dict]: Voice information dicts.
        """
        voices_info = []

        if self._engine_type == "pyttsx3" and self._engine:
            try:
                voices = self._engine.getProperty("voices")
                for voice in voices:
                    gender = self._guess_voice_gender(voice)
                    info = {
                        "id": voice.id,
                        "name": voice.name,
                        "gender": gender,
                    }
                    voices_info.append(info)
                    print(f"  - {voice.name} [{gender}] ({voice.id})")
            except Exception as exc:
                print(f"[TTS] Error listing voices: {exc}")
        else:
            print(f"[TTS] Voice listing not supported for engine '{self._engine_type}'")

        return voices_info

    @staticmethod
    def _guess_voice_gender(voice) -> str:
        """Heuristic to guess the gender of a pyttsx3 voice."""
        voice_text = f"{voice.id} {voice.name}".lower()
        female_keywords = ["female", "zira", "hazel", "samantha", "karen",
                           "victoria", "susan", "fiona", "tessa"]
        for kw in female_keywords:
            if kw in voice_text:
                return "female"
        male_keywords = ["male", "david", "mark", "james", "daniel", "alex"]
        for kw in male_keywords:
            if kw in voice_text:
                return "male"
        return "unknown"

    def is_speaking(self) -> bool:
        """Return True if the engine is currently producing speech."""
        with self._speaking_lock:
            return self._speaking

    @property
    def engine_type(self) -> str:
        """Return the active engine type string (``'pyttsx3'``, ``'gtts'``, or ``'console'``)."""
        return self._engine_type

    def shutdown(self):
        """
        Shut down the TTS engine cleanly.

        Stops any current speech, clears the queue, terminates the worker
        thread, and releases resources.
        """
        print("[TTS] Shutting down…")
        self.stop_speaking()
        self._running = False
        # Put a sentinel so the worker thread can exit cleanly
        self._queue.put(None)
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=3)
        if self._engine:
            try:
                del self._engine
            except Exception:
                pass
            self._engine = None
        print("[TTS] Shutdown complete")

    # ── Internal: Synchronous Speech ───────────────────────────────────

    def _speak_sync(self, text: str):
        """Speak *text* synchronously (called from the worker thread)."""
        print(f"[TTS] Speaking: '{text}'")

        if self._engine_type == "pyttsx3" and self._engine:
            self._speak_pyttsx3(text)
        elif self._engine_type == "gtts":
            self._speak_gtts(text)
        else:
            self._speak_console(text)

    # ── pyttsx3 Backend ────────────────────────────────────────────────

    def _speak_pyttsx3(self, text: str):
        """Speak using pyttsx3 (offline)."""
        try:
            self._engine.say(text)
            self._engine.runAndWait()
        except Exception as exc:
            print(f"[TTS] pyttsx3 playback error: {exc}")
            # If pyttsx3 is in a bad state, try to reinitialise once
            try:
                import pyttsx3
                self._engine = pyttsx3.init()
                self._engine.setProperty("rate", self._rate)
                self._engine.setProperty("volume", self._volume)
                self._engine.say(text)
                self._engine.runAndWait()
                print("[TTS] pyttsx3 reinitialised and retry succeeded")
            except Exception as retry_exc:
                print(f"[TTS] pyttsx3 retry also failed: {retry_exc}")
                # Fall back to console so the message is at least visible
                self._speak_console(text)

    # ── gTTS Backend ───────────────────────────────────────────────────

    def _speak_gtts(self, text: str):
        """Speak using gTTS (online, higher quality)."""
        try:
            from gtts import gTTS

            tts = gTTS(text=text, lang="en")
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
                temp_path = tmp.name
            tts.save(temp_path)

            self._play_audio_file(temp_path)

        except ImportError:
            print("[TTS] WARNING: gTTS not installed")
            self._speak_console(text)
        except Exception as exc:
            print(f"[TTS] gTTS error: {exc}")
            self._speak_console(text)
        finally:
            # Clean up temp file
            try:
                if "temp_path" in locals():
                    os.unlink(temp_path)
            except Exception:
                pass

    def _play_audio_file(self, filepath: str):
        """
        Play an audio file using the best available system player.

        Tries (in order): ``mpg123``, ``mpv``, ``ffplay``, ``aplay``,
        ``afplay`` (macOS), ``powershell`` (Windows).  The running
        subprocess is tracked so that :meth:`stop_speaking` can kill it.
        """
        players = [
            ["mpg123", "-q"],          # Linux – lightweight MP3 player
            ["mpv", "--really-quiet", "--no-video"],
            ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet"],
            ["aplay", "-q"],           # Linux – WAV only, but worth trying
        ]

        # Platform-specific players
        if os.name == "nt":
            # Windows: use PowerShell to play media
            players.insert(0, [
                "powershell", "-Command",
                f"(New-Object Media.SoundPlayer '{filepath}').PlaySync()"
            ])
        elif os.uname().sysname == "Darwin":
            players.insert(0, ["afplay"])  # macOS built-in

        for player_cmd in players:
            cmd = player_cmd + [filepath]
            try:
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                with self._process_lock:
                    self._current_process = proc

                proc.wait()
                with self._process_lock:
                    self._current_process = None

                # If the process finished normally, we are done
                if proc.returncode == 0:
                    return
                # If it was killed (e.g. by stop_speaking), don't try others
                if proc.returncode < 0:
                    return

            except FileNotFoundError:
                continue
            except Exception as exc:
                print(f"[TTS] Player {player_cmd[0]} failed: {exc}")
                continue

        # No player worked
        print("[TTS] WARNING: No audio player found; falling back to console")
        self._speak_console(os.path.basename(filepath).replace(".mp3", ""))

    # ── Console Fallback ───────────────────────────────────────────────

    @staticmethod
    def _speak_console(text: str):
        """Ultimate fallback: just print the text to the console."""
        print(f"[TTS] (console) {text}")
