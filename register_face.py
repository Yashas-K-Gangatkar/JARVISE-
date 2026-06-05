#!/usr/bin/env python3
"""
Register Face - Command-line tool to register a new face for JARVIS-AI.

Usage:
    python register_face.py --name "John" --image path/to/photo.jpg
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from face_recognition.face_encoder import register_face
import argparse


def main():
    parser = argparse.ArgumentParser(
        description="Register a face for JARVIS-AI face recognition"
    )
    parser.add_argument(
        "--name", required=True,
        help="Person's name (e.g., 'John')"
    )
    parser.add_argument(
        "--image", required=True,
        help="Path to a clear photo of the person's face"
    )
    parser.add_argument(
        "--dir", default="known_faces",
        help="Directory to store face data (default: known_faces)"
    )

    args = parser.parse_args()

    print("=" * 50)
    print("JARVIS-AI Face Registration")
    print("=" * 50)
    print(f"Name:  {args.name}")
    print(f"Image: {args.image}")
    print()

    register_face(args.name, args.image, args.dir)

    print()
    print("Face registered successfully!")
    print("The system will now recognize this person when they appear on camera.")


if __name__ == "__main__":
    main()
