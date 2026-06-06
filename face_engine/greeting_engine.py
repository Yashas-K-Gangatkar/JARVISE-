"""
Greeting Engine - Generates time-appropriate greeting messages.
"""

from datetime import datetime


class GreetingEngine:
    """
    Generates personalized greeting messages based on time of day
    and user preferences.
    """

    FORMAL_TEMPLATES = {
        "morning": "Good Morning, {name}! How may I assist you today?",
        "afternoon": "Good Afternoon, {name}! How may I help you?",
        "evening": "Good Evening, {name}! How can I assist you?",
    }

    CASUAL_TEMPLATES = {
        "morning": "Hey {name}! Morning! What's up?",
        "afternoon": "Hey {name}! Afternoon! What can I do for you?",
        "evening": "Hey {name}! Evening! What's happening?",
    }

    def __init__(self, style="formal"):
        self.style = style

    def get_greeting(self, name="User"):
        """
        Generate a greeting message based on current time and style.

        Args:
            name: The user's name

        Returns:
            str: Personalized greeting message
        """
        time_of_day = self._get_time_of_day()

        if self.style == "formal":
            template = self.FORMAL_TEMPLATES.get(time_of_day)
        else:
            template = self.CASUAL_TEMPLATES.get(time_of_day)

        return template.format(name=name)

    def _get_time_of_day(self):
        """Determine the current time of day."""
        hour = datetime.now().hour
        if hour < 12:
            return "morning"
        elif hour < 17:
            return "afternoon"
        else:
            return "evening"

    def get_date_summary(self):
        """Get a spoken summary of today's date."""
        now = datetime.now()
        return now.strftime("Today is %A, %B %d, %Y.")
