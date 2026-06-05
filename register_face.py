#!/usr/bin/env python3
"""
Register Face - Command-line tool to register a new face for JARVIS-AI.

Usage:
    Mode 1 - From image file:
        python register_face.py --name "John" --image path/to/photo.jpg

    Mode 2 - From camera:
        python register_face.py --name "John" --camera
"""

import sys
import os
import json

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from face_engine.face_encoder import register_face
import argparse


def register_face_from_camera(name, known_faces_dir="known_faces"):
    """
    Register a new face by capturing from the webcam.

    Opens a live camera preview. Press SPACE to capture a frame,
    or Q to quit. The captured frame is processed for face detection
    and encoding.

    Args:
        name: The person's name
        known_faces_dir: Directory to store face data
    """
    try:
        import cv2
    except ImportError:
        print("ERROR: OpenCV (cv2) not installed.")
        print("Install with: pip install opencv-python")
        sys.exit(1)

    try:
        import face_recognition
    except ImportError:
        print("ERROR: face_recognition not installed.")
        print("Install with: pip install face-recognition")
        sys.exit(1)

    import numpy as np

    # Open the webcam
    print("[Camera] Opening webcam...")
    cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        print("ERROR: Could not open webcam. Make sure a camera is connected.")
        sys.exit(1)

    print("[Camera] Webcam opened. Press SPACE to capture, Q to quit.")

    captured_frame = None

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("ERROR: Failed to read frame from camera.")
                sys.exit(1)

            # Show live preview with instructions
            display = frame.copy()
            cv2.putText(
                display,
                "Press SPACE to capture, Q to quit",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 0),
                2,
            )
            cv2.imshow("JARVIS Face Registration", display)

            key = cv2.waitKey(1) & 0xFF

            if key == ord(" "):
                # SPACE pressed - capture the frame
                captured_frame = frame.copy()
                print("[Camera] Frame captured!")
                break
            elif key == ord("q") or key == ord("Q"):
                # Q pressed - quit without capturing
                print("[Camera] Registration cancelled by user.")
                cap.release()
                cv2.destroyAllWindows()
                sys.exit(0)
    except KeyboardInterrupt:
        print("\n[Camera] Registration cancelled.")
        cap.release()
        cv2.destroyAllWindows()
        sys.exit(0)
    finally:
        cap.release()
        cv2.destroyAllWindows()

    if captured_frame is None:
        print("ERROR: No frame was captured.")
        sys.exit(1)

    # Convert BGR (OpenCV) to RGB (face_recognition)
    rgb_frame = cv2.cvtColor(captured_frame, cv2.COLOR_BGR2RGB)

    # Detect faces in the captured frame
    print("[FaceEncoder] Detecting faces in captured frame...")
    face_locations = face_recognition.face_locations(rgb_frame)
    encodings = face_recognition.face_encodings(rgb_frame, face_locations)

    if not encodings:
        print("ERROR: No face detected in the captured frame.")
        print("Please ensure your face is clearly visible and try again.")
        sys.exit(1)

    # If multiple faces, select the largest one
    if len(encodings) > 1:
        print(f"[FaceEncoder] Multiple faces detected ({len(encodings)}). Using the largest one.")
        # Find the largest face by bounding box area
        largest_idx = 0
        largest_area = 0
        for i, (top, right, bottom, left) in enumerate(face_locations):
            area = (right - left) * (bottom - top)
            if area > largest_area:
                largest_area = area
                largest_idx = i
        encoding = encodings[largest_idx]
    else:
        encoding = encodings[0]

    # Load existing face data
    os.makedirs(known_faces_dir, exist_ok=True)
    face_data_file = os.path.join(known_faces_dir, "face_data.json")
    if os.path.exists(face_data_file):
        with open(face_data_file, "r") as f:
            face_data = json.load(f)
    else:
        face_data = {}

    # Save the encoding
    face_data[name] = encoding.tolist()

    # Write face data
    with open(face_data_file, "w") as f:
        json.dump(face_data, f, indent=2)

    # Save the reference image
    ref_image_path = os.path.join(known_faces_dir, f"{name}.jpg")
    cv2.imwrite(ref_image_path, captured_frame)

    print(f"[FaceEncoder] Registered face for '{name}'")
    print(f"[FaceEncoder] Face data saved to {face_data_file}")
    print(f"[FaceEncoder] Reference image saved to {ref_image_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Register a face for JARVIS-AI face recognition"
    )
    parser.add_argument(
        "--name", required=True,
        help="Person's name (e.g., 'Yashas')"
    )
    parser.add_argument(
        "--image",
        help="Path to a clear photo of the person's face (Mode 1)"
    )
    parser.add_argument(
        "--camera", action="store_true",
        help="Capture face from webcam (Mode 2)"
    )
    parser.add_argument(
        "--dir", default="known_faces",
        help="Directory to store face data (default: known_faces)"
    )

    args = parser.parse_args()

    # Validate that either --image or --camera is provided, but not both
    if not args.image and not args.camera:
        parser.error("Either --image or --camera must be specified")

    if args.image and args.camera:
        parser.error("Specify either --image or --camera, not both")

    print("=" * 50)
    print("JARVIS-AI Face Registration")
    print("=" * 50)
    print(f"Name:  {args.name}")
    if args.image:
        print(f"Mode:  Image file")
        print(f"Image: {args.image}")
    else:
        print(f"Mode:  Camera capture")
    print()

    if args.image:
        # Mode 1: Register from image file
        register_face(args.name, args.image, args.dir)
    else:
        # Mode 2: Register from camera
        register_face_from_camera(args.name, args.dir)

    print()
    print("Face registered successfully!")
    print("The system will now recognize this person when they appear on camera.")


if __name__ == "__main__":
    main()
