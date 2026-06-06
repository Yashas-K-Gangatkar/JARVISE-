"""
Command Mappings - Maps voice keywords to system commands.

Modify this file to customize which voice commands trigger which actions.
"""

# Keyword to command mapping
# Each command maps to a list of trigger keywords/phrases
COMMAND_KEYWORDS = {
    "news": [
        "news",
        "headlines",
        "what's the news",
        "today's news",
        "latest news",
        "show news",
    ],
    "stocks": [
        "stocks",
        "stock market",
        "market",
        "share price",
        "stock price",
        "show stocks",
        "market update",
    ],
    "project": [
        "project",
        "progress",
        "status",
        "milestone",
        "next steps",
        "project status",
        "what's the progress",
    ],
    "hello": [
        "hello",
        "hi",
        "hey",
        "good morning",
        "good afternoon",
        "good evening",
    ],
    "help": [
        "help",
        "what can you do",
        "commands",
        "options",
    ],
    "stop": [
        "stop",
        "exit",
        "quit",
        "goodbye",
        "bye",
        "shut down",
    ],
    "time": [
        "time",
        "what time",
        "current time",
        "what's the time",
        "tell me the time",
    ],
    "weather": [
        "weather",
        "temperature",
        "forecast",
        "how's the weather",
        "what's the weather",
    ],
    "date": [
        "date",
        "what's the date",
        "today's date",
        "what day",
        "what's today",
    ],
    "open": [
        "open",
        "launch",
        "start app",
        "run",
        "open app",
    ],
    "chat": [
        "chat",
        "ask",
        "talk",
        "question",
        "i want to ask",
        "can you tell me about",
        "explain",
        "what do you think",
        "opinion",
    ],
    "remind": [
        "remind",
        "reminder",
        "remember",
        "remind me",
        "set a reminder",
        "add a reminder",
    ],
    "timer": [
        "timer",
        "set a timer",
        "set timer",
        "countdown",
    ],
    "briefing": [
        "briefing",
        "brief me",
        "morning report",
        "daily briefing",
        "give me a briefing",
        "morning briefing",
    ],
    "show_reminders": [
        "my reminders",
        "show reminders",
        "show my reminders",
        "list reminders",
        "what are my reminders",
        "any reminders",
    ],
    "clear_reminders": [
        "clear reminders",
        "clear all reminders",
        "delete all reminders",
        "remove all reminders",
    ],
    "cancel_reminder": [
        "cancel reminder",
        "remove reminder",
        "delete reminder",
    ],
    "schedule": [
        "schedule",
        "my schedule",
        "today's schedule",
        "what's my schedule",
        "what's on today",
        "what's on my schedule",
    ],
}


def get_command_for_text(text):
    """
    Find the matching command for a voice text input.

    Args:
        text: Recognized speech text (lowercase)

    Returns:
        tuple: (command_name, params) or ("unknown", {})
    """
    text_lower = text.lower()

    for command, keywords in COMMAND_KEYWORDS.items():
        for keyword in keywords:
            if keyword in text_lower:
                return command, {"keyword_matched": keyword}

    return "unknown", {}


def get_all_commands():
    """Return all supported commands and their trigger keywords."""
    return dict(COMMAND_KEYWORDS)
