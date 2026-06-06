"""
Email & Calendar Module - Main integration module for JARVIS AI Assistant.

Combines the email client (IMAP/SMTP) and calendar client (local JSON)
into a unified module with:
- Voice command handling via EventBus
- Demo/offline mode with sample emails
- Security masking for sensitive content
- Gmail setup guidance
- Calendar reminders that publish SPEAK_REQUEST events
"""

import re
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from .calendar_client import CalendarClient, CalendarEvent
from .email_client import EmailClient, EmailMessage


# ---------------------------------------------------------------------------
# Default configuration fallback
# ---------------------------------------------------------------------------

_DEFAULT_EMAIL_CALENDAR_CONFIG = {
    "email_enabled": False,
    "calendar_enabled": True,
    "email": {
        "provider": "gmail",
        "address": "",
        "app_password": "",
        "imap_server": "imap.gmail.com",
        "smtp_server": "smtp.gmail.com",
        "smtp_port": 587,
    },
    "calendar": {
        "type": "local",
        "data_file": "calendar_events.json",
        "reminder_minutes_before": 15,
        "default_event_duration_minutes": 60,
    },
    "demo": {
        "sample_emails": [
            {
                "from": "professor@university.edu",
                "subject": "Project Review Meeting",
                "body": "Hi, your project review is scheduled for next Monday at 10 AM. Please prepare your presentation and bring the latest progress report.",
            },
            {
                "from": "team@project.com",
                "subject": "Sprint Update",
                "body": "Great progress this week! Let's discuss next steps in our Friday standup.",
            },
            {
                "from": "hr@company.com",
                "subject": "Benefits Enrollment Reminder",
                "body": "This is a friendly reminder that the open enrollment period ends this Friday. Please review and update your selections.",
            },
            {
                "from": "noreply@github.com",
                "subject": "Pull Request Merged",
                "body": "Your pull request #42 has been merged into the main branch. Great work!",
            },
            {
                "from": "friend@email.com",
                "subject": "Weekend Plans",
                "body": "Hey! Are you free this Saturday? We're thinking of going hiking in the morning.",
            },
        ],
    },
}


# ---------------------------------------------------------------------------
# Date/time parsing helpers
# ---------------------------------------------------------------------------

_RELATIVE_DAY_MAP = {
    "today": 0,
    "tonight": 0,
    "tomorrow": 1,
    "day after tomorrow": 2,
    "the day after tomorrow": 2,
}


def _parse_relative_day(text: str) -> Optional[str]:
    """
    Parse a relative day reference from text into a YYYY-MM-DD string.

    Supports: today, tomorrow, day after tomorrow.
    """
    text_lower = text.lower().strip()
    for phrase, offset in _RELATIVE_DAY_MAP.items():
        if phrase in text_lower:
            target = datetime.now().date() + timedelta(days=offset)
            return target.isoformat()
    return None


def _parse_time_from_text(text: str) -> Optional[int]:
    """
    Extract an hour (0-23) from natural language text.

    Supports: "3pm", "3 pm", "15:00", "3 in the afternoon", "noon", "midnight".
    """
    text_lower = text.lower()

    # Special keywords
    if "noon" in text_lower:
        return 12
    if "midnight" in text_lower:
        return 0

    # "at 3pm" / "at 3 pm" / "at 3 in the afternoon"
    m = re.search(r"(?:at\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm|a\.m\.|p\.m\.)?", text_lower)
    if m:
        hour = int(m.group(1))
        minute = int(m.group(2)) if m.group(2) else 0
        ampm = m.group(3)

        if ampm and "p" in ampm and hour != 12:
            hour += 12
        elif ampm and "a" in ampm and hour == 12:
            hour = 0
        elif not ampm:
            # No AM/PM — infer from context
            if "afternoon" in text_lower or "evening" in text_lower or "night" in text_lower:
                if hour < 12:
                    hour += 12
            elif "morning" in text_lower and hour >= 12:
                hour -= 12

        # Only return if this looks like a valid time (1-12 with am/pm, or 0-23)
        if ampm or (0 <= hour <= 23):
            return hour

    # Try 24h format "15:00"
    m = re.search(r"(\d{1,2}):(\d{2})", text_lower)
    if m:
        return int(m.group(1))

    return None


