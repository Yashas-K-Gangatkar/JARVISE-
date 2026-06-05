"""
Face Encoder - Register and store face data for known users.

Uses OpenCV's built-in Haar Cascade for face detection.
No external face_recognition library needed.

Usage:
    python -m face_engine.face_encoder --name "John" --image path/to/photo.jpg
"""

import os
import sys
import json
import argparse

import cv2
import numpy as np


def register_face(name, image_path, known_faces_dir="known_faces"):
    """
    Register a new face by detecting it from an image file.

    Uses OpenCV's Haar Cascade to detect the face, then saves
    the reference image and metadata for later recognition.

    Args:
        name: The person's name
        image_path: Path to a photo of the person
        known_faces_dir: Directory to store face data
    """
    if not os.path.exists(image_path):
        print(f"ERROR: Image not found: {image_path}")
        sys.exit(1)

    # Load the image in grayscale
    image = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    if image is None:
        print(f"ERROR: Could not read image: {image_path}")
        sys.exit(1)

    # Detect faces using Haar Cascade
    cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    face_cascade = cv2.CascadeClassifier(cascade_path)

    faces = face_cascade.detectMultiScale(
        image, scaleFactor=1.1, minNeighbors=5, minSize=(50, 50)
    )

    if len(faces) == 0:
        print(f"ERROR: No face found in image: {image_path}")
        sys.exit(1)

    # Use the largest face found
    largest = max(faces, key=lambda f: f[2] * f[3])
    x, y, w, h = largest

    # Save face metadata (location info + simple feature descriptor)
    face_data_entry = {
        "registered_at": str(cv2.getTickCount()),
        "face_region": {"x": int(x), "y": int(y), "w": int(w), "h": int(h)},
        "image_size": {"width": int(image.shape[1]), "height": int(image.shape[0])},
    }

    # Load existing face data
    os.makedirs(known_faces_dir, exist_ok=True)
    face_data_file = os.path.join(known_faces_dir, "face_data.json")
    if os.path.exists(face_data_file):
        with open(face_data_file, "r") as f:
            face_data = json.load(f)
    else:
        face_data = {}

    # Save the face data
    face_data[name] = face_data_entry

    with open(face_data_file, "w") as f:
        json.dump(face_data, f, indent=2)

    # Copy the reference image
    import shutil
    ext = os.path.splitext(image_path)[1]
    ref_image = os.path.join(known_faces_dir, f"{name}{ext}")
    shutil.copy2(image_path, ref_image)

    print(f"[FaceEncoder] Registered face for '{name}'")
    print(f"[FaceEncoder] Face data saved to {face_data_file}")
    print(f"[FaceEncoder] Reference image saved to {ref_image}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Register a face for JARVIS-AI")
    parser.add_argument("--name", required=True, help="Person's name")
    parser.add_argument("--image", required=True, help="Path to photo")
    parser.add_argument(
        "--dir", default="known_faces", help="Known faces directory"
    )
    args = parser.parse_args()

    register_face(args.name, args.image, args.dir)
