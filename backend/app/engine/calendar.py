"""Calendar-day and working-day date conversion.

Offset convention
-----------------
Early start and early finish are measured in day offsets from the project start.
Finish offset is exclusive: a task with ES=0 and duration=5 occupies offsets
[0, 5) and its finish-to-start successors may start at offset 5.

When weekends are skipped, offsets count working days only. Elapsed calendar
time can therefore exceed the numeric duration.
"""

from __future__ import annotations

import math
from datetime import date, timedelta

from app.engine.types import WorkCalendar


def _is_working_day(day: date, calendar: WorkCalendar) -> bool:
    if calendar.skip_weekends and day.weekday() >= 5:
        return False
    return day not in set(calendar.holiday_dates)


def _uses_plain_calendar(calendar: WorkCalendar) -> bool:
    return not calendar.skip_weekends and not calendar.holiday_dates


def add_days(start: date, offset: float, calendar: WorkCalendar) -> date:
    """Return the date `offset` counted days after `start`.

    Offset 0 is `start`. A positive fractional offset is rounded upward so the
    exclusive finish of a partial day falls on a real date.
    """

    if offset < -1e-9:
        raise ValueError("Negative day offsets are not supported.")
    if offset <= 1e-9:
        return start

    if _uses_plain_calendar(calendar):
        days = int(math.ceil(offset - 1e-9))
        return start + timedelta(days=days)

    remaining = int(math.ceil(offset - 1e-9))
    cursor = start
    while remaining > 0:
        cursor += timedelta(days=1)
        if _is_working_day(cursor, calendar):
            remaining -= 1
    return cursor


def inclusive_finish(start: date, exclusive_offset: float, calendar: WorkCalendar) -> date | None:
    """Last day occupied by a task. Zero-duration milestones return None."""

    if exclusive_offset <= 1e-9:
        return None
    exclusive = add_days(start, exclusive_offset, calendar)
    if _uses_plain_calendar(calendar):
        return exclusive - timedelta(days=1)

    cursor = exclusive
    while True:
        cursor -= timedelta(days=1)
        if cursor < start:
            return start
        if _is_working_day(cursor, calendar):
            return cursor
