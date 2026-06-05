"""
Face Detection Module - Real-time face detection and recognition.

Uses OpenCV for video capture and face_recognition library
for face detection and identification.
"""

import cv2
import threading
import time
import os
import json
import numpy as np


class FaceDetectionModule:
    """
    Detects faces through the webcam and publishes face events.

    Features:
    - Real-time face detection using OpenCV + face_recognition
    - Face matching against known user encodings
    - Greeting cooldown to prevent repeated greetings
    - Visual overlay with bounding boxes and names
    """

    def __init__(self, event_bus, config):
        self.event_bus = event_bus
        self.config = config.get("face_recognition", {})
        self.camera_config = config.get("camera", {})

        self._running = False
        self._thread = None
        self._last_greeting_time = {}  # name -> timestamp
        self._known_encodings = []
        self._known_names = []
        self._cooldown = self.config.get("greeting_cooldown_seconds", 300)

        # Load known faces
        self._load_known_faces()

    def _load_known_faces(self):
        """Load face encodings from the known_faces directory."""
        try:
            import face_recognition
        except ImportError:
            print("[FaceDetection] WARNING: face_recognition not installed.")
            print("[FaceDetection] Install with: pip install face-recognition")
            return

        known_faces_dir = self.config.get("known_faces_dir", "known_faces")
        face_data_file = os.path.join(known_faces_dir, "face_data.json")

        # Try loading pre-computed encodings
        if os.path.exists(face_data_file):
            with open(face_data_file, "r") as f:
                face_data = json.load(f)
            self._known_names = list(face_data.keys())
            self._known_encodings = [
                np.array(enc) for enc in face_data.values()
            ]
            print(
                f"[FaceDetection] Loaded {len(self._known_names)} known faces "
                f"from {face_data_file}"
            )
        else:
            print(f"[FaceDetection] No face data found at {face_data_file}")
            print("[FaceDetection] Run register_face.py to register users")

    def start(self):
        """Start the face detection loop."""
        self._running = True
        self._thread = threading.Thread(
            target=self._detection_loop, daemon=True, name="FaceDetection"
        )
        self._thread.start()
        print("[FaceDetection] Started")

    def stop(self):
        """Stop the face detection loop."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=3)
        print("[FaceDetection] Stopped")

    def _detection_loop(self):
        """Main detection loop - captures frames and detects faces."""
        try:
            import face_recognition
        except ImportError:
            print("[FaceDetection] Cannot start: face_recognition not installed")
            return

        device_index = self.camera_config.get("device_index", 0)
        cap = cv2.VideoCapture(device_index)

        if not cap.isOpened():
            print(f"[FaceDetection] ERROR: Cannot open camera {device_index}")
            return

        fps = self.camera_config.get("fps", 30)
        model = self.config.get("model", "hog")
        tolerance = self.config.get("tolerance", 0.6)

        print(f"[FaceDetection] Camera opened (device={device_index}, fps={fps})")

        # Process every Nth frame for performance
        process_every_n = 3
        frame_count = 0

        while self._running:
            ret, frame = cap.read()
            if not ret:
                print("[FaceDetection] WARNING: Frame read failed")
                time.sleep(0.1)
                continue

            frame_count += 1

            # Only process every Nth frame
            if frame_count % process_every_n != 0:
                continue

            # Resize for faster processing
            small_frame = cv2.resize(frame, (0, 0), fx=0.5, fy=0.5)
            rgb_small = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)

            # Detect face locations
            face_locations = face_recognition.face_locations(
                rgb_small, model=model
            )

            if not face_locations:
                # No faces detected - could publish FACE_LOST
                continue

            # Encode detected faces
            face_encodings = face_recognition.face_encodings(
                rgb_small, face_locations
            )

            for face_encoding in face_encodings:
                # Check if face matches any known user
                if self._known_encodings:
                    matches = face_recognition.compare_faces(
                        self._known_encodings, face_encoding, tolerance=tolerance
                    )
                    name = "Unknown"

                    if True in matches:
                        # Use the known face with smallest distance
                        face_distances = face_recognition.face_distance(
                            self._known_encodings, face_encoding
                        )
                        best_match_idx = np.argmin(face_distances)
                        if matches[best_match_idx]:
                            name = self._known_names[best_match_idx]

                    # Publish face recognized event
                    self._handle_face_detected(name)
                else:
                    # No known faces - just detect that a face exists
                    self._handle_face_detected(None)

            # Optional: Show camera feed with overlays
            if self.config.get("show_camera", False):
                self._draw_overlays(frame, face_locations, [])
                cv2.imshow("JARVIS-AI Face Detection", frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break

        cap.release()
        if self.config.get("show_camera", False):
            cv2.destroyAllWindows()

    def _handle_face_detected(self, name):
        """Handle a detected face with greeting cooldown."""
        from ai_core.event_bus import Event, EventTypes

        current_time = time.time()

        if name and name != "Unknown":
            # Check cooldown
            last_time = self._last_greeting_time.get(name, 0)
            if current_time - last_time > self._cooldown:
                self._last_greeting_time[name] = current_time
                self.event_bus.publish(
                    Event(EventTypes.FACE_RECOGNIZED, {"name": name})
                )
            # Still publish detection (without greeting trigger)
            self.event_bus.publish(
                Event(EventTypes.FACE_DETECTED, {"name": name})
            )
        else:
            # Unknown face - just publish detection
            self.event_bus.publish(
                Event(EventTypes.FACE_DETECTED, {"name": None})
            )

    def _draw_overlays(self, frame, face_locations, names):
        """Draw bounding boxes and labels on the camera frame."""
        # Scale back up face locations since we detected on half-size frame
        for (top, right, bottom, left), name in zip(face_locations, names):
            top *= 2
            right *= 2
            bottom *= 2
            left *= 2

            # Draw box
            cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 0), 2)
            # Draw label
            cv2.rectangle(
                frame, (left, bottom - 35), (right, bottom), (0, 255, 0), cv2.FILLED
            )
            font = cv2.FONT_HERSHEY_DUPLEX
            cv2.putText(
                frame, name or "Unknown", (left + 6, bottom - 6),
                font, 0.8, (255, 255, 255), 1
            )
