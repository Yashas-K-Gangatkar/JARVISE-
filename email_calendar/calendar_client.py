"""
Calendar Client - Local JSON-based calendar for JARVIS AI Assistant.

Stores calendar events in a local JSON file. Supports:
- Adding, deleting, and querying events
- Recurring reminders via a background thread
- iCal/ICS export (optional)
- Google Calendar API integration (optional, future)
"""

import json
import os
import threading
import time
import uuid
from datetime import datetime, timedelta
from typing import Callable, Dict, List, Optional


# ---------------------------------------------------------------------------
# Calendar event data container
# ---------------------------------------------------------------------------

class CalendarEvent:
    """Represents a single calendar event."""

    def __init__(
        self,
        event_id: str,
        title: str,
        start_time: str,       # ISO 8601 format: "2026-03-05T15:00:00"
        duration_minutes: int,
        description: str = "",
        reminder_minutes: int = 15,
        created_at: Optional[str] = None,
    ):
        self.event_id = event_id
        self.title = title
        self.start_time = start_time
        self.duration_minutes = duration_minutes
        self.description = description
        self.reminder_minutes = reminder_minutes
        self.created_at = created_at or datetime.now().isoformat()
        self.reminded = False  # track if reminder was already fired

    @property
    def start_dt(self) -> datetime:
        """Parse start_time into a datetime object."""
        return datetime.fromisoformat(self.start_time)

    @property
    def end_dt(self) -> datetime:
        """Calculate end datetime."""
        return self.start_dt + timedelta(minutes=self.duration_minutes)

    @property
    def end_time(self) -> str:
        """End time as ISO string."""
        return self.end_dt.isoformat()

    def is_today(self) -> bool:
        """Check if the event is today."""
        return self.start_dt.date() == datetime.now().date()

    def is_upcoming(self, within_minutes: int = 0) -> bool:
        """Check if the event starts within the given minutes from now."""
        now = datetime.now()
        delta = self.start_dt - now
        return timedelta(0) <= delta <= timedelta(minutes=within_minutes)

    def needs_reminder(self) -> bool:
        """Check if the reminder should fire now."""
        if self.reminded:
            return False
        now = datetime.now()
        reminder_time = self.start_dt - timedelta(minutes=self.reminder_minutes)
        return now >= reminder_time and now < self.start_dt

    def to_dict(self) -> Dict:
        return {
            "event_id": self.event_id,
            "title": self.title,
            "start_time": self.start_time,
            "duration_minutes": self.duration_minutes,
            "description": self.description,
            "reminder_minutes": self.reminder_minutes,
            "created_at": self.created_at,
            "reminded": self.reminded,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "CalendarEvent":
        event = cls(
            event_id=data.get("event_id", str(uuid.uuid4())),
            title=data.get("title", "Untitled Event"),
            start_time=data.get("start_time", datetime.now().isoformat()),
            duration_minutes=data.get("duration_minutes", 60),
            description=data.get("description", ""),
            reminder_minutes=data.get("reminder_minutes", 15),
            created_at=data.get("created_at"),
        )
        event.reminded = data.get("reminded", False)
        return event

    def __repr__(self):
        return (
            f"CalendarEvent(id={self.event_id}, title={self.title}, "
            f"start={self.start_time}, dur={self.duration_minutes}m)"
        )


# ---------------------------------------------------------------------------
# Local JSON Calendar Client
# ---------------------------------------------------------------------------

class CalendarClient:
    """
    Local JSON-based calendar client.

    Events are stored in a JSON file on disk. A background thread
    checks for upcoming reminders and invokes a callback.
    """

    def __init__(self, config: dict, reminder_callback: Optional[Callable] = None):
        """
        Initialise the calendar client.

        Args:
            config: Calendar config dict with keys:
                data_file, reminder_minutes_before,
                default_event_duration_minutes
            reminder_callback: Function called when a reminder fires.
                               Signature: callback(event: CalendarEvent)
        """
        self.data_file = config.get("data_file", "calendar_events.json")
        self.default_duration = config.get("default_event_duration_minutes", 60)
        self.reminder_minutes = config.get("reminder_minutes_before", 15)
        self.reminder_callback = reminder_callback

        self._events: Dict[str, CalendarEvent] = {}
        self._lock = threading.Lock()
        self._running = False
        self._reminder_thread: Optional[threading.Thread] = None

        # Load existing events from disk
        self._load()

    # ── Persistence ───────────────────────────────────────────────

    def _load(self):
        """Load events from the JSON data file."""
        if not os.path.exists(self.data_file):
            self._events = {}
            return

        try:
            with open(self.data_file, "r", encoding="utf-8") as fh:
                data = json.load(fh)

            if isinstance(data, dict):
                raw_events = data.get("events", [])
            elif isinstance(data, list):
                raw_events = data
            else:
                raw_events = []

            self._events = {}
            for item in raw_events:
                try:
                    event = CalendarEvent.from_dict(item)
                    self._events[event.event_id] = event
                except Exception as exc:
                    print(f"[CalendarClient] Skipping invalid event: {exc}")

            print(f"[CalendarClient] Loaded {len(self._events)} events from {self.data_file}")

        except (json.JSONDecodeError, OSError) as exc:
            print(f"[CalendarClient] Error loading data file: {exc}")
            self._events = {}

    def _save(self):
        """Save events to the JSON data file."""
        events_list = [e.to_dict() for e in self._events.values()]
        payload = {
            "version": 1,
            "last_updated": datetime.now().isoformat(),
            "events": events_list,
        }

        try:
            # Ensure parent directory exists
            parent = os.path.dirname(self.data_file)
            if parent and not os.path.exists(parent):
                os.makedirs(parent, exist_ok=True)

            with open(self.data_file, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, indent=2, ensure_ascii=False)

        except OSError as exc:
            print(f"[CalendarClient] Error saving data file: {exc}")

    # ── CRUD Operations ───────────────────────────────────────────

    def add_event(
        self,
        title: str,
        start_time: str,
        duration_minutes: Optional[int] = None,
        description: str = "",
        reminder_minutes: Optional[int] = None,
    ) -> CalendarEvent:
        """
        Add a new calendar event.

        Args:
            title: Event title.
            start_time: Start time in ISO 8601 format (e.g. "2026-03-05T15:00:00").
            duration_minutes: Duration in minutes (uses default if not specified).
            description: Optional event description.
            reminder_minutes: Minutes before event to trigger reminder.

        Returns:
            The created CalendarEvent.
        """
        event_id = str(uuid.uuid4())[:8]  # short, human-friendly ID
        duration = duration_minutes if duration_minutes is not None else self.default_duration
        reminder = reminder_minutes if reminder_minutes is not None else self.reminder_minutes

        event = CalendarEvent(
            event_id=event_id,
            title=title,
            start_time=start_time,
            duration_minutes=duration,
            description=description,
            reminder_minutes=reminder,
        )

        with self._lock:
            self._events[event.event_id] = event
            self._save()

        print(f"[CalendarClient] Added event: {event}")
        return event

    def delete_event(self, event_id: str) -> bool:
        """
        Delete an event by ID.

        Args:
            event_id: The event ID to delete.

        Returns:
            True if the event was found and deleted, False otherwise.
        """
        with self._lock:
            if event_id in self._events:
                del self._events[event_id]
                self._save()
                print(f"[CalendarClient] Deleted event {event_id}")
                return True
            else:
                print(f"[CalendarClient] Event not found: {event_id}")
                return False

    def get_events(self, date: Optional[str] = None) -> List[CalendarEvent]:
        """
        Get events for a specific date.

        Args:
            date: Date string in "YYYY-MM-DD" format. Defaults to today.

        Returns:
            List of CalendarEvent objects on that date, sorted by start time.
        """
        if date is None:
            target_date = datetime.now().date()
        else:
            target_date = datetime.fromisoformat(date).date()

        with self._lock:
            matching = [
                e for e in self._events.values()
                if e.start_dt.date() == target_date
            ]

        matching.sort(key=lambda e: e.start_dt)
        return matching

    def get_upcoming_events(self, days: int = 7) -> List[CalendarEvent]:
        """
        Get upcoming events within the next N days.

        Args:
            days: Number of days to look ahead.

        Returns:
            List of CalendarEvent objects, sorted by start time.
        """
        now = datetime.now()
        cutoff = now + timedelta(days=days)

        with self._lock:
            upcoming = [
                e for e in self._events.values()
                if now <= e.start_dt <= cutoff
            ]

        upcoming.sort(key=lambda e: e.start_dt)
        return upcoming

    def get_all_events(self) -> List[CalendarEvent]:
        """Get all events, sorted by start time."""
        with self._lock:
            all_events = list(self._events.values())
        all_events.sort(key=lambda e: e.start_dt)
        return all_events

    def find_event_by_title(self, keyword: str) -> List[CalendarEvent]:
        """
        Find events whose title contains the given keyword (case-insensitive).

        Args:
            keyword: Search term.

        Returns:
            List of matching CalendarEvent objects.
        """
        keyword_lower = keyword.lower()
        with self._lock:
            matching = [
                e for e in self._events.values()
                if keyword_lower in e.title.lower()
            ]
        matching.sort(key=lambda e: e.start_dt)
        return matching

    def find_event_by_time(self, date: str, hour: int, minute: int = 0) -> List[CalendarEvent]:
        """
        Find events on a given date starting at or near a specific time.

        Args:
            date: Date string in "YYYY-MM-DD" format.
            hour: Hour (24-hour format).
            minute: Minute.

        Returns:
            List of matching CalendarEvent objects.
        """
        target = datetime.fromisoformat(date).replace(hour=hour, minute=minute)
        tolerance = timedelta(minutes=30)

        with self._lock:
            matching = [
                e for e in self._events.values()
                if e.start_dt.date() == target.date()
                and abs(e.start_dt - target) <= tolerance
            ]

        matching.sort(key=lambda e: e.start_dt)
        return matching

    # ── Reminder Thread ───────────────────────────────────────────

    def start_reminders(self):
        """Start the background reminder-checking thread."""
        if self._running:
            return

        self._running = True
        self._reminder_thread = threading.Thread(
            target=self._reminder_loop,
            daemon=True,
            name="CalendarReminders",
        )
        self._reminder_thread.start()
        print("[CalendarClient] Reminder thread started")

    def stop_reminders(self):
        """Stop the background reminder-checking thread."""
        self._running = False
        if self._reminder_thread:
            self._reminder_thread.join(timeout=3)
        print("[CalendarClient] Reminder thread stopped")

    def _reminder_loop(self):
        """Background loop that checks for upcoming event reminders."""
        while self._running:
            try:
                self._check_reminders()
            except Exception as exc:
                print(f"[CalendarClient] Reminder check error: {exc}")
            time.sleep(30)  # check every 30 seconds

    def _check_reminders(self):
        """Check all events and fire reminders for those approaching."""
        now = datetime.now()

        with self._lock:
            for event in self._events.values():
                if event.reminded:
                    continue

                reminder_time = event.start_dt - timedelta(minutes=event.reminder_minutes)
                if now >= reminder_time and now < event.start_dt:
                    event.reminded = True
                    self._save()

                    if self.reminder_callback:
                        try:
                            self.reminder_callback(event)
                        except Exception as exc:
                            print(f"[CalendarClient] Reminder callback error: {exc}")

    # ── ICS Export ────────────────────────────────────────────────

    def export_ics(self, filepath: str) -> bool:
        """
        Export all events to an iCalendar (.ics) file.

        Args:
            filepath: Path to write the .ics file.

        Returns:
            True if export succeeded, False otherwise.
        """
        lines = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//JARVIS AI//Calendar//EN",
            "CALSCALE:GREGORIAN",
            "METHOD:PUBLISH",
        ]

        with self._lock:
            events = list(self._events.values())

        for event in events:
            dt_start = event.start_dt.strftime("%Y%m%dT%H%M%S")
            dt_end = event.end_dt.strftime("%Y%m%dT%H%M%S")
            dt_stamp = datetime.now().strftime("%Y%m%dT%H%M%SZ")

            lines.extend([
                "BEGIN:VEVENT",
                f"UID:{event.event_id}@jarvis-ai",
                f"DTSTAMP:{dt_stamp}",
                f"DTSTART:{dt_start}",
                f"DTEND:{dt_end}",
                f"SUMMARY:{event.title}",
                f"DESCRIPTION:{event.description}",
                f"BEGIN:VALARM",
                f"TRIGGER:-PT{event.reminder_minutes}M",
                "ACTION:DISPLAY",
                f"DESCRIPTION:Reminder: {event.title}",
                "END:VALARM",
                "END:VEVENT",
            ])

        lines.append("END:VCALENDAR")
        ics_content = "\r\n".join(lines)

        try:
            with open(filepath, "w", encoding="utf-8") as fh:
                fh.write(ics_content)
            print(f"[CalendarClient] Exported {len(events)} events to {filepath}")
            return True
        except OSError as exc:
            print(f"[CalendarClient] ICS export error: {exc}")
            return False

    # ── Lifecycle ─────────────────────────────────────────────────

    def start(self):
        """Start the calendar client (including reminder thread)."""
        self.start_reminders()
        print("[CalendarClient] Started")

    def stop(self):
        """Stop the calendar client and save state."""
        self.stop_reminders()
        with self._lock:
            self._save()
        print("[CalendarClient] Stopped")
