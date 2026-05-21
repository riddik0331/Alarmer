"""Helper / utility functions used across the application.

Most functions are pure (no Qt or GUI dependencies), with the exception of
``center_on_screen`` which requires PySide6.QtWidgets.QWidget.
"""

import uuid
from datetime import datetime, timedelta
from typing import Any, Optional

import re

# ---------------------------------------------------------------------------
# Identifier generation
# ---------------------------------------------------------------------------


def generate_id() -> str:
    """Return a new UUID v4 string."""
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Time-string validation
# ---------------------------------------------------------------------------
_TIME_PATTERN = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


def validate_time(time_str: str) -> bool:
    """Check whether *time_str* is a valid "HH:MM" (24-hour) string.

    Args:
        time_str: Candidate time string.

    Returns:
        ``True`` if the string matches ``HH:MM`` with valid hour/minute ranges.
    """
    return bool(_TIME_PATTERN.match(time_str))


# ---------------------------------------------------------------------------
# Current-time comparison  (≈30 s tolerance)
# ---------------------------------------------------------------------------


def is_time_match(alarm_time: str) -> bool:
    """Return ``True`` if *alarm_time* matches the current system time ±30 seconds.

    Args:
        alarm_time: Time string in "HH:MM" format.

    Returns:
        ``True`` when the absolute difference between now and the
        alarm time is ≤ 30 seconds.
    """
    if not validate_time(alarm_time):
        return False

    now = datetime.now()
    try:
        alarm_dt = now.replace(hour=int(alarm_time[:2]), minute=int(alarm_time[3:]), second=0, microsecond=0)
    except ValueError:
        return False

    diff = abs((now - alarm_dt).total_seconds())
    return diff <= 30.0


# ---------------------------------------------------------------------------
# Time arithmetic
# ---------------------------------------------------------------------------


def time_from_now(minutes: int) -> str:
    """Return the "HH:MM" string *minutes* from the current system time.

    Args:
        minutes: How many minutes to add (may be negative or zero).

    Returns:
        A formatted time string like ``"14:05"``.
    """
    future = datetime.now() + timedelta(minutes=minutes)
    return future.strftime("%H:%M")


# ---------------------------------------------------------------------------
# Day-of-week helpers  (ISO: 1=Monday … 7=Sunday)
# ---------------------------------------------------------------------------


def format_days(days: list[int], locale: str = "ru") -> str:
    """Produce a short human-readable day-of-week string.

    Args:
        days: List of ISO weekday numbers (1=Monday … 7=Sunday).
        locale: Language (``"ru"`` supported).

    Returns:
        A space-separated string like ``"Пн Ср Пт"``,
        or ``"Каждый день"`` when all seven days are present,
        or a single day name when only one is given.
    """
    names_ru = ["", "Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]

    if not days:
        return ""

    if locale == "ru":
        labels = names_ru
    else:
        labels = ["", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

    # Sort to keep order
    sorted_days = sorted(d for d in days if 1 <= d <= 7)

    if len(sorted_days) == 7:
        return "Каждый день"

    return " ".join(labels[d] for d in sorted_days)


# ---------------------------------------------------------------------------
# Value clamping
# ---------------------------------------------------------------------------


def clamp(value: int, low: int, high: int) -> int:
    """Clamp *value* to the inclusive range ``[low, high]``."""
    return max(low, min(high, value))


# ---------------------------------------------------------------------------
# Current weekday  (ISO)
# ---------------------------------------------------------------------------


def current_weekday() -> int:
    """Return the current ISO weekday (1=Monday … 7=Sunday)."""
    return datetime.now().isoweekday()


# ---------------------------------------------------------------------------
# Centering a widget on the primary screen
# ---------------------------------------------------------------------------


def center_on_screen(widget: "Any") -> None:  # noqa: ANN401
    """Center *widget* on the primary screen's available geometry.

    Args:
        widget: A QWidget (or QDialog / QMainWindow) to be centered.
    """
    from PySide6.QtWidgets import QWidget  # noqa: PLC0415

    if not isinstance(widget, QWidget):
        return
    screen = widget.screen()
    if screen is not None:
        geometry = screen.availableGeometry()
        x = (geometry.width() - widget.width()) // 2 + geometry.x()
        y = (geometry.height() - widget.height()) // 2 + geometry.y()
        widget.move(x, y)
