# 🤖 JARVIS-AI: Team Division & Project Guide

> *"At your service, sir."* — JARVIS

Welcome to the **JARVIS-AI** mini project! This document is your complete guide to who does what, how to get started, and how we'll build an awesome AI assistant together over the next 8 weeks.

**You do NOT need any Python experience.** We'll learn everything as we go. Every command you need is written out right here — just copy, paste, and run. 💪

---

## 📋 Table of Contents

1. [Project Overview](#-project-overview)
2. [Team Member Assignments](#-team-member-assignments)
3. [How to Get Started](#-how-to-get-started)
4. [Git Workflow](#-git-workflow)
5. [Week-by-Week Schedule](#-week-by-week-schedule-8-weeks)
6. [Testing Checklist](#-testing-checklist)
7. [How Modules Communicate (EventBus)](#-how-modules-communicate-eventbus)
8. [Common Commands & How to Run Them](#-common-commands--how-to-run-them)

---

## 🌟 Project Overview

**JARVIS-AI** is a Python-based intelligent personal assistant inspired by Tony Stark's AI butler. Here's what it does:

| Feature | What It Does |
|---------|-------------|
| 🎭 **Face Recognition** | Detects your face via webcam and greets you by name with a time-appropriate message |
| ✋ **Gesture Control** | Control JARVIS using hand gestures (open palm, thumbs up, fist, etc.) |
| 🎙️ **Voice Commands** | Say "Jarvis" followed by a command — just like in the movies! |
| 📰 **News & Stocks** | Fetches live news headlines and stock market data |
| 📊 **Dashboard** | A futuristic HUD-style dashboard showing everything at a glance |
| 🔊 **Text-to-Speech** | JARVIS talks back to you with spoken responses |

### Project Structure

```
JARVISE-/
├── main.py                      # 🚀 Application entry point
├── config.example.yaml          # ⚙️ Configuration template
├── requirements.txt             # 📦 Python dependencies
├── register_face.py             # 👤 Face registration tool
├── project_status.json          # 📈 Project progress tracker
│
├── face_recognition/            # 👤 Member 1 — Face Recognition
│   ├── __init__.py
│   ├── face_detection.py        #   Camera + face detection loop
│   ├── face_encoder.py          #   Face encoding + comparison
│   └── greeting_engine.py       #   Time-based personalized greetings
│
├── gesture_control/             # ✋ Member 2 — Gesture Control
│   ├── __init__.py
│   ├── gesture_detector.py      #   MediaPipe hand landmark detection
│   └── gesture_mappings.py      #   Gesture → action mapping table
│
├── voice_control/               # 🎙️ Member 3 — Voice Control
│   ├── __init__.py
│   ├── voice_listener.py        #   Wake word + speech recognition
│   └── command_mappings.py      #   Voice keyword → command mapping
│
├── ai_core/                     # 🧠 Member 4 — AI Core + Data Integration
│   ├── __init__.py
│   ├── assistant_core.py        #   State machine + command routing
│   ├── event_bus.py             #   Inter-module event system
│   ├── state_manager.py         #   IDLE → ACTIVE → LISTENING → PROCESSING
│   └── preferences.py           #   User preferences manager
│
├── data_integration/            # 📡 Member 4 — Data Integration
│   ├── __init__.py
│   ├── data_manager.py          #   Orchestrates all data providers
│   ├── news_provider.py         #   NewsAPI / RSS feed fetching
│   ├── stock_provider.py        #   Stock data via yfinance
│   └── project_provider.py      #   Reads project_status.json
│
├── dashboard/                   # 📺 Member 5 — Dashboard + TTS
│   ├── __init__.py
│   ├── dashboard_tkinter.py     #   JARVIS-style HUD dashboard
│   └── tts_engine.py            #   Text-to-speech engine
│
├── tests/                       # 🧪 Test files
│   └── __init__.py
│
├── docs/                        # 📚 Documentation
│   └── __init__.py
│
├── known_faces/                 # 📸 Stored face encodings (created at runtime)
└── assets/                      # 🎨 Icons, sounds, images
```

---

## 👥 Team Member Assignments

---

### 🧑‍💻 Member 1: Face Recognition Module

> *"JARVIS knows who you are."*

| Detail | Value |
|--------|-------|
| **Branch** | `member1-face-recognition` |
| **Folder** | `face_recognition/` |
| **Extra File** | `register_face.py` (project root) |

#### Files You Own

| File | Purpose |
|------|---------|
| `face_recognition/face_detection.py` | Main module — runs camera loop, detects faces in real-time, publishes `FACE_DETECTED` / `FACE_RECOGNIZED` / `FACE_LOST` events on the EventBus |
| `face_recognition/face_encoder.py` | Loads saved face encodings from `known_faces/`, compares a new face encoding against all saved ones, returns the best match name |
| `face_recognition/greeting_engine.py` | Generates a personalized greeting based on the recognized user's name + current time of day (Good morning/afternoon/evening), respects a cooldown so it doesn't repeat |
| `register_face.py` | Standalone command-line tool to register a new user's face — supports `--name` and `--image` flags (from a file), or `--camera` flag (takes a photo from webcam) |

#### Your Responsibilities

- [ ] Make the camera detect faces in real-time using OpenCV
- [ ] Recognize registered users by comparing their face encoding to saved encodings
- [ ] Generate personalized, time-based greetings (e.g., "Good morning, Yashas")
- [ ] Create the `register_face.py` tool so users can add their face to the system
- [ ] Test with multiple people and different lighting conditions
- [ ] Publish `FACE_RECOGNIZED` events to the EventBus so other modules can react

#### Skills You'll Learn

| Skill | What It Is | Why You Need It |
|-------|-----------|-----------------|
| **OpenCV** | Computer vision library for camera access and image processing | To capture and process video frames from the webcam |
| **face_recognition** | Library built on dlib for face detection and encoding | To detect faces and create unique face encodings for comparison |
| **numpy** | Numerical computing library | To handle face encoding arrays (128-dimensional vectors) |

#### Key EventBus Events You'll Publish

```python
from ai_core.event_bus import Event, EventTypes

# When a face is recognized
event_bus.publish(Event(EventTypes.FACE_RECOGNIZED, {
    "name": "Yashas",
    "greeting": "Good morning, Yashas"
}))

# When a face is detected but not recognized
event_bus.publish(Event(EventTypes.FACE_DETECTED, {
    "unknown": True
}))

# When no face is in frame anymore
event_bus.publish(Event(EventTypes.FACE_LOST, {}))
```

---

### 🧑‍💻 Member 2: Gesture Control Module

> *"Control JARVIS with a wave of your hand."*

| Detail | Value |
|--------|-------|
| **Branch** | `member2-gesture-control` |
| **Folder** | `gesture_control/` |

#### Files You Own

| File | Purpose |
|------|---------|
| `gesture_control/gesture_detector.py` | Main module — captures camera frames, uses MediaPipe to detect hand landmarks, classifies the current gesture, implements hold-duration detection (gesture must be held for 0.5 seconds before triggering), publishes `GESTURE_DETECTED` / `GESTURE_HOLD` events |
| `gesture_control/gesture_mappings.py` | Maps gesture names to system actions (e.g., `"open_palm"` → `"pause"`, `"thumbs_up"` → `"confirm"`, `"victory"` → `"switch_panel"`) |

#### Your Responsibilities

- [ ] Detect hand landmarks using MediaPipe (21 landmark points per hand)
- [ ] Classify gestures from landmark positions: open palm, thumbs up, thumbs down, victory sign, point (index finger), fist
- [ ] Implement **hold duration detection** — a gesture must be held for 0.5 seconds before it triggers (prevents accidental triggers)
- [ ] Map each gesture to a system action in `gesture_mappings.py`
- [ ] Show a **visual overlay** on the camera feed when debugging (draw landmarks + gesture label on the frame)
- [ ] Add new gestures beyond the basic ones (e.g., OK sign, rock sign, call me)
- [ ] Publish `GESTURE_HOLD` events to the EventBus with the gesture name and mapped action

#### Skills You'll Learn

| Skill | What It Is | Why You Need It |
|-------|-----------|-----------------|
| **MediaPipe** | Google's ML framework for hand/face/pose detection | To detect 21 hand landmark points from the camera feed |
| **OpenCV** | Computer vision library | To capture camera frames and draw visual overlays |
| **Hand landmark detection** | Detecting specific points on a hand (finger tips, joints, etc.) | To determine which fingers are up/down and classify gestures |

#### Default Gesture Mappings

| Gesture | System Action | Voice Alternative |
|---------|--------------|-------------------|
| Open Palm ✋ | `pause` | "Jarvis, pause" |
| Thumbs Up 👍 | `confirm` | "Yes" |
| Thumbs Down 👎 | `cancel` | "No" |
| Victory Sign ✌️ | `switch_panel` | "Next panel" |
| Point ☝️ | `select` | "Select this" |
| Fist ✊ | `mute` | "Jarvis, mute" |

#### Key EventBus Events You'll Publish

```python
from ai_core.event_bus import Event, EventTypes

# When a gesture is held for the required duration
event_bus.publish(Event(EventTypes.GESTURE_HOLD, {
    "gesture": "open_palm",
    "action": "pause"
}))

# When any gesture is detected (even before hold duration)
event_bus.publish(Event(EventTypes.GESTURE_DETECTED, {
    "gesture": "open_palm",
    "confidence": 0.95
}))
```

#### How to Classify Gestures (Hint!)

MediaPipe gives you 21 landmark points. Here's the logic:

```
Index finger up?   → landmark 8.y < landmark 6.y
Middle finger up?  → landmark 12.y < landmark 10.y
Ring finger up?    → landmark 16.y < landmark 14.y
Pinky up?          → landmark 20.y < landmark 18.y
Thumb up?          → landmark 4.x < landmark 3.x (for right hand)

Open Palm  = all 5 fingers up
Fist       = all 5 fingers down
Thumbs Up  = only thumb up
Point      = only index finger up
Victory    = index + middle up
```

*(Note: y-coordinates increase downward in image space, so "up" means lower y value)*

---

### 🧑‍💻 Member 3: Voice Control Module

> *"Just say the word."*

| Detail | Value |
|--------|-------|
| **Branch** | `member3-voice-control` |
| **Folder** | `voice_control/` |

#### Files You Own

| File | Purpose |
|------|---------|
| `voice_control/voice_listener.py` | Main module — continuously listens for the wake word "Jarvis", then records a voice command, converts speech to text, parses it for keywords, and publishes `VOICE_COMMAND` events on the EventBus |
| `voice_control/command_mappings.py` | Maps voice command keywords/phrases to system commands (e.g., `"news"` → `"show_news"`, `"stock"` → `"show_stocks"`, `"help"` → `"show_help"`) |

#### Your Responsibilities

- [ ] Implement **wake word detection** — continuously listen and react when the user says "Jarvis"
- [ ] After the wake word, **listen for a voice command** (with a timeout of 10 seconds)
- [ ] **Parse commands** using keyword matching (look for keywords like "news", "stock", "weather", "time", "help", "pause", etc.)
- [ ] Handle **speech recognition errors gracefully** — if the speech is unclear, publish a `VOICE_TIMEOUT` event and provide voice feedback like "I didn't catch that"
- [ ] Add **more command keywords and phrases** beyond the basics (e.g., "what time is it", "tell me a joke", "goodnight")
- [ ] Test with different **accents and speech speeds**
- [ ] Implement **voice feedback** — after processing, have JARVIS respond (e.g., "Pulling up the news for you, sir")

#### Skills You'll Learn

| Skill | What It Is | Why You Need It |
|-------|-----------|-----------------|
| **SpeechRecognition** | Library for converting speech to text using various engines (Google, Sphinx, Whisper) | To transcribe what the user says into text |
| **PyAudio** | Cross-platform audio I/O library | Required by SpeechRecognition to access the microphone |
| **Natural language parsing** | Extracting meaning/intent from text | To match spoken phrases to system commands |

#### Default Voice Commands

| Say This | System Command | What Happens |
|----------|---------------|-------------|
| "Jarvis, what's the news?" | `show_news` | Dashboard shows news panel |
| "Jarvis, show me stocks" | `show_stocks` | Dashboard shows stock data |
| "Jarvis, project status" | `show_project` | Dashboard shows project progress |
| "Jarvis, what time is it?" | `show_time` | JARVIS speaks the current time |
| "Jarvis, help" | `show_help` | Shows available commands |
| "Jarvis, pause" | `pause` | Pauses the assistant |
| "Jarvis, stop" | `stop` | Stops the assistant |

#### Key EventBus Events You'll Publish

```python
from ai_core.event_bus import Event, EventTypes

# When the wake word is heard
event_bus.publish(Event(EventTypes.WAKE_WORD_DETECTED, {
    "word": "jarvis"
}))

# When a voice command is parsed successfully
event_bus.publish(Event(EventTypes.VOICE_COMMAND, {
    "raw_text": "Jarvis, what's the news?",
    "command": "show_news",
    "args": {}
}))

# When listening times out or speech is unclear
event_bus.publish(Event(EventTypes.VOICE_TIMEOUT, {
    "reason": "no_speech_detected"
}))
```

#### Handling Errors Gracefully

```python
try:
    audio = recognizer.listen(source, timeout=5, phrase_time_limit=10)
    text = recognizer.recognize_google(audio)
except sr.WaitTimeoutError:
    # User didn't say anything
    publish(VOICE_TIMEOUT, {"reason": "timeout"})
except sr.UnknownValueError:
    # Speech was unclear
    publish(VOICE_TIMEOUT, {"reason": "unclear"})
    publish(SPEAK_REQUEST, {"text": "I didn't catch that. Could you repeat?"})
except sr.RequestError:
    # API error (no internet for Google Speech)
    publish(VOICE_TIMEOUT, {"reason": "api_error"})
    publish(SPEAK_REQUEST, {"text": "I'm having trouble connecting."})
```

---

### 🧑‍💻 Member 4: AI Core + Data Integration

> *"The brain behind the operation."*

| Detail | Value |
|--------|-------|
| **Branch** | `member4-ai-core` |
| **Folder** | `ai_core/` + `data_integration/` |
| **Role** | **Team Lead** — you own the central nervous system |

#### Files You Own

| File | Purpose |
|------|---------|
| `ai_core/assistant_core.py` | The brain — manages the state machine, routes commands from voice/gesture to the right handler, orchestrates all modules |
| `ai_core/event_bus.py` | The nervous system — a lightweight publish/subscribe event system that all modules use to talk to each other without direct imports *(already scaffolded — you'll enhance it)* |
| `ai_core/state_manager.py` | Manages the assistant's state machine: `IDLE → ACTIVE → LISTENING → PROCESSING` |
| `ai_core/preferences.py` | Stores and retrieves user preferences (name, news categories, greeting style) |
| `data_integration/data_manager.py` | Orchestrates all data providers and publishes data-update events on the EventBus |
| `data_integration/news_provider.py` | Fetches news from NewsAPI or RSS feeds |
| `data_integration/stock_provider.py` | Fetches stock data using the yfinance library |
| `data_integration/project_provider.py` | Reads project status from `project_status.json` |

#### Your Responsibilities

- [ ] Manage the **state machine**: IDLE → ACTIVE → LISTENING → PROCESSING (and back)
- [ ] Route **events between modules** using the EventBus — when a `GESTURE_HOLD` or `VOICE_COMMAND` event arrives, execute the corresponding action
- [ ] Implement **command execution logic** — each command (show_news, show_stocks, etc.) triggers the right data fetch and dashboard update
- [ ] Fetch **news** from NewsAPI (or RSS feeds as a fallback)
- [ ] Fetch **stock data** from yfinance (no API key needed!)
- [ ] Read **project status** from `project_status.json`
- [ ] Handle **weather and time commands** (time = just `datetime.now()`, weather = optional API)
- [ ] Implement **error recovery** — if a data fetch fails, provide a graceful fallback message
- [ ] Coordinate the team — help others understand how their modules plug into the system

#### Skills You'll Learn

| Skill | What It Is | Why You Need It |
|-------|-----------|-----------------|
| **Event-driven architecture** | Modules communicate by publishing/subscribing to events instead of calling each other directly | This is how all 5 modules talk to each other |
| **State machines** | A system that can be in exactly one of a finite number of states at any time | To manage JARVIS's current mode (idle, listening, etc.) |
| **API integration** | Connecting to external services via HTTP | To fetch news and weather data |
| **yfinance** | Library to fetch stock market data from Yahoo Finance (free, no API key!) | For the stock provider module |
| **Threading** | Running multiple things concurrently | Data fetches run in background threads so the UI stays responsive |

#### State Machine Diagram

```
                    FACE_RECOGNIZED
         IDLE ──────────────────────► ACTIVE
          │                            │  ▲
          │                            │  │
          │            WAKE_WORD_DETECTED│  │
          │                            ▼  │ PROCESSING complete
          │                         LISTENING
          │                            │
          │                 VOICE_COMMAND /
          │                 GESTURE_HOLD │
          │                            ▼
          │                        PROCESSING
          │                            │
          └──────── FACE_LOST ◄────────┘
                  (after cooldown)
```

#### Key EventBus Events You'll Subscribe To

```python
# You'll subscribe to these and route them to the right handler:
event_bus.subscribe(EventTypes.FACE_RECOGNIZED, self._on_face_recognized)
event_bus.subscribe(EventTypes.GESTURE_HOLD, self._on_gesture)
event_bus.subscribe(EventTypes.VOICE_COMMAND, self._on_voice_command)
event_bus.subscribe(EventTypes.WAKE_WORD_DETECTED, self._on_wake_word)
event_bus.subscribe(EventTypes.VOICE_TIMEOUT, self._on_voice_timeout)

# You'll publish these to trigger actions in other modules:
event_bus.publish(Event(EventTypes.SPEAK_REQUEST, {"text": "Good morning, sir!"}))
event_bus.publish(Event(EventTypes.DASHBOARD_UPDATE, {"news": articles}))
event_bus.publish(Event(EventTypes.DASHBOARD_SWITCH_PANEL, {"panel": "stocks"}))
event_bus.publish(Event(EventTypes.STATE_CHANGED, {"state": "LISTENING"}))
```

#### Data Fetching Example (Stock Provider)

```python
import yfinance as yf

def get_stock_price(symbol: str) -> dict:
    """Fetch current stock data for a given symbol."""
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.fast_info
        return {
            "symbol": symbol,
            "price": round(info.last_price, 2),
            "change": round(info.last_price - info.previous_close, 2),
        }
    except Exception as e:
        # Graceful fallback!
        return {"symbol": symbol, "error": str(e)}
```

---

### 🧑‍💻 Member 5: Dashboard + TTS

> *"The face and voice of JARVIS."*

| Detail | Value |
|--------|-------|
| **Branch** | `member5-dashboard-tts` |
| **Folder** | `dashboard/` |

#### Files You Own

| File | Purpose |
|------|---------|
| `dashboard/dashboard_tkinter.py` | Builds the JARVIS-style HUD dashboard using Tkinter — includes all panels (Welcome, News, Stocks, Project, Preferences), live clock, status indicators, and connects to the EventBus for real-time updates |
| `dashboard/tts_engine.py` | Implements text-to-speech using pyttsx3 (offline) or gTTS (online, better quality), includes a speak queue to prevent overlapping speech |

#### Your Responsibilities

- [ ] Build the **JARVIS-style HUD dashboard** with Tkinter — dark futuristic theme!
- [ ] Implement **all panels**: Welcome, News, Stocks, Project, Preferences
- [ ] Connect the dashboard to the **EventBus** for real-time updates (when news arrives, the news panel auto-updates)
- [ ] Implement **text-to-speech** with pyttsx3 (default, works offline) and gTTS (optional, better quality but needs internet)
- [ ] Add a **speak queue** so JARVIS doesn't talk over itself — queue up speech requests and play them one at a time
- [ ] Style the dashboard with a **futuristic dark theme** (dark backgrounds, cyan/green accent colors, monospace fonts)
- [ ] Add a **live clock** and **status indicators** (showing current state: IDLE, ACTIVE, LISTENING, PROCESSING)
- [ ] Handle **thread-safe UI updates** — data arrives on background threads, but Tkinter UI must be updated from the main thread

#### Skills You'll Learn

| Skill | What It Is | Why You Need It |
|-------|-----------|-----------------|
| **Tkinter** | Python's built-in GUI library | To build the dashboard with windows, panels, labels, and frames |
| **UI design** | Layout, color schemes, fonts | To make it look like a real JARVIS HUD |
| **pyttsx3** | Offline text-to-speech engine | So JARVIS can speak responses out loud |
| **gTTS** | Google Text-to-Speech (online) | Higher quality voice (optional alternative) |
| **Threading for UI** | Running UI updates safely from background threads | Data events come from other threads — you must use `.after()` to update Tkinter safely |

#### Dashboard Layout (Suggested)

```
┌──────────────────────────────────────────────────────────────┐
│  JARVIS  ·  A.I. ASSISTANT              ● ONLINE   12:34 PM │  ← Header bar
├──────────────────────┬───────────────────────────────────────┤
│                      │                                       │
│   👤 WELCOME PANEL   │         📰 NEWS PANEL                 │
│   "Good morning,     │    • Headline 1                       │
│    Yashas"           │    • Headline 2                       │
│                      │    • Headline 3                       │
│   State: ACTIVE      │    • Headline 4                       │
│                      │                                       │
├──────────────────────┼───────────────────────────────────────┤
│                      │                                       │
│   📈 STOCKS PANEL    │    📋 PROJECT PANEL                   │
│   AAPL: $189.42 ↑   │    Phase 1: ████████░░ 80%            │
│   GOOGL: $141.27 ↓  │    Phase 2: ██░░░░░░░░ 20%           │
│   MSFT: $378.91 ↑   │    Phase 3: ░░░░░░░░░░ 0%            │
│                      │                                       │
├──────────────────────┴───────────────────────────────────────┤
│  🔊 "Pulling up the news for you, sir."          [⚙ Prefs] │  ← Footer bar
└──────────────────────────────────────────────────────────────┘
```

#### Dark Theme Colors (Suggested)

| Element | Color | Hex Code |
|---------|-------|----------|
| Background | Very dark blue/black | `#0a0a1a` |
| Panel background | Dark navy | `#0d1b2a` |
| Primary accent | Cyan | `#00d4ff` |
| Secondary accent | Green | `#00ff88` |
| Warning/alert | Orange | `#ff8800` |
| Text | Light gray | `#c0c0c0` |
| Highlight text | White | `#ffffff` |

#### Thread-Safe UI Updates (CRITICAL!)

Tkinter is **NOT thread-safe**. You CANNOT update UI elements from a background thread directly. Use `.after()` instead:

```python
# ❌ WRONG — will crash or cause weird bugs
def on_news_updated(self, event):
    self.news_label.config(text=event.data["headline"])  # Called from EventBus thread!

# ✅ CORRECT — schedule the update on the main thread
def on_news_updated(self, event):
    self._root.after(0, lambda: self.news_label.config(text=event.data["headline"]))
```

#### TTS Speak Queue

```python
import queue
import threading

class TTSEngine:
    def __init__(self, config):
        self._queue = queue.Queue()
        self._engine = pyttsx3.init()
        self._running = True
        # Start a background thread that processes the queue
        self._thread = threading.Thread(target=self._process_queue, daemon=True)
        self._thread.start()

    def speak(self, text: str):
        """Add text to the speak queue (non-blocking)."""
        self._queue.put(text)

    def _process_queue(self):
        """Process the speak queue one item at a time (prevents overlap)."""
        while self._running:
            try:
                text = self._queue.get(timeout=0.5)
                self._engine.say(text)
                self._engine.runAndWait()  # Blocks until speech is done
            except queue.Empty:
                continue
```

---

## 🚀 How to Get Started

### Step 1: Install Python (if you don't have it)

```bash
# Check if Python is installed
python --version
# or
python3 --version

# You need Python 3.9 or higher.
# If not installed, download from: https://www.python.org/downloads/
# ⚠️ On Windows: Make sure to check "Add Python to PATH" during installation!
```

### Step 2: Clone the Repository

```bash
# Clone the project repo
git clone https://github.com/Yashas-K-Gangatkar/JARVISE-.git

# Go into the project folder
cd JARVISE-
```

### Step 3: Create Your Branch

Each member works on their **own branch**. NEVER commit directly to `main`!

```bash
# Replace with YOUR branch name (see your assignment above)
git checkout -b member1-face-recognition
# or: git checkout -b member2-gesture-control
# or: git checkout -b member3-voice-control
# or: git checkout -b member4-ai-core
# or: git checkout -b member5-dashboard-tts
```

### Step 4: Create a Virtual Environment

A virtual environment keeps your project dependencies separate from your system Python. **Always do this!**

```bash
# Create the virtual environment
python -m venv venv

# Activate it:

# On Windows:
venv\Scripts\activate

# On macOS/Linux:
source venv/bin/activate

# You'll know it worked when you see (venv) in your terminal prompt:
# (venv) C:\Users\you\JARVISE->
```

### Step 5: Install Dependencies

```bash
# Make sure your virtual environment is activated first!
# You should see (venv) in your prompt.

# Install ALL project dependencies
pip install -r requirements.txt

# ⚠️ If you're on Windows and PyAudio fails to install:
pip install pipwin
pipwin install pyaudio

# ⚠️ If dlib fails to install:
# You may need to install CMake first:
pip install cmake
pip install dlib
```

### Step 6: Configure the Project

```bash
# Copy the example config file
cp config.example.yaml config.yaml

# Edit config.yaml with your API keys and settings
# At minimum, you need a NewsAPI key (get one free at https://newsapi.org)
# You can use any text editor:
notepad config.yaml      # Windows
nano config.yaml         # Linux/Mac
code config.yaml         # VS Code
```

### Step 7: Test That Everything Works

```bash
# Run the main application (it should start even with empty modules)
python main.py --debug

# You should see the JARVIS banner and module initialization output
# Press Ctrl+C to quit
```

### Step 8: Start Coding! 🎉

Open the files assigned to you and start implementing. See the [Week-by-Week Schedule](#-week-by-week-schedule-8-weeks) for guidance.

---

## 🔀 Git Workflow

We follow a strict **branch → code → commit → push → pull request** workflow. This keeps the `main` branch clean and working at all times.

### The Workflow

```
1. Create your branch     →  git checkout -b member1-face-recognition
2. Write code             →  (edit your files)
3. Stage your changes     →  git add .
4. Commit with a message  →  git commit -m "Add face detection loop"
5. Push to GitHub         →  git push origin member1-face-recognition
6. Create a Pull Request  →  (on GitHub.com)
7. Code review            →  Another team member reviews your code
8. Merge to main          →  After approval, merge the PR
```

### Daily Git Commands

```bash
# START OF DAY: Get the latest changes from main
git checkout main
git pull origin main

# Switch to YOUR branch
git checkout member1-face-recognition

# Merge any new changes from main into your branch
git merge main

# AFTER MAKING CHANGES: Stage, commit, push
git add .
git commit -m "Describe what you changed"
git push origin member1-face-recognition
```

### Commit Message Convention

Write **clear, descriptive** commit messages:

```bash
# ✅ Good commit messages:
git commit -m "Add face detection loop with OpenCV"
git commit -m "Fix: handle case when no face is detected"
git commit -m "Add greeting engine with time-based messages"
git commit -m "Test: add tests for face encoder matching"

# ❌ Bad commit messages:
git commit -m "stuff"
git commit -m "fixed things"
git commit -m "asdfgh"
git commit -m "update"
```

### Creating a Pull Request (PR)

1. Push your branch to GitHub: `git push origin your-branch-name`
2. Go to the repo on GitHub: https://github.com/Yashas-K-Gangatkar/JARVISE-
3. Click the **"Compare & pull request"** button (GitHub usually shows this automatically)
4. Write a description of what you changed
5. Assign a team member to review your code
6. Wait for approval, then click **"Merge pull request"**

### Merge Conflicts (Don't Panic! 😱➡️😌)

Merge conflicts happen when two people edit the same file. Here's how to fix them:

```bash
# After running git merge main, if you see CONFLICT:
# 1. Open the conflicting file(s)
# 2. Look for markers like:
#    <<<<<<< HEAD
#    (your changes)
#    =======
#    (their changes)
#    >>>>>>> main
# 3. Keep the correct version (or combine both)
# 4. Delete the conflict markers (<<<<<<, =======, >>>>>>>)
# 5. Save the file
# 6. Stage and commit:
git add .
git commit -m "Resolve merge conflict in [filename]"
```

---

## 📅 Week-by-Week Schedule (8 Weeks)

### Week 1: 🏗️ Setup & Python Basics

**Goal**: Get your environment working and learn Python fundamentals.

| Day | Task | Everyone |
|-----|------|----------|
| Mon | Install Python, clone repo, create branch | ✅ |
| Tue | Create virtual environment, install dependencies | ✅ |
| Wed | Complete Python basics tutorial (variables, functions, loops) | ✅ |
| Thu | Complete Python tutorial (classes, imports, error handling) | ✅ |
| Fri | Read through ALL the project files — understand the structure | ✅ |

**Resources:**
- [Python for Beginners (free)](https://www.learnpython.org/)
- [Python Official Tutorial](https://docs.python.org/3/tutorial/)
- [Automate the Boring Stuff with Python (free)](https://automatetheboringstuff.com/)

### Week 2: 📚 Library Learning + Hello World Demos

**Goal**: Learn your specific libraries and create a standalone demo.

| Member | Task |
|--------|------|
| M1 | Learn OpenCV basics: open camera, show frames, save images. Learn face_recognition: detect a face, get encoding |
| M2 | Learn MediaPipe basics: detect hand landmarks, draw them on screen. Learn OpenCV: camera capture |
| M3 | Learn SpeechRecognition: record audio, convert to text. Learn PyAudio: access microphone |
| M4 | Learn EventBus pattern (read `event_bus.py` thoroughly). Learn yfinance: fetch a stock price. Learn requests: make an API call |
| M5 | Learn Tkinter: create a window, add labels, buttons, frames. Learn pyttsx3: make Python speak a sentence |

**Deliverable**: A standalone Python script that demonstrates your library working (e.g., `test_camera.py`, `test_speech.py`)

### Week 3: 🔨 Module Skeleton + Core Logic

**Goal**: Implement the core logic of your module files.

| Member | Task |
|--------|------|
| M1 | Implement `face_detection.py` — camera loop + face detection. Implement `face_encoder.py` — load/save encodings, compare faces |
| M2 | Implement `gesture_detector.py` — camera loop + hand landmark detection. Implement `gesture_mappings.py` — gesture → action mapping table |
| M3 | Implement `voice_listener.py` — wake word detection + command listening. Implement `command_mappings.py` — keyword → command mapping |
| M4 | Implement `state_manager.py` — state machine. Enhance `event_bus.py` if needed. Implement `assistant_core.py` skeleton — subscribe to events |
| M5 | Implement `tts_engine.py` — pyttsx3 with speak queue. Implement `dashboard_tkinter.py` skeleton — main window + header + one panel |

**Deliverable**: Your module files have working core logic (even if not fully integrated)

### Week 4: 🔗 EventBus Integration

**Goal**: Connect your module to the EventBus so modules can talk to each other.

| Member | Task |
|--------|------|
| M1 | Publish `FACE_DETECTED`, `FACE_RECOGNIZED`, `FACE_LOST` events. Implement `greeting_engine.py` |
| M2 | Publish `GESTURE_DETECTED`, `GESTURE_HOLD` events. Implement hold-duration timer |
| M3 | Publish `WAKE_WORD_DETECTED`, `VOICE_COMMAND`, `VOICE_TIMEOUT` events |
| M4 | Subscribe to ALL events in `assistant_core.py`. Route commands to actions. Implement data providers |
| M5 | Subscribe to `DASHBOARD_UPDATE`, `STATE_CHANGED`. Implement thread-safe UI updates. Subscribe `SPEAK_REQUEST` in TTS |

**Deliverable**: Modules can communicate through the EventBus. Run `python main.py` and see events flowing!

### Week 5: 🧪 Testing & Bug Fixing

**Goal**: Test your module thoroughly and fix bugs.

| Member | Task |
|--------|------|
| M1 | Test face detection in different lighting. Test with 3+ people. Test `register_face.py` with camera + image |
| M2 | Test all gestures. Test hold duration. Test with different hand sizes. Add visual overlay for debugging |
| M3 | Test with different accents/speeds. Test error handling (no mic, no internet). Add voice feedback for errors |
| M4 | Test all data providers. Test error recovery (no API key, no internet). Test state transitions |
| M5 | Test all dashboard panels. Test TTS with long text. Test speak queue (no overlap). Test thread safety |

**Deliverable**: All module tests passing. Bug list documented and resolved.

### Week 6: 🔧 Integration + Polish

**Goal**: Make all modules work together seamlessly.

| Member | Task |
|--------|------|
| M1 | Polish greeting messages. Add support for `preferences.greeting_style`. Fine-tune recognition tolerance |
| M2 | Add 2-3 new gestures beyond the basics. Polish visual overlay. Fine-tune hold duration sensitivity |
| M3 | Add 5+ new voice commands. Improve keyword matching. Polish voice feedback messages |
| M4 | Complete `assistant_core.py` command routing. Add weather command. Polish all data providers. Add caching |
| M5 | Polish dashboard theme (dark futuristic). Add animations/transitions. Add live clock. Add status bar |

**Deliverable**: The full JARVIS system running smoothly with `python main.py`

### Week 7: 📖 Documentation & Final Testing

**Goal**: Document everything and do final integration testing.

| Member | Task |
|--------|------|
| M1 | Add docstrings and comments to all your files. Write a `HOW_IT_WORKS.md` for your module |
| M2 | Add docstrings and comments. Document gesture detection algorithm. Write a `HOW_IT_WORKS.md` |
| M3 | Add docstrings and comments. Document voice command system. Write a `HOW_IT_WORKS.md` |
| M4 | Add docstrings and comments. Document state machine and event flow. Update `project_status.json` to 100% |
| M5 | Add docstrings and comments. Document dashboard layout and TTS system. Write a `HOW_IT_WORKS.md` |

**Team**: Full integration test — everyone runs the complete system together and logs issues

### Week 8: 🎤 Presentation & Demo

**Goal**: Present JARVIS to the world!

| Day | Task |
|-----|------|
| Mon | Final bug fixes and polish |
| Tue | Rehearse the demo — run through every feature |
| Wed | Prepare presentation slides (5 minutes per member explaining their module) |
| Thu | 🎤 **DEMO DAY** — Live presentation of JARVIS-AI |
| Fri | Celebrate! 🎉 You built an AI assistant from scratch! |

---

## ✅ Testing Checklist

### Member 1: Face Recognition

- [ ] Camera opens and shows live video feed
- [ ] A face is detected when someone looks at the camera
- [ ] Face is highlighted with a bounding box in debug mode
- [ ] A registered face is recognized by name
- [ ] An unregistered face is flagged as "Unknown"
- [ ] Greeting is generated based on time of day (morning/afternoon/evening)
- [ ] Greeting includes the person's name
- [ ] Greeting doesn't repeat within the cooldown period (5 minutes)
- [ ] `register_face.py --name "Test" --image photo.jpg` works
- [ ] `register_face.py --name "Test" --camera` works
- [ ] Face encodings are saved to `known_faces/` directory
- [ ] Multiple faces in frame are handled
- [ ] Different lighting conditions (bright, dim, backlit) work
- [ ] `FACE_RECOGNIZED` event is published on the EventBus
- [ ] `FACE_LOST` event is published when no face is detected

### Member 2: Gesture Control

- [ ] Camera opens and shows live video feed
- [ ] Hand landmarks are detected and drawn on screen in debug mode
- [ ] Open palm gesture is correctly classified
- [ ] Thumbs up gesture is correctly classified
- [ ] Thumbs down gesture is correctly classified
- [ ] Victory sign gesture is correctly classified
- [ ] Point (index finger) gesture is correctly classified
- [ ] Fist gesture is correctly classified
- [ ] Hold duration works — gesture must be held for 0.5 seconds
- [ ] Brief/accidental gestures are ignored
- [ ] Each gesture maps to the correct action in `gesture_mappings.py`
- [ ] Visual overlay shows the detected gesture name on screen
- [ ] `GESTURE_DETECTED` event is published for any detected gesture
- [ ] `GESTURE_HOLD` event is published only after hold duration
- [ ] At least 2 additional gestures beyond the 6 basic ones work
- [ ] Works with different hand sizes (small/large hands)
- [ ] Works with either left or right hand

### Member 3: Voice Control

- [ ] Microphone access works without errors
- [ ] Wake word "Jarvis" is detected reliably
- [ ] After wake word, system listens for a command
- [ ] "What's the news?" is recognized and parsed as `show_news`
- [ ] "Show me stocks" is recognized and parsed as `show_stocks`
- [ ] "Project status" is recognized and parsed as `show_project`
- [ ] "What time is it?" is recognized and parsed as `show_time`
- [ ] "Help" is recognized and parsed as `show_help`
- [ ] "Pause" is recognized and parsed as `pause`
- [ ] Unclear speech triggers "I didn't catch that" feedback
- [ ] Timeout after 10 seconds of silence is handled gracefully
- [ ] `WAKE_WORD_DETECTED` event is published
- [ ] `VOICE_COMMAND` event is published with `raw_text` and `command`
- [ ] `VOICE_TIMEOUT` event is published on timeout/error
- [ ] At least 5 additional voice commands work
- [ ] Different accents and speech speeds are handled reasonably
- [ ] System works with background noise (to some extent)

### Member 4: AI Core + Data Integration

- [ ] EventBus `subscribe()` and `publish()` work correctly
- [ ] State machine transitions: IDLE → ACTIVE on `FACE_RECOGNIZED`
- [ ] State machine transitions: ACTIVE → LISTENING on `WAKE_WORD_DETECTED`
- [ ] State machine transitions: LISTENING → PROCESSING on `VOICE_COMMAND`
- [ ] State machine transitions: PROCESSING → ACTIVE on completion
- [ ] `GESTURE_HOLD` events are routed to the correct action
- [ ] `VOICE_COMMAND` events are routed to the correct action
- [ ] News is fetched from NewsAPI (with API key) or RSS feeds (fallback)
- [ ] Stock data is fetched from yfinance for configured symbols
- [ ] Project status is read from `project_status.json`
- [ ] Time command returns current time
- [ ] Failed API calls have graceful fallback messages
- [ ] Data is cached for the configured duration (30 min default)
- [ ] `SPEAK_REQUEST` events are published for voice feedback
- [ ] `DASHBOARD_UPDATE` events are published with fetched data
- [ ] `STATE_CHANGED` events are published on state transitions
- [ ] Multiple rapid events are handled without crashing
- [ ] Thread safety — no race conditions in event processing

### Member 5: Dashboard + TTS

- [ ] Dashboard window opens with a dark futuristic theme
- [ ] Welcome panel shows greeting message and current state
- [ ] News panel updates when `DASHBOARD_UPDATE` with news data arrives
- [ ] Stocks panel updates when `DASHBOARD_UPDATE` with stock data arrives
- [ ] Project panel shows progress bars for each milestone
- [ ] Live clock updates every second
- [ ] Status indicator shows current state (IDLE, ACTIVE, LISTENING, PROCESSING)
- [ ] Panel switching works (via gesture or voice command)
- [ ] TTS speaks text when `SPEAK_REQUEST` event arrives
- [ ] Speak queue prevents overlapping speech
- [ ] Dashboard updates are thread-safe (no crashes from background thread updates)
- [ ] Dashboard closes gracefully (triggers system shutdown)
- [ ] Preferences panel allows viewing/editing user preferences
- [ ] All text is readable (good contrast against dark background)
- [ ] Dashboard responds correctly to `DASHBOARD_SWITCH_PANEL` events

---

## 🔄 How Modules Communicate (EventBus)

### The Big Picture

Instead of modules calling each other directly (which creates a tangled mess), they communicate through a **central EventBus**. Think of it like a group chat:

- **Publish**: A module sends a message to the group chat (an event)
- **Subscribe**: A module listens for certain types of messages (subscribes to event types)

```
┌──────────────────┐     publish      ┌─────────────┐     notify      ┌──────────────────┐
│  Face Recognition │ ──────────────► │             │ ──────────────► │  Assistant Core   │
│  (Member 1)       │                 │             │                 │  (Member 4)       │
└──────────────────┘                 │   EVENTBUS  │                 └──────────────────┘
                                     │             │
┌──────────────────┐     publish      │             │     notify      ┌──────────────────┐
│  Gesture Control  │ ──────────────► │             │ ──────────────► │  Dashboard + TTS  │
│  (Member 2)       │                 │             │                 │  (Member 5)       │
└──────────────────┘                 │             │                 └──────────────────┘
                                     │             │
┌──────────────────┐     publish      │             │
│  Voice Control    │ ──────────────► │             │
│  (Member 3)       │                 └─────────────┘
└──────────────────┘
```

### How It Works (Code Level)

Every module receives the `EventBus` instance in its `__init__` method:

```python
class FaceDetectionModule:
    def __init__(self, event_bus, config):
        self.event_bus = event_bus
        self.config = config

        # Subscribe to events you care about
        from ai_core.event_bus import EventTypes
        self.event_bus.subscribe(EventTypes.SYSTEM_START, self._on_system_start)

    def _on_system_start(self, event):
        """Called when the system starts up."""
        print("System started! Beginning face detection...")

    def detect_face(self):
        # ... face detection logic ...
        # Publish an event when a face is recognized
        from ai_core.event_bus import Event, EventTypes
        self.event_bus.publish(Event(EventTypes.FACE_RECOGNIZED, {
            "name": "Yashas",
            "greeting": "Good morning, Yashas"
        }))
```

### All Event Types

Here are ALL the events in the system and who publishes/subscribes to them:

| Event Type | Published By | Subscribed By | Data |
|-----------|-------------|--------------|------|
| `FACE_DETECTED` | Member 1 | Member 4 | `{unknown: bool}` |
| `FACE_RECOGNIZED` | Member 1 | Member 4, Member 5 | `{name: str, greeting: str}` |
| `FACE_LOST` | Member 1 | Member 4 | `{}` |
| `GESTURE_DETECTED` | Member 2 | Member 4 | `{gesture: str, confidence: float}` |
| `GESTURE_HOLD` | Member 2 | Member 4 | `{gesture: str, action: str}` |
| `WAKE_WORD_DETECTED` | Member 3 | Member 4 | `{word: str}` |
| `VOICE_COMMAND` | Member 3 | Member 4 | `{raw_text: str, command: str, args: dict}` |
| `VOICE_TIMEOUT` | Member 3 | Member 4 | `{reason: str}` |
| `SYSTEM_START` | main.py | All modules | `{}` |
| `SYSTEM_STOP` | main.py | All modules | `{}` |
| `STATE_CHANGED` | Member 4 | Member 5 | `{state: str}` |
| `NEWS_UPDATED` | Member 4 | Member 5 | `{articles: list}` |
| `STOCKS_UPDATED` | Member 4 | Member 5 | `{stocks: list}` |
| `PROJECT_UPDATED` | Member 4 | Member 5 | `{project: dict}` |
| `SPEAK_REQUEST` | Member 4 | Member 5 | `{text: str}` |
| `DASHBOARD_UPDATE` | Member 4 | Member 5 | `{...various data...}` |
| `DASHBOARD_SWITCH_PANEL` | Member 4 | Member 5 | `{panel: str}` |

### Event Flow Example: "Jarvis, what's the news?"

```
1. 👤 User says "Jarvis, what's the news?"
         │
2. 🎙️ Member 3 (Voice) detects wake word
         │  publishes WAKE_WORD_DETECTED
         ▼
3. 🧠 Member 4 (Core) changes state → LISTENING
         │  publishes STATE_CHANGED
         ▼
4. 🎙️ Member 3 (Voice) transcribes "what's the news"
         │  parses command → "show_news"
         │  publishes VOICE_COMMAND {command: "show_news"}
         ▼
5. 🧠 Member 4 (Core) changes state → PROCESSING
         │  publishes STATE_CHANGED
         │  calls news_provider to fetch news
         ▼
6. 📡 Member 4 (Data) fetches news articles
         │  publishes NEWS_UPDATED {articles: [...]}
         │  publishes SPEAK_REQUEST {text: "Here are the latest headlines, sir."}
         ▼
7. 📺 Member 5 (Dashboard) updates news panel
   🔊 Member 5 (TTS) speaks the response
         │
8. 🧠 Member 4 (Core) changes state → ACTIVE
         │  publishes STATE_CHANGED
         ▼
9. 📺 Member 5 (Dashboard) updates status indicator → ACTIVE
```

### How to Use the EventBus in Your Module

```python
# 1. Import what you need
from ai_core.event_bus import Event, EventTypes

# 2. Subscribe to events you care about (in __init__)
self.event_bus.subscribe(EventTypes.SYSTEM_START, self._on_start)
self.event_bus.subscribe(EventTypes.FACE_RECOGNIZED, self._on_face)

# 3. Define your handler functions
def _on_start(self, event):
    """Called when SYSTEM_START event is published."""
    print("JARVIS is starting!")
    self.start_detection()

def _on_face(self, event):
    """Called when FACE_RECOGNIZED event is published."""
    name = event.data.get("name", "Unknown")
    print(f"Welcome back, {name}!")

# 4. Publish your own events
self.event_bus.publish(Event(EventTypes.GESTURE_HOLD, {
    "gesture": "open_palm",
    "action": "pause"
}))
```

---

## 💻 Common Commands & How to Run Them

### Running JARVIS

```bash
# Make sure your virtual environment is activated first!
source venv/bin/activate    # macOS/Linux
venv\Scripts\activate       # Windows

# Run with all modules
python main.py

# Run with debug logging (see everything that happens)
python main.py --debug

# Run without camera (no face/gesture detection)
python main.py --no-camera

# Run without voice control
python main.py --no-voice

# Run without the dashboard (headless mode)
python main.py --no-dashboard

# Combine flags
python main.py --no-camera --no-voice --debug

# Use a custom config file
python main.py --config my_config.yaml
```

### Registering a Face

```bash
# Register from an image file
python register_face.py --name "Yashas" --image photos/yashas.jpg

# Register using the camera (it will take a photo)
python register_face.py --name "Yashas" --camera

# Face encodings are saved in the known_faces/ directory
```

### Running Tests

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run tests for a specific module
pytest tests/test_face_recognition.py -v
pytest tests/test_gesture_control.py -v
pytest tests/test_voice_control.py -v
pytest tests/test_ai_core.py -v
pytest tests/test_dashboard.py -v
```

### Git Commands Quick Reference

```bash
# Check current status
git status

# See what changed
git diff

# Stage all changes
git add .

# Stage a specific file
git add face_recognition/face_detection.py

# Commit staged changes
git commit -m "Add face detection with OpenCV"

# Push your branch to GitHub
git push origin member1-face-recognition

# Pull latest changes from main
git pull origin main

# Switch branches
git checkout main
git checkout member1-face-recognition

# See all branches
git branch -a

# Create a new branch from current branch
git checkout -b my-new-branch
```

### Python Commands Quick Reference

```bash
# Install a single package
pip install opencv-python

# Install all project dependencies
pip install -r requirements.txt

# See installed packages
pip list

# Check which package version is installed
pip show opencv-python

# Run a single Python file
python face_recognition/face_detection.py

# Run Python interactively (test commands one at a time)
python
>>> import cv2
>>> print(cv2.__version__)
>>> exit()
```

### Useful Debug Commands

```bash
# Test if your camera works
python -c "import cv2; cap = cv2.VideoCapture(0); print('Camera works!' if cap.isOpened() else 'Camera failed'); cap.release()"

# Test if face_recognition is installed
python -c "import face_recognition; print('face_recognition version:', face_recognition.__version__)"

# Test if MediaPipe is installed
python -c "import mediapipe; print('MediaPipe version:', mediapipe.__version__)"

# Test if SpeechRecognition is installed
python -c "import speech_recognition; print('SpeechRecognition works!')"

# Test if pyttsx3 works
python -c "import pyttsx3; engine = pyttsx3.init(); engine.say('JARVIS online'); engine.runAndWait()"

# Test if yfinance works
python -c "import yfinance as yf; print(yf.Ticker('AAPL').fast_info.last_price)"

# Test if Tkinter works
python -c "import tkinter as tk; root = tk.Tk(); root.title('Test'); root.mainloop()"
```

---

## 🎯 Quick Start Checklist (Do This Today!)

Print this out or copy it somewhere. Do each item one by one:

- [ ] **Install Python 3.9+** — [python.org/downloads](https://www.python.org/downloads/)
- [ ] **Clone the repo** — `git clone https://github.com/Yashas-K-Gangatkar/JARVISE-.git`
- [ ] **Create your branch** — `git checkout -b your-branch-name`
- [ ] **Create virtual environment** — `python -m venv venv`
- [ ] **Activate virtual environment** — `source venv/bin/activate` or `venv\Scripts\activate`
- [ ] **Install dependencies** — `pip install -r requirements.txt`
- [ ] **Copy config** — `cp config.example.yaml config.yaml`
- [ ] **Run JARVIS** — `python main.py --debug`
- [ ] **Read your module files** — Open every file you're responsible for and read it top to bottom
- [ ] **Create your first commit** — Add a comment to one of your files, commit, and push

---

## 💪 Final Words of Encouragement

Look — if you've never coded before, this project might feel overwhelming. **That's completely normal.** Every expert was once a beginner who felt exactly the same way.

Here's the secret: **you don't need to understand everything to make progress.** Start small:

1. **Week 1**: Just get Python running and print "Hello, World!"
2. **Week 2**: Get your library's basic demo working
3. **Week 3**: Start filling in your module files
4. **Week 4**: Connect to the EventBus
5. **Week 5-8**: Polish, test, and integrate

You're building **freaking JARVIS**. An AI assistant that sees your face, hears your voice, understands your gestures, and talks back to you. That's incredible. Most people never build something this cool in their entire lives.

So don't stress about being perfect. Stress about **making progress every day.** Even 30 minutes a day adds up to 28 hours over 8 weeks. That's enough to build something amazing.

**Now go build JARVIS. 🚀**

---

*Last updated: 2026-06-06 | Repo: https://github.com/Yashas-K-Gangatkar/JARVISE-*
