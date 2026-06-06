"""
Time Parser - Natural language time parsing for reminders.

Converts human-readable time expressions into datetime objects
and recurrence patterns.  Uses dateutil.parser when available,
falling back to regex-based pattern matching.

Supported patterns:
    - "5pm" / "5:30 pm"       -> today at that time (or tomorrow if already past)
    - "tomorrow at 9am"       -> tomorrow 09:00
    - "in 30 minutes"         -> now + 30 min
    - "in 2 hours"            -> now + 2 h
    - "every day at 8am"      -> recurring daily
    - "every 2 hours"         -> recurring every 2 h
    - "every Monday at 10am"  -> recurring weekly
    - "next Monday at 3pm"    -> next occurrence of that weekday
    - "next week"             -> 7 days from now
    - "at 14:30"              -> today 14:30 (or tomorrow if past)

Returns:
    (trigger_datetime, is_recurring, recurrence_pattern)

    recurrence_pattern is one of:
        None                     -> one-time
        "daily"                  -> every day
        "weekly"                 -> every week (same weekday)
        ("interval", seconds)    -> every N seconds
"""

import re
from datetime import datetime, timedelta
from typing import Optional, Tuple, Union

# ---------------------------------------------------------------------------
# Try to import dateutil for flexible parsing; fall back gracefully.
# ---------------------------------------------------------------------------
try:
    from dateutil import parser as dateutil_parser
    from dateutil.relativedelta import relativedelta

    _HAS_DATEUTIL = True
except ImportError:
    _HAS_DATEUTIL = False

# ---------------------------------------------------------------------------
# Weekday name -> weekday index (0=Monday … 6=Sunday)
# ---------------------------------------------------------------------------
_WEEKDAY_MAP: dict[str, int] = {
    "monday": 0, "mon": 0,
    "tuesday": 1, "tue": 1, "tues": 1,
    "wednesday": 2, "wed": 2,
    "thursday": 3, "thu": 3, "thur": 3, "thurs": 3,
    "friday": 4, "fri": 4,
    "saturday": 5, "sat": 5,
    "sunday": 6, "sun": 6,
}

# Recurrence pattern type alias
RecurrencePattern = Optional[Union[str, Tuple[str, int]]]


def parse_time(text: str) -> Tuple[datetime, bool, RecurrencePattern]:
    """
    Parse a natural-language time expression.

    Args:
        text: Human-readable time string, e.g. "5pm", "in 30 minutes",
              "every day at 8am", "next Monday at 3pm".

    Returns:
        A 3-tuple (trigger_datetime, is_recurring, recurrence_pattern).

        * trigger_datetime  - The first time the reminder should fire.
        * is_recurring      - True if the reminder repeats.
        * recurrence_pattern - Describes how it repeats:
            None                   -> one-time
            "daily"                -> every day at the same time
            "weekly"               -> every week on the same weekday
            ("interval", seconds)  -> every N seconds
    """
    if not text or not text.strip():
        return datetime.now(), False, None

    original = text.strip()
    lowered = original.lower()

    # ------------------------------------------------------------------
    # 1. Recurring patterns  ("every …")
    # ------------------------------------------------------------------
    recurring_match = re.match(
        r"every\s+(?P<rest>.+)", lowered
    )
    if recurring_match:
        return _parse_recurring(recurring_match.group("rest").strip())

    # ------------------------------------------------------------------
    # 2. Relative patterns  ("in X minutes/hours")
    # ------------------------------------------------------------------
    relative_match = re.match(
        r"in\s+(?P<num>\d+)\s+(?P<unit>seconds?|minutes?|hours?)",
        lowered,
    )
    if relative_match:
        num = int(relative_match.group("num"))
        unit = relative_match.group("unit")
        delta = _make_timedelta(num, unit)
        return datetime.now() + delta, False, None

    # ------------------------------------------------------------------
    # 3. "next <weekday>" or "next week"
    # ------------------------------------------------------------------
    next_match = re.match(
        r"next\s+(?P<target>week|monday|tuesday|wednesday|thursday|friday|saturday|sunday"
        r"|mon|tue|wed|thu|fri|sat|sun)\s*(?:at\s+)?(?P<time>.*)?",
        lowered,
    )
    if next_match:
        return _parse_next(next_match.group("target").strip(),
                           next_match.group("time") or "")

    # ------------------------------------------------------------------
    # 4. "tomorrow at <time>"
    # ------------------------------------------------------------------
    tomorrow_match = re.match(
        r"tomorrow\s+(?:at\s+)?(?P<time>.+)", lowered
    )
    if tomorrow_match:
        time_part = tomorrow_match.group("time").strip()
        target_time = _parse_time_of_day(time_part)
        if target_time is None:
            target_time = datetime.now().replace(
                hour=9, minute=0, second=0, microsecond=0
            )
        tomorrow = datetime.now().replace(
            hour=target_time.hour,
            minute=target_time.minute,
            second=0,
            microsecond=0,
        ) + timedelta(days=1)
        return tomorrow, False, None

    # ------------------------------------------------------------------
    # 5. Bare time-of-day  ("5pm", "at 9am", "14:30")
    # ------------------------------------------------------------------
    time_only = lowered.lstrip("at ").strip()
    target_time = _parse_time_of_day(time_only)
    if target_time is not None:
        candidate = datetime.now().replace(
            hour=target_time.hour,
            minute=target_time.minute,
            second=0,
            microsecond=0,
        )
        # If the time has already passed today, schedule for tomorrow
        if candidate <= datetime.now():
            candidate += timedelta(days=1)
        return candidate, False, None

    # ------------------------------------------------------------------
    # 6. Fallback: try dateutil parser if available
    # ------------------------------------------------------------------
    if _HAS_DATEUTIL:
        try:
            parsed = dateutil_parser.parse(
                original,
                fuzzy=True,
                default=datetime.now().replace(
                    second=0, microsecond=0
                ),
            )
            if parsed <= datetime.now():
                parsed += timedelta(days=1)
            return parsed, False, None
        except (ValueError, OverflowError):
            pass

    # ------------------------------------------------------------------
    # 7. Ultimate fallback: 5 minutes from now
    # ------------------------------------------------------------------
    print(f"[TimeParser] Could not parse time expression: '{original}' — defaulting to 5 min from now")
    return datetime.now() + timedelta(minutes=5), False, None


