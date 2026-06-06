"""
Gesture Detector - Real-time hand gesture recognition using MediaPipe.

Uses the new MediaPipe Hand Landmarker API (mediapipe 0.10.35+) which
replaces the deprecated mp.solutions.hands module.

Supported gestures:
    - open_palm: Activate/pause assistant
    - thumbs_up: Confirm/yes
    - thumbs_down: Cancel/no (fist)
    - victory: Switch dashboard panel (peace sign)
    - point: Select/highlight (pointing)
"""

import cv2
import threading
import time
import os
import urllib.request


MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/"
    "hand_landmarker/hand_landmarker/float16/latest/hand_landmarker.task"
)
MODEL_FILENAME = "hand_landmarker.task"


class GestureDetectionModule:
    """
    Detects hand gestures through the webcam and publishes gesture events.

    Uses MediaPipe Hand Landmarker (tasks API) for hand landmark detection
    and a rule-based classifier to map finger states to predefined gestures.
    """

    def __init__(self, event_bus, config):
        self.event_bus = event_bus
        self.config = config.get("gesture", {})
        self.camera_config = config.get("camera", {})

        self._running = False
        self._thread = None
        self._hold_duration = self.config.get("hold_duration_seconds", 0.5)
        self._current_gesture = None
        self._gesture_start_time = None

        # Model path: look in the gesture_control directory first, then cwd
        self._model_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), MODEL_FILENAME
        )

    def _ensure_model(self):
        """
        Download the hand_landmarker.task model file if it is not present.

        Returns:
            str: Path to the model file, or None on failure.
        """
        if os.path.isfile(self._model_path):
            return self._model_path

        print(f"[GestureDetection] Model not found at {self._model_path}")
        print(f"[GestureDetection] Downloading from {MODEL_URL} ...")
        try:
            os.makedirs(os.path.dirname(self._model_path), exist_ok=True)
            urllib.request.urlretrieve(MODEL_URL, self._model_path)
            print(f"[GestureDetection] Model downloaded to {self._model_path}")
            return self._model_path
        except Exception as exc:
            print(f"[GestureDetection] ERROR: Failed to download model: {exc}")
            return None

    def start(self):
        """Start the gesture detection loop."""
        self._running = True
        self._thread = threading.Thread(
            target=self._detection_loop, daemon=True, name="GestureDetection"
        )
        self._thread.start()
        print("[GestureDetection] Started")

    def stop(self):
        """Stop the gesture detection loop."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=3)
        print("[GestureDetection] Stopped")

    def _detection_loop(self):
        """Main gesture detection loop using the new MediaPipe Tasks API."""
        # ---- import & validate mediapipe ----
        try:
            import mediapipe as mp
        except ImportError:
            print("[GestureDetection] Cannot start: mediapipe not installed")
            print("[GestureDetection] Install with: pip install mediapipe")
            return

        # Verify the new tasks API is available
        try:
            HandLandmarker = mp.tasks.vision.HandLandmarker
            HandLandmarkerOptions = mp.tasks.vision.HandLandmarkerOptions
            BaseOptions = mp.tasks.BaseOptions
            VisionRunningMode = mp.tasks.vision.RunningMode
        except AttributeError:
            print(
                "[GestureDetection] ERROR: mediapipe installed but the "
                "tasks API is not available. You need mediapipe >= 0.10.35. "
                "Current version: " + getattr(mp, "__version__", "unknown")
            )
            return

        # ---- ensure model file is present ----
        model_path = self._ensure_model()
        if model_path is None:
            return

        # ---- create HandLandmarker ----
        max_hands = self.config.get("max_num_hands", 1)
        confidence = self.config.get("confidence_threshold", 0.8)

        options = HandLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=model_path),
            running_mode=VisionRunningMode.VIDEO,
            num_hands=max_hands,
            min_hand_detection_confidence=confidence,
            min_hand_presence_confidence=0.5,
            min_tracking_confidence=0.5,
        )

        # ---- open camera ----
        device_index = self.camera_config.get("device_index", 0)
        cap = cv2.VideoCapture(device_index)
        if not cap.isOpened():
            print(f"[GestureDetection] ERROR: Cannot open camera {device_index}")
            return

        try:
            detector = HandLandmarker.create_from_options(options)
            print("[GestureDetection] HandLandmarker created successfully")

            timestamp_ms = 0

            while self._running:
                ret, frame = cap.read()
                if not ret:
                    time.sleep(0.1)
                    continue

                # Convert BGR -> RGB for MediaPipe
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

                # Wrap as mp.Image
                mp_image = mp.Image(
                    image_format=mp.ImageFormat.SRGB, data=rgb_frame
                )

                # Increment timestamp (approximate, based on frame count)
                timestamp_ms += 33  # ~30 fps

                # Detect hand landmarks
                result = detector.detect_for_video(mp_image, timestamp_ms)

                if result.hand_landmarks:
                    # Process the first detected hand only
                    landmarks = result.hand_landmarks[0]
                    gesture = self._classify_gesture(landmarks)
                    self._check_hold(gesture)

                    # Optional: draw landmarks on frame
                    if self.config.get("show_camera", False):
                        self._draw_landmarks(frame, landmarks)
                else:
                    # No hand detected - reset hold timer
                    self._current_gesture = None
                    self._gesture_start_time = None

                # Optional: Show camera feed
                if self.config.get("show_camera", False):
                    if self._current_gesture:
                        cv2.putText(
                            frame,
                            f"Gesture: {self._current_gesture}",
                            (10, 30),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            1,
                            (0, 255, 0),
                            2,
                        )
                    cv2.imshow("JARVIS-AI Gesture Detection", frame)
                    if cv2.waitKey(1) & 0xFF == ord("q"):
                        break

        finally:
            # Clean up
            try:
                detector.close()
            except Exception:
                pass
            cap.release()
            if self.config.get("show_camera", False):
                cv2.destroyAllWindows()

    # ------------------------------------------------------------------
    # Gesture classification
    # ------------------------------------------------------------------

    def _classify_gesture(self, landmarks):
        """
        Classify a hand gesture from MediaPipe Hand Landmarker results.

        Determines finger states (extended or curled) and maps
        them to predefined gestures.

        Args:
            landmarks: List of 21 NormalizedLandmark objects from
                       result.hand_landmarks[0].  Each has .x, .y, .z
                       attributes normalised to [0, 1].

        Returns:
            str: Name of the detected gesture, or None
        """
        fingers = self._get_finger_states(landmarks)

        # All fingers extended -> open palm
        if all(fingers):
            return "open_palm"

        # Only thumb extended -> thumbs up
        if fingers[0] and not any(fingers[1:]):
            return "thumbs_up"

        # All fingers curled -> fist / thumbs down
        if not fingers[0] and not any(fingers[1:]):
            return "thumbs_down"

        # Index + middle extended, others curled -> victory / peace sign
        if fingers[1] and fingers[2] and not fingers[3] and not fingers[4]:
            return "victory"

        # Only index finger extended -> point
        if fingers[1] and not fingers[2] and not fingers[3] and not fingers[4]:
            return "point"

        return None

    def _get_finger_states(self, landmarks):
        """
        Determine which fingers are extended.

        Args:
            landmarks: List of 21 NormalizedLandmark objects.

        Returns:
            list: [thumb, index, middle, ring, pinky] - True if extended
        """
        # Thumb: compare tip (4) x with IP joint (3) x.
        # For a right hand facing the camera, thumb extended means tip.x < ip.x.
        # For a left hand it would be the reverse.  We use a simple heuristic
        # that works for the common case; a more robust version would inspect
        # result.handedness to pick the correct comparison direction.
        thumb_extended = landmarks[4].x < landmarks[3].x

        # Other fingers: tip y < PIP y means finger is raised (image y-axis
        # points downward, so a lower y-value means the tip is higher).
        index_extended = landmarks[8].y < landmarks[6].y
        middle_extended = landmarks[12].y < landmarks[10].y
        ring_extended = landmarks[16].y < landmarks[14].y
        pinky_extended = landmarks[20].y < landmarks[18].y

        return [thumb_extended, index_extended, middle_extended, ring_extended, pinky_extended]

    # ------------------------------------------------------------------
    # Hold-duration logic & event publishing
    # ------------------------------------------------------------------

    def _check_hold(self, gesture):
        """
        Check if a gesture has been held for the required duration.

        Only triggers an event after the gesture is held stable
        for the configured hold duration.
        """
        from ai_core.event_bus import Event, EventTypes

        if gesture == self._current_gesture:
            # Same gesture - check if hold duration reached
            if self._gesture_start_time:
                elapsed = time.time() - self._gesture_start_time
                if elapsed >= self._hold_duration:
                    # Gesture held long enough - publish event (once)
                    if elapsed < self._hold_duration + 0.1:
                        self.event_bus.publish(
                            Event(EventTypes.GESTURE_DETECTED, {
                                "gesture": gesture,
                                "hold_duration": elapsed,
                            })
                        )
        else:
            # New gesture - start timer
            self._current_gesture = gesture
            self._gesture_start_time = time.time()

    # ------------------------------------------------------------------
    # Optional visualisation
    # ------------------------------------------------------------------

    def _draw_landmarks(self, frame, landmarks):
        """
        Draw hand landmarks and connections on the frame for debugging.

        Args:
            frame: OpenCV BGR image (numpy array)
            landmarks: List of 21 NormalizedLandmark objects (x, y in [0,1])
        """
        h, w, _ = frame.shape

        # Landmark connections (mirroring mp.solutions.hands.HAND_CONNECTIONS)
        connections = [
            (0, 1), (1, 2), (2, 3), (3, 4),        # thumb
            (0, 5), (5, 6), (6, 7), (7, 8),        # index
            (5, 9), (9, 10), (10, 11), (11, 12),   # middle
            (9, 13), (13, 14), (14, 15), (15, 16), # ring
            (13, 17), (17, 18), (18, 19), (19, 20),# pinky
            (0, 17),                                 # palm base
        ]

        # Draw connections
        for start_idx, end_idx in connections:
            pt1 = (int(landmarks[start_idx].x * w), int(landmarks[start_idx].y * h))
            pt2 = (int(landmarks[end_idx].x * w), int(landmarks[end_idx].y * h))
            cv2.line(frame, pt1, pt2, (255, 255, 255), 2)

        # Draw landmark points
        for lm in landmarks:
            cx, cy = int(lm.x * w), int(lm.y * h)
            cv2.circle(frame, (cx, cy), 4, (0, 255, 0), -1)