def _parse_minute_from_text(text: str) -> int:
    """Extract the minute component from time text, if present."""
    m = re.search(r"(?:at\s+)?\d{1,2}:(\d{2})", text.lower())
    if m:
        return int(m.group(1))
    m = re.search(r"(\d{1,2}):(\d{2})", text.lower())
    if m:
        return int(m.group(2))
    return 0


# ---------------------------------------------------------------------------
# Voice command parser
# ---------------------------------------------------------------------------

def _parse_send_email_command(text: str) -> Optional[Dict]:
    """
    Parse a "send email to X saying Y" command.

    Returns dict with 'to' and 'body' keys, or None.
    """
    # "send email to John saying Hello there"
    m = re.search(
        r"send\s+(?:an?\s+)?email\s+to\s+(.+?)\s+saying\s+(.+)",
        text,
        re.IGNORECASE,
    )
    if m:
        return {"to": m.group(1).strip(), "body": m.group(2).strip()}
    return None


def _parse_reply_command(text: str) -> Optional[Dict]:
    """
    Parse a "reply to email N saying X" command.

    Returns dict with 'email_number' and 'body' keys, or None.
    """
    m = re.search(
        r"reply\s+to\s+(?:email\s+)?(?:number\s+)?(\d+)\s+saying\s+(.+)",
        text,
        re.IGNORECASE,
    )
    if m:
        return {"email_number": int(m.group(1)), "body": m.group(2).strip()}
    return None


def _parse_add_event_command(text: str) -> Optional[Dict]:
    """
    Parse an "add event/meeting X at Y" command.

    Returns dict with 'title', 'date', 'hour', 'minute' keys, or None.
    """
    # "add meeting with team tomorrow at 3pm"
    # "add event lunch with Sarah on Friday at noon"
    # "schedule appointment with doctor on Monday at 10am"
    m = re.search(
        r"(?:add|create|schedule)\s+(?:an?\s+)?(.+)",
        text,
        re.IGNORECASE,
    )
    if not m:
        return None

    title = m.group(1).strip()
    # Remove the generic "event" prefix if present (keep "meeting"/"appointment" as part of title)
    title = re.sub(r"^event\s+", "", title, flags=re.IGNORECASE)
    # Remove time references from the title (e.g. "at 3pm", "at noon", "at midnight")
    title = re.sub(r"\s*(?:at\s+)?\d{1,2}(?::\d{2})?\s*(?:am|pm|a\.m\.|p\.m\.)?", "", title, flags=re.IGNORECASE)
    title = re.sub(r"\s+at\s+(?:noon|midnight)\b", "", title, flags=re.IGNORECASE)
    # Remove day references from the title
    title = re.sub(r"\s+(?:tomorrow|today|tonight|day after tomorrow)\b", "", title, flags=re.IGNORECASE)
    title = re.sub(r"\s+on\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b", "", title, flags=re.IGNORECASE)
    # Clean trailing prepositions
    title = re.sub(r"\s+(on|at|for|from)\s+$", "", title)
    title = title.strip()

    date_str = _parse_relative_day(text)
    if date_str is None:
        # Try to find day-of-week reference
        days_of_week = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        now = datetime.now()
        for i, day in enumerate(days_of_week):
            if day in text.lower():
                target = now + timedelta(days=(i - now.weekday() + 7) % 7)
                if target.date() <= now.date():
                    target += timedelta(weeks=1)
                date_str = target.date().isoformat()
                break

    if date_str is None:
        date_str = datetime.now().date().isoformat()

    hour = _parse_time_from_text(text)
    if hour is None:
        hour = 9  # default to 9 AM if no time specified
    minute = _parse_minute_from_text(text)

    return {
        "title": title,
        "date": date_str,
        "hour": hour,
        "minute": minute,
    }


