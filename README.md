# JARVIS-AI: Intelligent Personal Assistant

A Python-based AI assistant that responds to hand gestures and voice commands, featuring face recognition auto-start, news updates, stock market data, and project progress tracking.

## Features

- **Face Recognition Auto-Start**: Detects users via webcam and greets them with a personalized, time-appropriate voice message
- **Hand Gesture Control**: Control the assistant using 5 predefined hand gestures through your webcam
- **Voice Commands**: Interact using natural language voice commands with wake word detection ("Jarvis")
- **Personalized Dashboard**: Displays news, stocks, project progress, and preferences
- **Text-to-Speech**: Spoken responses for all interactions

## Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/YOUR_TEAM/jarvis-ai.git
cd jarvis-ai
```

### 2. Create Virtual Environment

```bash
python -m venv venv

# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure

```bash
cp config.example.yaml config.yaml
# Edit config.yaml with your API keys and preferences
```

### 5. Register Your Face

```bash
python register_face.py --name "Your Name" --image path/to/your/photo.jpg
```

### 6. Run

```bash
python main.py
```

## Supported Gestures

| Gesture | Action | Voice Alternative |
|---------|--------|-------------------|
| Open Palm | Pause/Resume | "Jarvis, pause" |
| Thumbs Up | Confirm/Yes | "Yes" |
| Thumbs Down | Cancel/No | "No" |
| Victory Sign | Switch Panel | "Next panel" |
| Point (Index) | Select | "Select this" |

## Voice Commands

Say "Jarvis" followed by any command:

- "Jarvis, what's the news?"
- "Jarvis, show me stocks"
- "Jarvis, project status"
- "Jarvis, help"

## Project Structure

```
jarvis-ai/
├── main.py                  # Application entry point
├── config.yaml              # Configuration file
├── requirements.txt         # Python dependencies
├── register_face.py         # Face registration tool
├── face_recognition/        # Face detection module
├── gesture_control/         # Hand gesture module
├── voice_control/           # Voice command module
├── ai_core/                 # Core assistant logic
├── dashboard/               # Dashboard & TTS module
├── data_integration/        # External data providers
├── tests/                   # Unit and integration tests
├── known_faces/             # Reference face photos
└── assets/                  # Icons, sounds, images
```

## Team

| Role | Module |
|------|--------|
| Member 1 | Face Recognition |
| Member 2 | Gesture Control |
| Member 3 | Voice Control |
| Member 4 | AI Core (Team Lead) |
| Member 5 | Dashboard & TTS |

## License

This project is for educational purposes.
