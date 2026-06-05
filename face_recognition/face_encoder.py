"""
Face Encoder - Register and store face encodings for known users.

Usage:
    python -m face_recognition.face_encoder --name "John" --image path/to/photo.jpg
"""

import os
import sys
import json
import argparse


def register_face(name, image_path, known_faces_dir="known_faces"):
    """
    Register a new face by encoding it from an image file.

    Args:
        name: The person's name
        image_path: Path to a photo of the person
        known_faces_dir: Directory to store face data
    """
    try:
        import face_recognition
    except ImportError:
        print("ERROR: face_recognition not installed.")
        print("Install with: pip install face-recognition")
        sys.exit(1)

    if not os.path.exists(image_path):
        print(f"ERROR: Image not found: {image_path}")
        sys.exit(1)

    # Load the image
    image = face_recognition.load_image_file(image_path)
    encodings = face_recognition.face_encodings(image)

    if not encodings:
        print(f"ERROR: No face found in image: {image_path}")
        sys.exit(1)

    # Use the first face found
    encoding = encodings[0]

    # Load existing face data
    face_data_file = os.path.join(known_faces_dir, "face_data.json")
    if os.path.exists(face_data_file):
        with open(face_data_file, "r") as f:
            face_data = json.load(f)
    else:
        face_data = {}

    # Save the encoding
    face_data[name] = encoding.tolist()

    # Ensure directory exists
    os.makedirs(known_faces_dir, exist_ok=True)

    # Write face data
    with open(face_data_file, "w") as f:
        json.dump(face_data, f, indent=2)

    # Also copy the reference image
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
