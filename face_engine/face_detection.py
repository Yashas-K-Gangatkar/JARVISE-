"""
Face Detection Module - Real-time face detection and recognition.

Uses OpenCV's built-in Haar Cascade and LBPH Face Recognizer.
No external face_recognition library needed.
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
    - Real-time face detection using OpenCV Haar Cascades
    - Face matching using LBPH (Local Binary Patterns Histograms) recognizer
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
        self._known_names = []
        self._cooldown = self.config.get("greeting_cooldown_seconds", 300)

        # OpenCV face detector (Haar Cascade - built into OpenCV)
        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        self._face_cascade = cv2.CascadeClassifier(cascade_path)

        # LBPH Face Recognizer (built into OpenCV)
        self._recognizer = cv2.face.LBPHFaceRecognizer_create(
            radius=1, neighbors=8, grid_x=8, grid_y=8
        )
        self._recognizer_trained = False

        # Load known faces
        self._load_known_faces()

    def _load_known_faces(self):
        """Load face data and train the LBPH recognizer."""
        known_faces_dir = self.config.get("known_faces_dir", "known_faces")
        face_data_file = os.path.join(known_faces_dir, "face_data.json")

        if not os.path.exists(face_data_file):
            print(f"[FaceDetection] No face data found at {face_data_file}")
            print("[FaceDetection] Run register_face.py to register users")
            return

        with open(face_data_file, "r") as f:
            face_data = json.load(f)

        self._known_names = list(face_data.keys())

        if not self._known_names:
            print("[FaceDetection] No registered faces found")
            return

        # Train recognizer from reference images
        training_images = []
        training_labels = []
        label_map = {}  # index -> name

        for label_idx, name in enumerate(self._known_names):
            label_map[label_idx] = name
            # Look for reference image
            ref_jpg = os.path.join(known_faces_dir, f"{name}.jpg")
            ref_png = os.path.join(known_faces_dir, f"{name}.png")

            ref_image = ref_jpg if os.path.exists(ref_jpg) else ref_png

            if os.path.exists(ref_image):
                img = cv2.imread(ref_image, cv2.IMREAD_GRAYSCALE)
                if img is not None:
                    # Detect face in the reference image
                    faces = self._face_cascade.detectMultiScale(
                        img, scaleFactor=1.1, minNeighbors=5, minSize=(50, 50)
                    )
                    if len(faces) > 0:
                        # Use the largest face
                        largest = max(faces, key=lambda f: f[2] * f[3])
                        x, y, w, h = largest
                        face_roi = cv2.resize(img[y:y+h, x:x+w], (200, 200))
                        training_images.append(face_roi)
                        training_labels.append(label_idx)
                    else:
                        print(f"[FaceDetection] WARNING: No face found in {ref_image}")
                else:
                    print(f"[FaceDetection] WARNING: Could not read {ref_image}")
            else:
                print(f"[FaceDetection] WARNING: No reference image for '{name}'")

        if training_images:
            self._recognizer.train(training_images, np.array(training_labels))
            self._recognizer_trained = True
            self._label_map = label_map
            print(
                f"[FaceDetection] Loaded {len(self._known_names)} known faces, "
                f"trained with {len(training_images)} images"
            )
        else:
            print("[FaceDetection] WARNING: Could not train recognizer (no valid reference images)")

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
        device_index = self.camera_config.get("device_index", 0)
        cap = cv2.VideoCapture(device_index)

        if not cap.isOpened():
            print(f"[FaceDetection] ERROR: Cannot open camera {device_index}")
            return

        confidence_threshold = self.config.get("confidence_threshold", 70)

        print(f"[FaceDetection] Camera opened (device={device_index})")

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

            # Convert to grayscale for detection
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            # Detect faces using Haar Cascade
            face_locations = self._face_cascade.detectMultiScale(
                gray, scaleFactor=1.1, minNeighbors=5, minSize=(80, 80)
            )

            if len(face_locations) == 0:
                continue

            # Process each detected face
            for (x, y, w, h) in face_locations:
                name = "Unknown"
                confidence = 0

                if self._recognizer_trained:
                    # Try to recognize the face
                    face_roi = cv2.resize(gray[y:y+h, x:x+w], (200, 200))
                    label, confidence = self._recognizer.predict(face_roi)

                    # LBPH confidence: lower is better. We invert it for clarity
                    # confidence < 70 usually means a good match
                    if confidence < (100 - confidence_threshold):
                        name = self._label_map.get(label, "Unknown")

                # Publish face event
                self._handle_face_detected(name)

            # Optional: Show camera feed with overlays
            if self.config.get("show_camera", False):
                self._draw_overlays(frame, face_locations)
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

    def _draw_overlays(self, frame, face_locations):
        """Draw bounding boxes and labels on the camera frame."""
        for (x, y, w, h) in face_locations:
            # Draw box
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
            # Draw label background
            cv2.rectangle(
                frame, (x, y + h - 35), (x + w, y + h), (0, 255, 0), cv2.FILLED
            )
            font = cv2.FONT_HERSHEY_DUPLEX
            cv2.putText(
                frame, "Face", (x + 6, y + h - 6),
                font, 0.8, (255, 255, 255), 1
            )
