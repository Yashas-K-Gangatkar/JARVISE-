"""
Gesture Detector - Real-time hand gesture recognition using MediaPipe.

Supported gestures:
    - open_palm: Activate/pause assistant
    - thumbs_up: Confirm/yes
    - thumbs_down: Cancel/no
    - victory: Switch dashboard panel
    - point: Select/highlight
"""

import cv2
import threading
import time


class GestureDetectionModule:
    """
    Detects hand gestures through the webcam and publishes gesture events.

    Uses MediaPipe Hands for hand landmark detection and a rule-based
    classifier to map finger states to predefined gestures.
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
        """Main gesture detection loop."""
        try:
            import mediapipe as mp
        except ImportError:
            print("[GestureDetection] Cannot start: mediapipe not installed")
            print("[GestureDetection] Install with: pip install mediapipe")
            return

        mp_hands = mp.solutions.hands
        mp_draw = mp.solutions.drawing_utils

        device_index = self.camera_config.get("device_index", 0)
        max_hands = self.config.get("max_num_hands", 1)
        confidence = self.config.get("confidence_threshold", 0.8)

        cap = cv2.VideoCapture(device_index)
        if not cap.isOpened():
            print(f"[GestureDetection] ERROR: Cannot open camera {device_index}")
            return

        with mp_hands.Hands(
            max_num_hands=max_hands,
            min_detection_confidence=confidence,
            min_tracking_confidence=0.5,
        ) as hands:

            while self._running:
                ret, frame = cap.read()
                if not ret:
                    time.sleep(0.1)
                    continue

                # Convert to RGB for MediaPipe
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                results = hands.process(rgb_frame)

                if results.multi_hand_landmarks:
                    for hand_landmarks in results.multi_hand_landmarks:
                        # Classify gesture from landmarks
                        gesture = self._classify_gesture(hand_landmarks)

                        # Check hold duration
                        self._check_hold(gesture)

                        # Draw hand landmarks (optional)
                        if self.config.get("show_camera", False):
                            mp_draw.draw_landmarks(
                                frame, hand_landmarks, mp_hands.HAND_CONNECTIONS
                            )
                else:
                    # No hand detected - reset hold timer
                    self._current_gesture = None
                    self._gesture_start_time = None

                # Optional: Show camera feed
                if self.config.get("show_camera", False):
                    # Show detected gesture
                    if self._current_gesture:
                        cv2.putText(
                            frame, f"Gesture: {self._current_gesture}",
                            (10, 30), cv2.FONT_HERSHEY_SIMPLEX,
                            1, (0, 255, 0), 2
                        )
                    cv2.imshow("JARVIS-AI Gesture Detection", frame)
                    if cv2.waitKey(1) & 0xFF == ord("q"):
                        break

        cap.release()
        if self.config.get("show_camera", False):
            cv2.destroyAllWindows()

    def _classify_gesture(self, hand_landmarks):
        """
        Classify a hand gesture from MediaPipe landmarks.

        Determines finger states (extended or curled) and maps
        them to predefined gestures.

        Args:
            hand_landmarks: MediaPipe hand landmarks object

        Returns:
            str: Name of the detected gesture, or None
        """
        # Get landmark positions
        landmarks = hand_landmarks.landmark

        # Determine which fingers are extended
        fingers = self._get_finger_states(landmarks)

        # Rule-based gesture classification
        # Thumb: extended if tip is further from palm than IP joint
        # Fingers: extended if tip is above PIP joint (in y-coordinate)

        if all(fingers):
            # All fingers extended = open palm
            return "open_palm"

        if fingers[0] and not any(fingers[1:]):
            # Only thumb extended = thumbs up
            return "thumbs_up"

        if not fingers[0] and not any(fingers[1:]):
            # All fingers curled = fist / thumbs down variant
            # Check thumb position for thumbs down
            return "thumbs_down"

        if fingers[1] and fingers[2] and not fingers[3] and not fingers[4]:
            # Index + middle extended, others curled = victory/peace
            return "victory"

        if fingers[1] and not fingers[2] and not fingers[3] and not fingers[4]:
            # Only index finger extended = point
            return "point"

        return None

    def _get_finger_states(self, landmarks):
        """
        Determine which fingers are extended.

        Returns:
            list: [thumb, index, middle, ring, pinky] - True if extended
        """
        # Thumb: compare tip x with IP joint x
        # (simplified - works for right hand facing camera)
        thumb_extended = landmarks[4].x < landmarks[3].x

        # Other fingers: compare tip y with PIP joint y
        # (lower y = higher on screen = extended)
        index_extended = landmarks[8].y < landmarks[6].y
        middle_extended = landmarks[12].y < landmarks[10].y
        ring_extended = landmarks[16].y < landmarks[14].y
        pinky_extended = landmarks[20].y < landmarks[18].y

        return [thumb_extended, index_extended, middle_extended, ring_extended, pinky_extended]

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