# ======================================================================
# Internal helpers
# ======================================================================

def _parse_recurring(rest: str) -> Tuple[datetime, bool, RecurrencePattern]:
    """Handle 'every …' patterns."""
    now = datetime.now()

    # "every day at 8am"
    day_match = re.match(r"(?:day|daily)\s+(?:at\s+)?(?P<time>.+)", rest)
    if day_match:
        target_time = _parse_time_of_day(day_match.group("time").strip())
        if target_time is None:
            target_time = now.replace(hour=8, minute=0, second=0, microsecond=0)
        candidate = now.replace(
            hour=target_time.hour,
            minute=target_time.minute,
            second=0,
            microsecond=0,
        )
        if candidate <= now:
            candidate += timedelta(days=1)
        return candidate, True, "daily"

    # "every N hours/minutes"
    interval_match = re.match(
        r"(?P<num>\d+)\s+(?P<unit>hours?|minutes?)", rest
    )
    if interval_match:
        num = int(interval_match.group("num"))
        unit = interval_match.group("unit")
        delta = _make_timedelta(num, unit)
        return now + delta, True, ("interval", int(delta.total_seconds()))

    # "every hour" / "every minute"
    single_interval_match = re.match(r"(?P<unit>hour|minute)", rest)
    if single_interval_match:
        unit = single_interval_match.group("unit")
        delta = _make_timedelta(1, unit)
        return now + delta, True, ("interval", int(delta.total_seconds()))

    # "every Monday/Tuesday/… at <time>"
    weekday_match = re.match(
        r"(?P<day>monday|tuesday|wednesday|thursday|friday|saturday|sunday"
        r"|mon|tue|wed|thu|fri|sat|sun)\s+(?:at\s+)?(?P<time>.*)?",
        rest,
    )
    if weekday_match:
        day_name = weekday_match.group("day").strip()
        time_part = (weekday_match.group("time") or "").strip()
        target_weekday = _WEEKDAY_MAP.get(day_name)
        if target_weekday is not None:
            target_time = _parse_time_of_day(time_part) if time_part else None
            if target_time is None:
                target_time = now.replace(hour=9, minute=0, second=0, microsecond=0)
            candidate = _next_weekday(now, target_weekday, target_time.hour, target_time.minute)
            return candidate, True, "weekly"

    # "every morning" / "every evening" / "every afternoon"
    period_match = re.match(
        r"(?P<period>morning|afternoon|evening|night)", rest
    )
    if period_match:
        period = period_match.group("period")
        hour_map = {"morning": 8, "afternoon": 14, "evening": 18, "night": 21}
        hour = hour_map.get(period, 8)
        candidate = now.replace(hour=hour, minute=0, second=0, microsecond=0)
        if candidate <= now:
            candidate += timedelta(days=1)
        return candidate, True, "daily"

    # Generic "every …" fallback: treat as daily at the parsed time
    target_time = _parse_time_of_day(rest)
    if target_time is not None:
        candidate = now.replace(
            hour=target_time.hour,
            minute=target_time.minute,
            second=0,
            microsecond=0,
        )
        if candidate <= now:
            candidate += timedelta(days=1)
        return candidate, True, "daily"

    # Complete fallback
    print(f"[TimeParser] Could not parse recurring expression: 'every {rest}' — defaulting to daily at 8 AM")
    candidate = now.replace(hour=8, minute=0, second=0, microsecond=0)
    if candidate <= now:
        candidate += timedelta(days=1)
    return candidate, True, "daily"


