"""
Face Engine Module - Detects and identifies human faces.

Uses OpenCV's built-in Haar Cascade and LBPH Face Recognizer.
No external face_recognition library needed.
"""

from .face_detection import FaceDetectionModule

__all__ = ["FaceDetectionModule"]