def _parse_delete_event_command(text: str) -> Optional[Dict]:
    """
    Parse a "cancel/delete event X at Y" command.

    Returns dict with 'keyword' and optionally 'hour', or None.
    """
    m = re.search(
        r"(?:cancel|delete|remove)\s+(?:my\s+)?(?:event|meeting|appointment)?\s*(.+)",
        text,
        re.IGNORECASE,
    )
    if m:
        keyword = m.group(1).strip()
        hour = _parse_time_from_text(text)
        return {"keyword": keyword, "hour": hour}
    return None


# ---------------------------------------------------------------------------
# Main Module
# ---------------------------------------------------------------------------

class EmailCalendarModule:
    """
    Combined Email & Calendar module for JARVIS AI Assistant.

    Integrates with the EventBus for voice command handling,
    publishes SPEAK_REQUEST for verbal responses, and
    DASHBOARD_UPDATE for visual display.
    """

    def __init__(self, event_bus, config: dict):
        """
        Initialise the Email & Calendar module.

        Args:
            event_bus: The system EventBus instance.
            config: Full application configuration dict.
        """
        self.event_bus = event_bus
        self.config = config

        # Module-specific config (with defaults)
        ec_config = config.get("email_calendar", _DEFAULT_EMAIL_CALENDAR_CONFIG)
        self.email_enabled = ec_config.get("email_enabled", False)
        self.calendar_enabled = ec_config.get("calendar_enabled", True)

        # ── Email client ──────────────────────────────────────────
        email_config = ec_config.get("email", _DEFAULT_EMAIL_CALENDAR_CONFIG["email"])
        self.email_client = EmailClient(email_config)
        self._cached_emails: List[EmailMessage] = []  # for "read email number N"
        self._demo_mode = not self.email_client.is_configured

        # ── Calendar client ───────────────────────────────────────
        cal_config = ec_config.get("calendar", _DEFAULT_EMAIL_CALENDAR_CONFIG["calendar"])
        self.calendar_client = CalendarClient(
            cal_config,
            reminder_callback=self._on_calendar_reminder,
        )

        # ── Demo emails ──────────────────────────────────────────
        demo_config = ec_config.get("demo", _DEFAULT_EMAIL_CALENDAR_CONFIG["demo"])
        self._demo_emails: List[EmailMessage] = self._build_demo_emails(
            demo_config.get("sample_emails", [])
        )

        # ── Running state ────────────────────────────────────────
        self._running = False
        self._lock = threading.Lock()

        # ── Subscribe to EventBus ────────────────────────────────
        from ai_core.event_bus import EventTypes

        self.event_bus.subscribe(
            EventTypes.VOICE_COMMAND, self._on_voice_command
        )
        print("[EmailCalendar] Subscribed to VOICE_COMMAND")

    # ── Lifecycle ─────────────────────────────────────────────────

    def start(self):
        """Start the module."""
        self._running = True

        if self.calendar_enabled:
            self.calendar_client.start()

        print(
            f"[EmailCalendar] Started "
            f"(email={'demo' if self._demo_mode else 'live'}, "
            f"calendar={'enabled' if self.calendar_enabled else 'disabled'})"
        )

    def stop(self):
        """Stop the module."""
        self._running = False

        # Disconnect email
        if not self._demo_mode:
            self.email_client.disconnect_imap()

        # Stop calendar
        if self.calendar_enabled:
            self.calendar_client.stop()

        print("[EmailCalendar] Stopped")

    # ── Demo mode helpers ─────────────────────────────────────────

    def _build_demo_emails(self, sample_list: List[Dict]) -> List[EmailMessage]:
        """Build demo EmailMessage objects from config sample data."""
        messages = []
        for i, sample in enumerate(sample_list):
            msg = EmailMessage(
                uid=f"demo-{i+1}",
                sender=sample.get("from", "unknown@example.com"),
                sender_email=sample.get("from", "unknown@example.com"),
                subject=sample.get("subject", "No Subject"),
                body=sample.get("body", ""),
                date=datetime.now().strftime("%a, %d %b %Y %H:%M:%S"),
                is_unread=True,
            )
            messages.append(msg)
        return messages

    # ── Email operations ──────────────────────────────────────────

    def read_emails(self, count: int = 5) -> List[EmailMessage]:
        """
        Read the latest emails.

        In demo mode, returns sample emails. In live mode, fetches
        from the IMAP server.

        Args:
            count: Maximum number of emails to read.

        Returns:
            List of EmailMessage objects.
        """
        if self._demo_mode:
            emails = self._demo_emails[:count]
            with self._lock:
                self._cached_emails = emails
            return emails

        try:
            emails = self.email_client.fetch_latest(count)
            with self._lock:
                self._cached_emails = emails
            return emails
        except Exception as exc:
            print(f"[EmailCalendar] read_emails error: {exc}")
            return []

    def read_unread_emails(self, count: int = 5) -> List[EmailMessage]:
        """Read only unread emails."""
        if self._demo_mode:
            emails = self._demo_emails[:count]
            with self._lock:
                self._cached_emails = emails
            return emails

        try:
            emails = self.email_client.fetch_unread(count)
            with self._lock:
                self._cached_emails = emails
            return emails
        except Exception as exc:
            print(f"[EmailCalendar] read_unread_emails error: {exc}")
            return []

    def read_specific_email(self, number: int) -> Optional[EmailMessage]:
        """
        Read a specific email by its 1-based index.

        Uses the cached email list from the last read_emails call.

        Args:
            number: 1-based email number.

        Returns:
            EmailMessage or None.
        """
        with self._lock:
            if 1 <= number <= len(self._cached_emails):
                return self._cached_emails[number - 1]

        # If not in cache, fetch latest and try again
        self.read_emails()
        with self._lock:
            if 1 <= number <= len(self._cached_emails):
                return self._cached_emails[number - 1]

        return None

    def send_email(self, to: str, subject: str, body: str) -> bool:
        """
        Send an email.

        Args:
            to: Recipient (name or email address).
            subject: Email subject.
            body: Email body.

        Returns:
            True if sent (or demo mode), False on error.
        """
        if self._demo_mode:
            print(f"[EmailCalendar] DEMO: Would send email to {to}: {body}")
            return True

        return self.email_client.send_email(to, subject, body)

    def check_unread_count(self) -> int:
        """
        Check the number of unread emails.

        Returns:
            Number of unread emails, or count of demo emails.
        """
        if self._demo_mode:
            return len(self._demo_emails)

        count = self.email_client.get_unread_count()
        return max(count, 0)

    def delete_email(self, number: int) -> bool:
        """
        Delete an email by its 1-based index.

        Args:
            number: 1-based email number from the cached list.

        Returns:
            True if deleted, False otherwise.
        """
        with self._lock:
            if 1 <= number <= len(self._cached_emails):
                uid = self._cached_emails[number - 1].uid
            else:
                return False

        if self._demo_mode:
            print(f"[EmailCalendar] DEMO: Would delete email {number} (UID {uid})")
            return True

        return self.email_client.delete_email(uid)

    def search_emails(self, query: str) -> List[EmailMessage]:
        """
        Search emails by sender or subject.

        Args:
            query: Search term.

        Returns:
            List of matching EmailMessage objects.
        """
        if self._demo_mode:
            query_lower = query.lower()
            return [
                e for e in self._demo_emails
                if query_lower in e.sender.lower()
                or query_lower in e.sender_email.lower()
                or query_lower in e.subject.lower()
            ]

        try:
            results = self.email_client.search_emails(query, criteria="FROM")
            if not results:
                results = self.email_client.search_emails(query, criteria="SUBJECT")
            with self._lock:
                self._cached_emails = results
            return results
        except Exception as exc:
            print(f"[EmailCalendar] search_emails error: {exc}")
            return []

    def reply_to_email(self, number: int, body: str) -> bool:
        """
        Reply to an email by its 1-based index.

        Args:
            number: 1-based email number.
            body: Reply body text.

        Returns:
            True if reply sent, False otherwise.
        """
        msg = self.read_specific_email(number)
        if msg is None:
            return False

        subject = f"Re: {msg.subject}"
        to = msg.sender_email

        if self._demo_mode:
            print(f"[EmailCalendar] DEMO: Would reply to {to} with: {body}")
            return True

        return self.email_client.send_email(to, subject, body)

    # ── Calendar operations ───────────────────────────────────────

    def get_calendar_events(self, date: Optional[str] = None) -> List[CalendarEvent]:
        """
        Get calendar events for a date.

        Args:
            date: Date in "YYYY-MM-DD" format, or None for today.

        Returns:
            List of CalendarEvent objects.
        """
        if not self.calendar_enabled:
            return []
        return self.calendar_client.get_events(date)

    def add_calendar_event(
        self,
        title: str,
        start_time: str,
        duration: Optional[int] = None,
        description: str = "",
    ) -> Optional[CalendarEvent]:
        """
        Add a calendar event.

        Args:
            title: Event title.
            start_time: ISO 8601 datetime string.
            duration: Duration in minutes (optional).
            description: Event description.

        Returns:
            The created CalendarEvent, or None.
        """
        if not self.calendar_enabled:
            return None
        return self.calendar_client.add_event(
            title=title,
            start_time=start_time,
            duration_minutes=duration,
            description=description,
        )

    def delete_calendar_event(self, event_id: str) -> bool:
        """Delete a calendar event by ID."""
        if not self.calendar_enabled:
            return False
        return self.calendar_client.delete_event(event_id)

    def check_upcoming(self, days: int = 7) -> List[CalendarEvent]:
        """
        Get upcoming events within the next N days.

        Args:
            days: Number of days to look ahead.

        Returns:
            List of CalendarEvent objects.
        """
        if not self.calendar_enabled:
            return []
        return self.calendar_client.get_upcoming_events(days)

    # ── Calendar reminder callback ────────────────────────────────

    def _on_calendar_reminder(self, event: CalendarEvent):
        """
        Called by CalendarClient when a reminder fires.

        Publishes a SPEAK_REQUEST event so JARVIS announces the reminder.
        """
        from ai_core.event_bus import Event, EventTypes

        minutes_left = event.reminder_minutes
        message = (
            f"Reminder: you have {event.title} "
            f"in {minutes_left} minutes "
            f"at {event.start_dt.strftime('%I:%M %p')}."
        )

        self.event_bus.publish(
            Event(EventTypes.SPEAK_REQUEST, {"text": message})
        )
        print(f"[EmailCalendar] Reminder fired: {message}")

    # ── EventBus: Voice Command Handler ───────────────────────────

    def _on_voice_command(self, event):
        """
        Handle VOICE_COMMAND events for email and calendar commands.

        Routes voice commands to the appropriate handler method.
        """
        if not self._running:
            return

        command = event.data.get("command", "")
        text = event.data.get("text", "").lower()
        original_text = event.data.get("text", "")

        # Route email commands
        if command == "email" or self._is_email_command(text):
            self._handle_email_command(original_text)
        # Route calendar commands
        elif command == "calendar" or self._is_calendar_command(text):
            self._handle_calendar_command(original_text)

    # ── Command detection ─────────────────────────────────────────

    @staticmethod
    def _is_email_command(text: str) -> bool:
        """Check if the voice text contains an email-related command."""
        email_phrases = [
            "read my email",
            "read email",
            "check email",
            "any new email",
            "new email",
            "unread email",
            "send email",
            "reply to email",
            "delete email",
            "search email",
            "check my email",
            "email from",
        ]
        return any(phrase in text for phrase in email_phrases)

    @staticmethod
    def _is_calendar_command(text: str) -> bool:
        """Check if the voice text contains a calendar-related command."""
        cal_phrases = [
            "calendar",
            "schedule",
            "what's on my",
            "what is on my",
            "add event",
            "add meeting",
            "create event",
            "schedule meeting",
            "cancel my",
            "cancel meeting",
            "cancel event",
            "delete event",
            "what's coming up",
            "upcoming event",
            "my schedule",
            "today's schedule",
            "this week",
        ]
        return any(phrase in text for phrase in cal_phrases)

    # ── Email command handler ─────────────────────────────────────

    def _handle_email_command(self, text: str):
        """Route and execute email voice commands."""
        text_lower = text.lower()

        # "read email number N"
        m = re.search(r"read\s+email\s+number\s+(\d+)", text_lower)
        if m:
            number = int(m.group(1))
            self._speak_email_detail(number)
            return

        # "send email to X saying Y"
        parsed = _parse_send_email_command(text)
        if parsed:
            self._handle_send_email(parsed["to"], parsed["body"])
            return

        # "reply to email N saying X"
        parsed = _parse_reply_command(text)
        if parsed:
            self._handle_reply_email(parsed["email_number"], parsed["body"])
            return

        # "delete email number N"
        m = re.search(r"delete\s+email\s+number\s+(\d+)", text_lower)
        if not m:
            m = re.search(r"delete\s+email\s+(\d+)", text_lower)
        if m:
            number = int(m.group(1))
            self._handle_delete_email(number)
            return

        # "search emails from X"
        m = re.search(r"search\s+email(?:s)?\s+(?:from\s+)?(.+)", text_lower)
        if m:
            query = m.group(1).strip()
            self._handle_search_emails(query)
            return

        # "check email from X" / "email from X"
        m = re.search(r"(?:check\s+)?email\s+from\s+(.+)", text_lower)
        if m:
            query = m.group(1).strip()
            self._handle_search_emails(query)
            return

        # "any new emails?" / "new emails"
        if "new email" in text_lower or "unread" in text_lower:
            self._handle_unread_count()
            return

        # "read my emails" (default)
        if "email" in text_lower:
            self._handle_read_emails()
            return

    # ── Calendar command handler ──────────────────────────────────

    def _handle_calendar_command(self, text: str):
        """Route and execute calendar voice commands."""
        text_lower = text.lower()

        # "add event/meeting X at Y"
        parsed = _parse_add_event_command(text)
        if parsed:
            self._handle_add_event(parsed)
            return

        # "cancel/delete event X"
        parsed = _parse_delete_event_command(text)
        if parsed:
            self._handle_delete_event(parsed)
            return

        # "what's coming up this week" / "upcoming"
        if "coming up" in text_lower or "upcoming" in text_lower or "this week" in text_lower:
            self._handle_upcoming_events()
            return

        # "what's on my calendar today" / "schedule today"
        if "today" in text_lower or "calendar" in text_lower or "schedule" in text_lower:
            self._handle_today_events()
            return

        # Default: show today's events
        self._handle_today_events()

    # ── Email handlers ────────────────────────────────────────────

    def _handle_read_emails(self, count: int = 5):
        """Read and speak the latest emails."""
        from ai_core.event_bus import Event, EventTypes

        if self._demo_mode:
            emails = self._demo_emails[:count]
        else:
            emails = self.read_emails(count)

        if not emails:
            self._speak("You have no emails to read.")
            return

        with self._lock:
            self._cached_emails = emails

        if self._demo_mode:
            self._speak(
                "You're in demo mode. Here are your sample emails. "
                "To read real emails, configure your email settings in config.yaml."
            )

        lines = []
        for i, msg in enumerate(emails, 1):
            lines.append(f"Email {i}: {msg.brief()}")

        response = ". ".join(lines)
        self._speak(response)

        # Dashboard update
        self.event_bus.publish(
            Event(
                EventTypes.DASHBOARD_UPDATE,
                {
                    "panel": "email",
                    "emails": [e.to_dict() for e in emails],
                    "demo_mode": self._demo_mode,
                },
            )
        )

    def _speak_email_detail(self, number: int):
        """Speak the full content of a specific email."""
        msg = self.read_specific_email(number)
        if msg is None:
            self._speak(f"Email number {number} not found. Say read my emails first.")
            return

        self._speak(msg.full())

    def _handle_unread_count(self):
        """Check and speak the unread email count."""
        count = self.check_unread_count()
        if count < 0:
            self._speak("I couldn't check your emails. Please verify your email settings.")
        elif count == 0:
            self._speak("You have no unread emails.")
        else:
            word = "email" if count == 1 else "emails"
            prefix = "In demo mode, you have " if self._demo_mode else "You have "
            self._speak(f"{prefix}{count} unread {word}.")

    def _handle_send_email(self, to: str, body: str):
        """Handle a send-email voice command with confirmation."""
        from ai_core.event_bus import Event, EventTypes

        # Confirm before sending
        self._speak(
            f"I'll send an email to {to} saying: {body}. "
            f"Please confirm."
        )

        # For now, auto-send (in a full system, wait for confirmation)
        success = self.send_email(to, f"Message from JARVIS", body)
        if success:
            if self._demo_mode:
                self._speak(f"Demo mode: email to {to} would be sent. Configure email settings to send real emails.")
            else:
                self._speak(f"Email sent to {to}.")
        else:
            self._speak("I couldn't send the email. Please check your email configuration.")

    def _handle_reply_email(self, number: int, body: str):
        """Handle a reply-to-email voice command."""
        success = self.reply_to_email(number, body)
        if success:
            if self._demo_mode:
                self._speak(f"Demo mode: reply to email {number} would be sent.")
            else:
                self._speak(f"Reply sent to email {number}.")
        else:
            self._speak(f"Couldn't reply to email {number}. Please check the email number.")

    def _handle_delete_email(self, number: int):
        """Handle a delete-email voice command."""
        success = self.delete_email(number)
        if success:
            self._speak(f"Email {number} deleted.")
        else:
            self._speak(f"Couldn't delete email {number}. Please check the email number.")

    def _handle_search_emails(self, query: str):
        """Handle a search-emails voice command."""
        from ai_core.event_bus import Event, EventTypes

        results = self.search_emails(query)
        if not results:
            self._speak(f"No emails found matching {query}.")
            return

        with self._lock:
            self._cached_emails = results

        lines = [f"Email {i}: {msg.brief()}" for i, msg in enumerate(results, 1)]
        response = f"Found {len(results)} emails. " + ". ".join(lines)
        self._speak(response)

    # ── Calendar handlers ─────────────────────────────────────────

    def _handle_today_events(self):
        """Handle a voice command to show today's events."""
        from ai_core.event_bus import Event, EventTypes

        events = self.get_calendar_events()
        now = datetime.now()

        if not events:
            self._speak("You have no events scheduled for today.")
            return

        lines = []
        for ev in events:
            time_str = ev.start_dt.strftime("%I:%M %p")
            lines.append(f"{ev.title} at {time_str}")

        response = f"You have {len(events)} event{'s' if len(events) > 1 else ''} today. " + ". ".join(lines)
        self._speak(response)

        # Dashboard update
        self.event_bus.publish(
            Event(
                EventTypes.DASHBOARD_UPDATE,
                {
                    "panel": "calendar",
                    "date": now.date().isoformat(),
                    "events": [e.to_dict() for e in events],
                },
            )
        )

    def _handle_upcoming_events(self, days: int = 7):
        """Handle a voice command to show upcoming events."""
        from ai_core.event_bus import Event, EventTypes

        events = self.check_upcoming(days)

        if not events:
            self._speak(f"You have no events coming up in the next {days} days.")
            return

        lines = []
        for ev in events:
            date_str = ev.start_dt.strftime("%A at %I:%M %p")
            lines.append(f"{ev.title} on {date_str}")

        response = f"You have {len(events)} upcoming event{'s' if len(events) > 1 else ''}. " + ". ".join(lines)
        self._speak(response)

        # Dashboard update
        self.event_bus.publish(
            Event(
                EventTypes.DASHBOARD_UPDATE,
                {
                    "panel": "calendar",
                    "view": "upcoming",
                    "events": [e.to_dict() for e in events],
                },
            )
        )

    def _handle_add_event(self, parsed: Dict):
        """Handle an add-event voice command."""
        title = parsed["title"]
        date = parsed["date"]
        hour = parsed["hour"]
        minute = parsed.get("minute", 0)

        start_time = f"{date}T{hour:02d}:{minute:02d}:00"

        event = self.add_calendar_event(title=title, start_time=start_time)
        if event:
            time_str = event.start_dt.strftime("%I:%M %p on %A")
            self._speak(f"Added {title} at {time_str}.")
        else:
            self._speak("I couldn't add the event. Calendar may be disabled.")

    def _handle_delete_event(self, parsed: Dict):
        """Handle a cancel/delete-event voice command."""
        keyword = parsed.get("keyword", "")
        hour = parsed.get("hour")

        # Try to find by title keyword
        candidates = self.calendar_client.find_event_by_title(keyword)

        if not candidates and hour is not None:
            # Try to find by time today
            today = datetime.now().date().isoformat()
            candidates = self.calendar_client.find_event_by_time(today, hour)

        if not candidates:
            self._speak(f"I couldn't find an event matching {keyword}.")
            return

        if len(candidates) == 1:
            event = candidates[0]
            success = self.delete_calendar_event(event.event_id)
            if success:
                self._speak(f"Cancelled {event.title}.")
            else:
                self._speak("I couldn't cancel that event.")
        else:
            # Multiple matches — list them
            lines = [
                f"Number {i}: {ev.title} at {ev.start_dt.strftime('%I:%M %p')}"
                for i, ev in enumerate(candidates, 1)
            ]
            self._speak(
                f"Found {len(candidates)} matching events. " +
                ". ".join(lines) +
                ". Please specify which one to cancel."
            )

    # ── Gmail setup guidance ──────────────────────────────────────

    def get_setup_instructions(self) -> str:
        """
        Return instructions for setting up Gmail with App Passwords.

        Returns:
            Setup instruction string suitable for speech or display.
        """
        return (
            "To set up Gmail, follow these steps. "
            "First, go to your Google Account settings at myaccount.google.com. "
            "Second, enable two-factor authentication if you haven't already. "
            "Third, go to the Security section and find App Passwords. "
            "Fourth, generate a new app password for JARVIS. "
            "Fifth, copy the 16-character password. "
            "Sixth, open your config.yaml file and fill in your email address "
            "and paste the app password in the email_calendar section. "
            "Set email_enabled to true and restart JARVIS. "
            "Remember, never use your real Google password. Only use app passwords."
        )

    # ── Utility ───────────────────────────────────────────────────

    def _speak(self, text: str):
        """
        Publish a SPEAK_REQUEST event to make JARVIS speak the text.

        Also publishes a DASHBOARD_UPDATE with the text for visual display.
        """
        from ai_core.event_bus import Event, EventTypes

        self.event_bus.publish(
            Event(EventTypes.SPEAK_REQUEST, {"text": text})
        )

        # Also push to dashboard status
        self.event_bus.publish(
            Event(EventTypes.DASHBOARD_UPDATE, {
                "panel": "email_calendar",
                "message": text,
            })
        )

    def get_status(self) -> Dict:
        """
        Get the current status of the module.

        Returns:
            Dict with module status information.
        """
        return {
            "email_enabled": self.email_enabled,
            "email_configured": self.email_client.is_configured,
            "demo_mode": self._demo_mode,
            "calendar_enabled": self.calendar_enabled,
            "calendar_events_count": len(self.calendar_client.get_all_events()),
            "unread_emails": self.check_unread_count() if self.email_enabled or self._demo_mode else 0,
        }