def _parse_next(target: str, time_str: str) -> Tuple[datetime, bool, RecurrencePattern]:
    """Handle 'next <weekday/week>' patterns."""
    now = datetime.now()

    if target == "week":
        target_time = _parse_time_of_day(time_str.strip()) if time_str.strip() else None
        if target_time is None:
            candidate = now + timedelta(days=7)
        else:
            candidate = (now + timedelta(days=7)).replace(
                hour=target_time.hour,
                minute=target_time.minute,
                second=0,
                microsecond=0,
            )
        return candidate, False, None

    weekday_idx = _WEEKDAY_MAP.get(target)
    if weekday_idx is not None:
        target_time = _parse_time_of_day(time_str.strip()) if time_str.strip() else None
        if target_time is None:
            target_time = now.replace(hour=9, minute=0, second=0, microsecond=0)
        candidate = _next_weekday(now, weekday_idx, target_time.hour, target_time.minute)
        return candidate, False, None

    # Fallback
    return now + timedelta(days=1), False, None


def _parse_time_of_day(text: str) -> Optional[datetime]:
    """
    Parse a bare time-of-day string like '5pm', '5:30 pm', '14:30', '9am'.

    Returns a datetime object with today's date and the parsed time,
    or None if parsing fails.
    """
    if not text or not text.strip():
        return None

    text = text.strip()

    # "5:30pm" / "5:30 pm" / "5pm" / "5 pm"
    match = re.match(
        r"(?P<hour>\d{1,2}):?(?P<min>\d{2})?\s*(?P<ampm>am|pm|a\.m\.|p\.m\.)?",
        text,
        re.IGNORECASE,
    )
    if match:
        hour = int(match.group("hour"))
        minute = int(match.group("min") or 0)
        ampm = (match.group("ampm") or "").lower().replace(".", "")

        if ampm == "pm" and hour != 12:
            hour += 12
        elif ampm == "am" and hour == 12:
            hour = 0
        elif ampm == "" and 1 <= hour <= 6:
            # Ambiguous — assume PM for small numbers
            hour += 12

        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return datetime.now().replace(
                hour=hour, minute=minute, second=0, microsecond=0
            )

    # Try dateutil as a fallback
    if _HAS_DATEUTIL:
        try:
            parsed = dateutil_parser.parse(
                text,
                fuzzy=True,
                default=datetime.now().replace(second=0, microsecond=0),
            )
            return parsed
        except (ValueError, OverflowError):
            pass

    return None


def _next_weekday(
    from_date: datetime, weekday: int, hour: int = 9, minute: int = 0
) -> datetime:
    """
    Return the next occurrence of *weekday* (0=Mon … 6=Sun) at the
    given hour:minute, starting from *from_date*.
    """
    days_ahead = weekday - from_date.weekday()
    if days_ahead <= 0:
        days_ahead += 7
    target = from_date + timedelta(days=days_ahead)
    return target.replace(hour=hour, minute=minute, second=0, microsecond=0)


def _make_timedelta(num: int, unit: str) -> timedelta:
    """Convert a number + unit string into a timedelta."""
    unit_lower = unit.lower()
    if unit_lower.startswith("second"):
        return timedelta(seconds=num)
    elif unit_lower.startswith("minute"):
        return timedelta(minutes=num)
    elif unit_lower.startswith("hour"):
        return timedelta(hours=num)
    else:
        return timedelta(minutes=num)


# ======================================================================
# Convenience: compute the next fire time for a recurring reminder
# ======================================================================

def next_fire_time(
    last_fire: datetime,
    recurrence: RecurrencePattern,
) -> datetime:
    """
    Given the last fire time and a recurrence pattern, compute the
    next fire time.
    """
    if recurrence == "daily":
        return last_fire + timedelta(days=1)

    if recurrence == "weekly":
        return last_fire + timedelta(weeks=1)

    if isinstance(recurrence, tuple) and recurrence[0] == "interval":
        return last_fire + timedelta(seconds=recurrence[1])

    # Shouldn't happen for one-time reminders, but handle gracefully
    return last_fire + timedelta(days=1)
