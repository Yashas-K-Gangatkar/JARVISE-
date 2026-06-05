"""
Reminder Module - Proactive Alerts & Reminders for JARVIS AI Assistant.

Features:
    - One-time reminders:   "Remind me to call Mom at 5pm"
    - Recurring reminders:  "Remind me to drink water every 2 hours"
    - Timer reminders:      "Set a timer for 10 minutes"
    - Daily briefing:       Morning summary (weather, calendar, news, reminders)

Storage:
    - JSON file persistence (loads on start, saves on every mutation)
    - Survives application restarts

EventBus Integration:
    - Subscribes to VOICE_COMMAND for "remind", "timer", "briefing", etc.
    - Publishes SPEAK_REQUEST when a reminder fires
    - Publishes DASHBOARD_UPDATE to display active reminders

Smart Scheduling:
    - Respects sleep hours (default 23:00 – 07:00)
    - Queues reminders that fall in sleep window for the morning
"""

import json
import os
import re
import threading
import time
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from reminders.time_parser import parse_time, next_fire_time, RecurrencePattern


# ======================================================================
# Reminder data model
# ======================================================================

class Reminder:
    """Single reminder entry."""

    def __init__(
        self,
        text: str,
        trigger_time: datetime,
        recurring: RecurrencePattern = None,
        reminder_type: str = "one_time",
        reminder_id: Optional[str] = None,
    ):
        self.id: str = reminder_id or uuid.uuid4().hex[:8]
        self.text: str = text
        self.trigger_time: datetime = trigger_time
        self.recurring: RecurrencePattern = recurring
        self.reminder_type: str = reminder_type  # "one_time" | "recurring" | "timer" | "briefing"
        self.fired: bool = False
        self.snoozed_until: Optional[datetime] = None
        self.created_at: datetime = datetime.now()

    # -- serialisation ---------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a JSON-friendly dict."""
        return {
            "id": self.id,
            "text": self.text,
            "trigger_time": self.trigger_time.isoformat(),
            "recurring": self._serialise_recurrence(self.recurring),
            "reminder_type": self.reminder_type,
            "fired": self.fired,
            "snoozed_until": self.snoozed_until.isoformat() if self.snoozed_until else None,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Reminder":
        """Deserialise from a dict."""
        r = cls(
            text=data["text"],
            trigger_time=datetime.fromisoformat(data["trigger_time"]),
            recurring=cls._deserialise_recurrence(data.get("recurring")),
            reminder_type=data.get("reminder_type", "one_time"),
            reminder_id=data.get("id"),
        )
        r.fired = data.get("fired", False)
        r.snoozed_until = (
            datetime.fromisoformat(data["snoozed_until"])
            if data.get("snoozed_until")
            else None
        )
        r.created_at = (
            datetime.fromisoformat(data["created_at"])
            if data.get("created_at")
            else datetime.now()
        )
        return r

    # -- helpers ---------------------------------------------------------

    @staticmethod
    def _serialise_recurrence(pattern: RecurrencePattern) -> Any:
        if pattern is None:
            return None
        if isinstance(pattern, str):
            return pattern
        if isinstance(pattern, tuple):
            return {"type": pattern[0], "value": pattern[1]}
        return None

    @staticmethod
    def _deserialise_recurrence(data: Any) -> RecurrencePattern:
        if data is None:
            return None
        if isinstance(data, str):
            return data
        if isinstance(data, dict):
            return (data["type"], data["value"])
        return None

    @property
    def is_recurring(self) -> bool:
        return self.recurring is not None

    @property
    def effective_trigger(self) -> datetime:
        """The time at which this reminder should next fire."""
        if self.snoozed_until:
            return self.snoozed_until
        return self.trigger_time

    def __repr__(self) -> str:
        return (
            f"Reminder(id={self.id!r}, text={self.text!r}, "
            f"trigger={self.trigger_time:%Y-%m-%d %H:%M}, "
            f"type={self.reminder_type}, recurring={self.recurring})"
        )


# ======================================================================
# Main module
# ======================================================================

class ReminderModule:
    """
    Proactive Alerts & Reminders module.

    Integrates with the JARVIS EventBus to handle voice commands for
    reminders and timers, runs a background checker, and produces
    daily briefings.
    """

    def __init__(self, event_bus, config: dict):
        self.event_bus = event_bus
        self.reminder_config: dict = config.get("reminders", {})
        self.prefs_config: dict = config.get("preferences", {})
        self.data_config: dict = config.get("data", {})

        # ── Settings ────────────────────────────────────────────────
        self._data_file: str = self.reminder_config.get(
            "data_file", "reminders/reminder_data.json"
        )
        self._check_interval: int = self.reminder_config.get(
            "check_interval_seconds", 30
        )
        self._briefing_time_str: str = self.reminder_config.get(
            "daily_briefing_time", "08:00"
        )
        self._sleep_start: int = self.reminder_config.get("sleep_hours_start", 23)
        self._sleep_end: int = self.reminder_config.get("sleep_hours_end", 7)
        self._briefing_enabled: bool = self.reminder_config.get(
            "briefing_enabled", True
        )

        # Parse the briefing hour/minute once
        try:
            parts = self._briefing_time_str.split(":")
            self._briefing_hour = int(parts[0])
            self._briefing_minute = int(parts[1]) if len(parts) > 1 else 0
        except (ValueError, IndexError):
            self._briefing_hour = 8
            self._briefing_minute = 0

        # ── State ───────────────────────────────────────────────────
        self._reminders: Dict[str, Reminder] = {}
        self._running: bool = False
        self._checker_thread: Optional[threading.Thread] = None
        self._briefing_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._last_briefing_date: Optional[str] = None  # track daily briefing

        # Cached data for briefings (populated by EventBus events)
        self._cached_news: List[str] = []
        self._cached_stocks: Dict[str, Any] = {}

        # ── Load persisted reminders ────────────────────────────────
        self._load_reminders()

    # ==================================================================
    # Public API
    # ==================================================================

    def start(self):
        """Start the reminder module (background checker + event subscriptions)."""
        self._running = True

        # Subscribe to voice commands
        from ai_core.event_bus import EventTypes

        self.event_bus.subscribe(EventTypes.VOICE_COMMAND, self._on_voice_command)
        self.event_bus.subscribe(EventTypes.NEWS_UPDATED, self._on_news_updated)
        self.event_bus.subscribe(EventTypes.STOCKS_UPDATED, self._on_stocks_updated)

        # Start background checker thread
        self._checker_thread = threading.Thread(
            target=self._checker_loop, daemon=True, name="ReminderChecker"
        )
        self._checker_thread.start()

        # Start daily-briefing scheduler thread
        self._briefing_thread = threading.Thread(
            target=self._briefing_scheduler_loop,
            daemon=True,
            name="BriefingScheduler",
        )
        self._briefing_thread.start()

        print(
            f"[ReminderModule] Started — checking every {self._check_interval}s, "
            f"briefing at {self._briefing_time_str}"
        )

    def stop(self):
        """Stop the reminder module gracefully."""
        self._running = False
        # Wait for threads to finish
        if self._checker_thread and self._checker_thread.is_alive():
            self._checker_thread.join(timeout=3)
        if self._briefing_thread and self._briefing_thread.is_alive():
            self._briefing_thread.join(timeout=3)
        # Persist state
        self._save_reminders()
        print("[ReminderModule] Stopped")

    def add_reminder(
        self,
        text: str,
        trigger_time: datetime,
        recurring: RecurrencePattern = None,
        reminder_type: str = "one_time",
    ) -> Reminder:
        """
        Add a new reminder.

        Args:
            text:          The reminder message.
            trigger_time:  When the reminder should fire.
            recurring:     Recurrence pattern (None, "daily", "weekly",
                           or ("interval", seconds)).
            reminder_type: One of "one_time", "recurring", "timer", "briefing".

        Returns:
            The created Reminder object.
        """
        reminder = Reminder(
            text=text,
            trigger_time=trigger_time,
            recurring=recurring,
            reminder_type=reminder_type,
        )
        with self._lock:
            self._reminders[reminder.id] = reminder
        self._save_reminders()
        print(f"[ReminderModule] Added: {reminder}")
        return reminder

    def remove_reminder(self, reminder_id: str) -> bool:
        """
        Remove a reminder by its ID.

        Returns:
            True if the reminder was found and removed.
        """
        with self._lock:
            removed = self._reminders.pop(reminder_id, None)
        if removed:
            self._save_reminders()
            print(f"[ReminderModule] Removed: {removed}")
            return True
        return False

    def get_active_reminders(self) -> List[Reminder]:
        """Return all reminders that have not yet fired (or are recurring)."""
        with self._lock:
            return [
                r for r in self._reminders.values()
                if not r.fired or r.is_recurring
            ]

    def get_all_reminders(self) -> List[Reminder]:
        """Return all reminders including fired ones."""
        with self._lock:
            return list(self._reminders.values())

    def trigger_briefing(self):
        """
        Manually trigger the daily briefing.

        Assembles a spoken summary and publishes it as a SPEAK_REQUEST.
        """
        user_name = self.prefs_config.get("user_name", "Sir")
        now = datetime.now()

        # Greeting based on time of day
        if now.hour < 12:
            greeting = "Good morning"
        elif now.hour < 17:
            greeting = "Good afternoon"
        else:
            greeting = "Good evening"

        parts: List[str] = [f"{greeting}, {user_name}. Here is your briefing."]

        # ── Today's reminders ───────────────────────────────────────
        today_reminders = [
            r for r in self.get_active_reminders()
            if r.effective_trigger.date() == now.date()
        ]
        if today_reminders:
            parts.append(f"You have {len(today_reminders)} reminder{'s' if len(today_reminders) != 1 else ''} today:")
            for r in today_reminders[:5]:
                t = r.effective_trigger.strftime("%I:%M %p")
                parts.append(f"  At {t}, {r.text}.")
        else:
            parts.append("You have no reminders scheduled for today.")

        # ── News headlines ──────────────────────────────────────────
        if self._cached_news:
            parts.append("Here are the top news headlines:")
            for i, headline in enumerate(self._cached_news[:3], 1):
                parts.append(f"  {i}. {headline}")
        else:
            parts.append("News headlines are not available at the moment.")

        # ── Stock summary ───────────────────────────────────────────
        if self._cached_stocks:
            stock_parts = []
            for symbol, data in list(self._cached_stocks.items())[:5]:
                price = data.get("price", "N/A")
                change = data.get("change_pct", data.get("change", ""))
                stock_parts.append(f"{symbol} at {price} ({change})")
            if stock_parts:
                parts.append("Stock update: " + ", ".join(stock_parts) + ".")
        else:
            parts.append("Stock data is not available at the moment.")

        # ── Current time ────────────────────────────────────────────
        parts.append(f"The current time is {now.strftime('%I:%M %p on %A, %B %d')}.")

        parts.append("That's all for now. Have a great day!")

        briefing_text = " ".join(parts)

        # Publish speak event
        from ai_core.event_bus import Event, EventTypes

        self.event_bus.publish(
            Event(EventTypes.SPEAK_REQUEST, {"text": briefing_text})
        )

        # Also update dashboard
        self.event_bus.publish(
            Event(
                EventTypes.DASHBOARD_UPDATE,
                {
                    "panel": "briefing",
                    "briefing": briefing_text,
                    "reminders_today": [
                        {"id": r.id, "text": r.text, "time": r.effective_trigger.isoformat()}
                        for r in today_reminders
                    ],
                },
            )
        )

        print("[ReminderModule] Briefing triggered")

    # ==================================================================
    # Voice command handling
    # ==================================================================

    def _on_voice_command(self, event):
        """Handle VOICE_COMMAND events relevant to reminders."""
        data = event.data or {}
        command = data.get("command", "")
        raw_text = data.get("text", "") or data.get("params", {}).get("raw_text", "")

        # Route to the right handler
        if command == "remind":
            self._handle_remind_command(raw_text)
        elif command == "timer":
            self._handle_timer_command(raw_text)
        elif command == "briefing":
            self.trigger_briefing()
        elif command == "show_reminders":
            self._handle_show_reminders()
        elif command == "clear_reminders":
            self._handle_clear_reminders()
        elif command == "cancel_reminder":
            self._handle_cancel_reminder(raw_text)
        elif command == "schedule":
            self._handle_schedule_command(raw_text)
        else:
            # Catch-all: check raw text for reminder keywords
            text_lower = raw_text.lower()
            if any(kw in text_lower for kw in ("remind", "reminder", "remember")):
                self._handle_remind_command(raw_text)
            elif "timer" in text_lower:
                self._handle_timer_command(raw_text)
            elif any(kw in text_lower for kw in ("briefing", "brief me", "morning report")):
                self.trigger_briefing()
            elif any(kw in text_lower for kw in ("my reminders", "show reminder", "what reminder")):
                self._handle_show_reminders()
            elif any(kw in text_lower for kw in ("clear reminder", "delete reminder")):
                self._handle_clear_reminders()
            elif any(kw in text_lower for kw in ("cancel reminder", "remove reminder")):
                self._handle_cancel_reminder(raw_text)
            elif any(kw in text_lower for kw in ("schedule", "what's on", "my schedule", "today's schedule")):
                self._handle_schedule_command(raw_text)

    def _handle_remind_command(self, raw_text: str):
        """
        Parse and handle: "remind me to [task] at [time]"
                          "remind me to [task] every [recurrence]"
        """
        from ai_core.event_bus import Event, EventTypes

        text_lower = raw_text.lower()

        # Strip leading "jarvis" or wake word
        text_clean = re.sub(r"^(jarvis\s+)?", "", text_lower, flags=re.IGNORECASE).strip()

        # Remove "remind me to" / "remind me" / "reminder to"
        task_match = re.match(
            r"(?:remind\s+me\s+(?:to\s+)?)"
            r"(?P<task>.+?)(?:\s+(?:at|by|on|in|every|tomorrow|next))",
            text_clean,
            re.IGNORECASE,
        )
        if task_match:
            task = task_match.group("task").strip()
            # Time part is everything after the preposition
            time_match = re.search(
                r"(?:at|by|on|in|every|tomorrow|next)\s+(?P<time>.+)",
                text_clean,
                re.IGNORECASE,
            )
            time_str = time_match.group("time").strip() if time_match else ""
            # Reconstruct the full preposition+time for the parser
            if time_match:
                full_time_str = time_match.group(0).strip()
            else:
                full_time_str = ""
        else:
            # Simpler: "remind me to call Mom at 5pm"
            # Try splitting on " at ", " by ", " on ", " every "
            split_match = re.match(
                r"(?:remind\s+me\s+(?:to\s+)?)?(?P<task>.+?)"
                r"\s+(?:at|by|on|every|in|tomorrow|next)\s+(?P<time>.+)",
                text_clean,
                re.IGNORECASE,
            )
            if split_match:
                task = split_match.group("task").strip()
                # Recombine the preposition with the time for parse_time
                preposition_match = re.search(
                    r"(at|by|on|every|in|tomorrow|next)\s+.+",
                    text_clean,
                    re.IGNORECASE,
                )
                full_time_str = preposition_match.group(0).strip() if preposition_match else ""
            else:
                # Last resort: everything is the task, default 5 min
                task = re.sub(
                    r"^(jarvis\s+)?remind\s+me\s+(?:to\s+)?",
                    "",
                    text_clean,
                    flags=re.IGNORECASE,
                ).strip()
                full_time_str = ""

        if not task:
            self.event_bus.publish(
                Event(
                    EventTypes.SPEAK_REQUEST,
                    {"text": "I'd love to set a reminder, but I didn't catch what you wanted to be reminded about."},
                )
            )
            return

        # Parse the time expression
        if full_time_str:
            trigger_time, is_recurring, recurrence = parse_time(full_time_str)
        else:
            # Default: 5 minutes from now
            trigger_time = datetime.now() + timedelta(minutes=5)
            is_recurring = False
            recurrence = None

        reminder_type = "recurring" if is_recurring else "one_time"
        reminder = self.add_reminder(task, trigger_time, recurrence, reminder_type)

        # Spoken confirmation
        time_desc = self._describe_time(trigger_time)
        if is_recurring:
            recur_desc = self._describe_recurrence(recurrence)
            confirmation = (
                f"Got it. I'll remind you to {task} {recur_desc}, "
                f"starting {time_desc}."
            )
        else:
            confirmation = f"Sure thing. I'll remind you to {task} at {time_desc}."

        self.event_bus.publish(
            Event(EventTypes.SPEAK_REQUEST, {"text": confirmation})
        )

        # Dashboard update
        self.event_bus.publish(
            Event(
                EventTypes.DASHBOARD_UPDATE,
                {
                    "panel": "reminders",
                    "action": "added",
                    "reminder": reminder.to_dict(),
                },
            )
        )

    def _handle_timer_command(self, raw_text: str):
        """
        Parse and handle: "set a timer for 10 minutes"
                          "timer for 5 minutes"
        """
        from ai_core.event_bus import Event, EventTypes

        text_lower = raw_text.lower()

        # Extract duration
        duration_match = re.search(
            r"(?P<num>\d+)\s+(?P<unit>seconds?|minutes?|hours?)",
            text_lower,
        )
        if duration_match:
            num = int(duration_match.group("num"))
            unit = duration_match.group("unit")
            if unit.startswith("second"):
                delta = timedelta(seconds=num)
            elif unit.startswith("minute"):
                delta = timedelta(minutes=num)
            elif unit.startswith("hour"):
                delta = timedelta(hours=num)
            else:
                delta = timedelta(minutes=num)

            trigger_time = datetime.now() + delta
            task = f"Timer: {num} {unit}"
            reminder = self.add_reminder(task, trigger_time, None, "timer")

            confirmation = (
                f"Timer set for {num} {unit}. "
                f"I'll alert you when it's done."
            )
            self.event_bus.publish(
                Event(EventTypes.SPEAK_REQUEST, {"text": confirmation})
            )
            self.event_bus.publish(
                Event(
                    EventTypes.DASHBOARD_UPDATE,
                    {
                        "panel": "reminders",
                        "action": "timer_added",
                        "reminder": reminder.to_dict(),
                    },
                )
            )
        else:
            self.event_bus.publish(
                Event(
                    EventTypes.SPEAK_REQUEST,
                    {"text": "How long should I set the timer for? For example, say 'set a timer for 10 minutes'."},
                )
            )

    def _handle_show_reminders(self):
        """List all active reminders."""
        from ai_core.event_bus import Event, EventTypes

        active = self.get_active_reminders()
        if not active:
            self.event_bus.publish(
                Event(
                    EventTypes.SPEAK_REQUEST,
                    {"text": "You have no active reminders."},
                )
            )
            return

        # Sort by trigger time
        active.sort(key=lambda r: r.effective_trigger)

        lines = [f"You have {len(active)} active reminder{'s' if len(active) != 1 else ''}:"]
        for i, r in enumerate(active, 1):
            time_desc = self._describe_time(r.effective_trigger)
            recur = ""
            if r.is_recurring:
                recur = f" ({self._describe_recurrence(r.recurring)})"
            lines.append(f"  {i}. {r.text} — {time_desc}{recur}")

        self.event_bus.publish(
            Event(EventTypes.SPEAK_REQUEST, {"text": " ".join(lines)})
        )
        self.event_bus.publish(
            Event(
                EventTypes.DASHBOARD_UPDATE,
                {
                    "panel": "reminders",
                    "action": "list",
                    "reminders": [r.to_dict() for r in active],
                },
            )
        )

    def _handle_clear_reminders(self):
        """Remove all reminders."""
        from ai_core.event_bus import Event, EventTypes

        with self._lock:
            count = len(self._reminders)
            self._reminders.clear()
        self._save_reminders()

        self.event_bus.publish(
            Event(
                EventTypes.SPEAK_REQUEST,
                {"text": f"Cleared all {count} reminder{'s' if count != 1 else ''}."},
            )
        )
        self.event_bus.publish(
            Event(
                EventTypes.DASHBOARD_UPDATE,
                {"panel": "reminders", "action": "cleared"},
            )
        )

    def _handle_cancel_reminder(self, raw_text: str):
        """
        Cancel a specific reminder by number or keyword.
        "cancel reminder 3" or "cancel reminder call Mom"
        """
        from ai_core.event_bus import Event, EventTypes

        text_lower = raw_text.lower()

        active = self.get_active_reminders()
        active.sort(key=lambda r: r.effective_trigger)

        # Try to extract a number
        num_match = re.search(r"(?:number\s+)?(\d+)", text_lower)
        if num_match:
            index = int(num_match.group(1)) - 1  # 1-based → 0-based
            if 0 <= index < len(active):
                reminder = active[index]
                self.remove_reminder(reminder.id)
                self.event_bus.publish(
                    Event(
                        EventTypes.SPEAK_REQUEST,
                        {"text": f"Cancelled reminder: {reminder.text}."},
                    )
                )
                return

        # Try keyword matching
        keyword = re.sub(
            r"^(jarvis\s+)?(cancel|remove|delete)\s+(reminder\s+)?",
            "",
            text_lower,
            flags=re.IGNORECASE,
        ).strip()
        if keyword:
            for r in active:
                if keyword in r.text.lower():
                    self.remove_reminder(r.id)
                    self.event_bus.publish(
                        Event(
                            EventTypes.SPEAK_REQUEST,
                            {"text": f"Cancelled reminder: {r.text}."},
                        )
                    )
                    return

        self.event_bus.publish(
            Event(
                EventTypes.SPEAK_REQUEST,
                {"text": "I couldn't find that reminder. Say 'show my reminders' to see them."},
            )
        )

    def _handle_schedule_command(self, raw_text: str):
        """Handle 'what's my schedule today' type commands."""
        from ai_core.event_bus import Event, EventTypes

        now = datetime.now()
        today_reminders = [
            r for r in self.get_active_reminders()
            if r.effective_trigger.date() == now.date()
        ]
        today_reminders.sort(key=lambda r: r.effective_trigger)

        if not today_reminders:
            self.event_bus.publish(
                Event(
                    EventTypes.SPEAK_REQUEST,
                    {"text": "Your schedule is clear for today. No reminders are set."},
                )
            )
            return

        lines = [f"Here's your schedule for today. You have {len(today_reminders)} item{'s' if len(today_reminders) != 1 else ''}:"]
        for r in today_reminders:
            t = r.effective_trigger.strftime("%I:%M %p")
            recur = f" (recurring)" if r.is_recurring else ""
            lines.append(f"  At {t}, {r.text}.{recur}")

        self.event_bus.publish(
            Event(EventTypes.SPEAK_REQUEST, {"text": " ".join(lines)})
        )

    # ==================================================================
    # Background checker
    # ==================================================================

    def _checker_loop(self):
        """
        Background thread that checks for due reminders every
        ``check_interval_seconds`` and fires them.
        """
        while self._running:
            try:
                self._check_and_fire_reminders()
            except Exception as e:
                print(f"[ReminderModule] Checker error: {e}")
            time.sleep(self._check_interval)

    def _check_and_fire_reminders(self):
        """Fire all reminders that are due now."""
        now = datetime.now()
        fired_ids = []

        with self._lock:
            reminders_to_check = list(self._reminders.values())

        for reminder in reminders_to_check:
            effective = reminder.effective_trigger

            # Check if it's time to fire
            if effective <= now and not (reminder.fired and not reminder.is_recurring):
                # Smart scheduling: skip during sleep hours
                if self._is_sleep_hours(now):
                    # Reschedule for the end of sleep
                    wake_time = now.replace(
                        hour=self._sleep_end, minute=0, second=0, microsecond=0
                    )
                    if wake_time <= now:
                        wake_time += timedelta(days=1)
                    reminder.snoozed_until = wake_time
                    print(
                        f"[ReminderModule] Snoozing '{reminder.text}' until "
                        f"{wake_time:%H:%M} (sleep hours)"
                    )
                    continue

                # Fire the reminder
                self._fire_reminder(reminder)
                fired_ids.append(reminder.id)

        if fired_ids:
            self._save_reminders()

    def _fire_reminder(self, reminder: Reminder):
        """Trigger a single reminder — speak it and update dashboard."""
        from ai_core.event_bus import Event, EventTypes

        user_name = self.prefs_config.get("user_name", "Sir")

        if reminder.reminder_type == "timer":
            speech = f"{user_name}, your timer is done! {reminder.text}."
        else:
            speech = (
                f"{user_name}, you asked me to remind you to {reminder.text}."
            )

        # Publish speak event
        self.event_bus.publish(
            Event(EventTypes.SPEAK_REQUEST, {"text": speech})
        )

        # Publish dashboard update
        self.event_bus.publish(
            Event(
                EventTypes.DASHBOARD_UPDATE,
                {
                    "panel": "reminders",
                    "action": "fired",
                    "reminder": reminder.to_dict(),
                    "message": speech,
                },
            )
        )

        print(f"[ReminderModule] FIRED: {reminder}")

        # Update state
        if reminder.is_recurring:
            # Compute next fire time
            next_time = next_fire_time(reminder.trigger_time, reminder.recurring)
            reminder.trigger_time = next_time
            reminder.snoozed_until = None
            # Keep fired=False for recurring so it fires again
        else:
            reminder.fired = True

    # ==================================================================
    # Daily briefing scheduler
    # ==================================================================

    def _briefing_scheduler_loop(self):
        """
        Background thread that triggers the daily briefing at the
        configured time each day.
        """
        while self._running:
            if not self._briefing_enabled:
                time.sleep(60)
                continue

            now = datetime.now()
            today_str = now.strftime("%Y-%m-%d")

            # Check if it's briefing time and we haven't fired today
            if (
                now.hour == self._briefing_hour
                and now.minute == self._briefing_minute
                and self._last_briefing_date != today_str
                and not self._is_sleep_hours(now)
            ):
                self._last_briefing_date = today_str
                try:
                    self.trigger_briefing()
                except Exception as e:
                    print(f"[ReminderModule] Briefing error: {e}")

            # Sleep for 30 seconds before checking again
            time.sleep(30)

    # ==================================================================
    # EventBus data subscribers (for briefing content)
    # ==================================================================

    def _on_news_updated(self, event):
        """Cache news headlines when they are updated."""
        headlines = event.data.get("headlines", [])
        if headlines:
            self._cached_news = headlines

    def _on_stocks_updated(self, event):
        """Cache stock data when it is updated."""
        stocks = event.data.get("stocks", {})
        if stocks:
            self._cached_stocks = stocks

    # ==================================================================
    # Persistence
    # ==================================================================

    def _load_reminders(self):
        """Load reminders from the JSON data file."""
        if not os.path.exists(self._data_file):
            print(f"[ReminderModule] No data file at {self._data_file} — starting fresh")
            return

        try:
            with open(self._data_file, "r") as f:
                data = json.load(f)

            loaded_count = 0
            for item in data.get("reminders", []):
                try:
                    r = Reminder.from_dict(item)
                    # Skip one-time reminders that already fired
                    if r.fired and not r.is_recurring:
                        continue
                    # Recompute trigger for recurring reminders that are in the past
                    if r.is_recurring and r.trigger_time < datetime.now():
                        while r.trigger_time < datetime.now():
                            r.trigger_time = next_fire_time(r.trigger_time, r.recurring)
                    self._reminders[r.id] = r
                    loaded_count += 1
                except Exception as e:
                    print(f"[ReminderModule] Skipping invalid reminder entry: {e}")

            print(f"[ReminderModule] Loaded {loaded_count} reminders from {self._data_file}")
        except (json.JSONDecodeError, OSError) as e:
            print(f"[ReminderModule] Error loading reminders: {e}")

    def _save_reminders(self):
        """Save reminders to the JSON data file."""
        # Ensure the directory exists
        dir_path = os.path.dirname(self._data_file)
        if dir_path:
            os.makedirs(dir_path, exist_ok=True)

        with self._lock:
            data = {
                "reminders": [
                    r.to_dict()
                    for r in self._reminders.values()
                    if not (r.fired and not r.is_recurring)
                ],
                "last_saved": datetime.now().isoformat(),
            }

        try:
            with open(self._data_file, "w") as f:
                json.dump(data, f, indent=2)
        except OSError as e:
            print(f"[ReminderModule] Error saving reminders: {e}")

    # ==================================================================
    # Utility helpers
    # ==================================================================

    def _is_sleep_hours(self, dt: datetime) -> bool:
        """
        Check if *dt* falls within configured sleep hours.

        Handles overnight spans, e.g. 23:00 → 07:00.
        """
        hour = dt.hour
        if self._sleep_start > self._sleep_end:
            # Overnight: e.g. 23 → 7 means 23,0,1,…,6 are sleep hours
            return hour >= self._sleep_start or hour < self._sleep_end
        else:
            # Same-day: e.g. 1 → 5 means 1,2,3,4 are sleep hours
            return self._sleep_start <= hour < self._sleep_end

    @staticmethod
    def _describe_time(dt: datetime) -> str:
        """Human-friendly description of a datetime for speech."""
        now = datetime.now()
        if dt.date() == now.date():
            return f"today at {dt.strftime('%I:%M %p')}"
        elif dt.date() == (now + timedelta(days=1)).date():
            return f"tomorrow at {dt.strftime('%I:%M %p')}"
        else:
            return dt.strftime("%A, %B %d at %I:%M %p")

    @staticmethod
    def _describe_recurrence(pattern: RecurrencePattern) -> str:
        """Human-friendly description of a recurrence pattern."""
        if pattern is None:
            return "once"
        if pattern == "daily":
            return "every day"
        if pattern == "weekly":
            return "every week"
        if isinstance(pattern, tuple) and pattern[0] == "interval":
            seconds = pattern[1]
            if seconds < 60:
                return f"every {seconds} seconds"
            elif seconds < 3600:
                minutes = seconds // 60
                return f"every {minutes} minute{'s' if minutes != 1 else ''}"
            else:
                hours = seconds // 3600
                return f"every {hours} hour{'s' if hours != 1 else ''}"
        return str(pattern)
