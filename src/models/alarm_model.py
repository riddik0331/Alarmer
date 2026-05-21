"""Alarm data model — a dataclass representing a single alarm clock entry.

Provides serialisation / deserialisation to/from dictionaries for JSON
persistence, and helpers for checking whether the alarm should ring.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from src.utils.helpers import format_days, generate_id, validate_time


@dataclass
class Alarm:
    """A single alarm clock entry.

    Attributes:
        id:            Unique identifier (UUID v4).
        enabled:       Whether the alarm is active.
        title:         Optional user-assigned label.
        time:          Alarm time in "HH:MM" (24-hour) format.
        days:          ISO weekday numbers 1=Monday … 7=Sunday.
                       Empty list means ``once`` mode.
        once:          ``True`` = one-shot alarm (ignores *days*).
        sound_source:  ``"builtin"`` or ``"file"``.
        sound_name:    Key into ``BUILTIN_SOUNDS`` (used when *sound_source* is ``"builtin"``).
        sound_file:    Absolute path to a user-supplied sound file, or ``None``.
        volume:        Volume level 0–100.
        fade_in:       ``True`` = gradually increase volume over 30 s.
        snoozed_until: "HH:MM" string when snoozed, or ``None``.
    """

    id: str = ""
    enabled: bool = True
    title: str = ""
    time: str = "08:00"
    days: list[int] = field(default_factory=list)
    once: bool = True
    sound_source: str = "builtin"
    sound_name: str = "classic"
    sound_file: Optional[str] = None
    volume: int = 80
    fade_in: bool = False
    snoozed_until: Optional[str] = None

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Serialise this alarm to a JSON-compatible dictionary."""
        return {
            "id": self.id,
            "enabled": self.enabled,
            "title": self.title,
            "time": self.time,
            "days": list(self.days),
            "once": self.once,
            "sound_source": self.sound_source,
            "sound_name": self.sound_name,
            "sound_file": self.sound_file,
            "volume": self.volume,
            "fade_in": self.fade_in,
            "snoozed_until": self.snoozed_until,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Alarm:
        """Create an ``Alarm`` from a dictionary (deserialisation).

        Missing keys are filled with defaults.
        """
        return cls(
            id=str(data.get("id", generate_id())),
            enabled=bool(data.get("enabled", True)),
            title=str(data.get("title", "")),
            time=str(data.get("time", "08:00")),
            days=list(data.get("days", [])),
            once=bool(data.get("once", True)),
            sound_source=str(data.get("sound_source", "builtin")),
            sound_name=str(data.get("sound_name", "classic")),
            sound_file=data.get("sound_file"),  # keep None
            volume=int(data.get("volume", 80)),
            fade_in=bool(data.get("fade_in", False)),
            snoozed_until=data.get("snoozed_until"),  # keep None
        )

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def is_repeating(self) -> bool:
        """Return ``True`` when this alarm is *not* a one-shot."""
        return not self.once

    def get_days_display(self, locale: str = "ru") -> str:
        """Return a human-readable representation of the alarm schedule.

        Args:
            locale: Language code (``"ru"`` supported).

        Returns:
            e.g. ``"Пн Вт Ср"``, ``"Единоразово"``, or ``"Каждый день"``.
        """
        if self.once or not self.days:
            return "Единоразово"
        return format_days(self.days, locale=locale)

    def should_ring(self, current_time_str: str, current_weekday: int) -> bool:
        """Determine whether this alarm should ring at the given moment.

        Args:
            current_time_str:  Current time as ``"HH:MM"``.
            current_weekday:   Current ISO weekday (1=Monday … 7=Sunday).

        Returns:
            ``True`` if the alarm is enabled, time matches, snooze is not
            active, and the day condition (once / weekday) is satisfied.
        """
        if not self.enabled:
            return False

        if not validate_time(current_time_str):
            return False

        if self.time != current_time_str:
            return False

        # Snoozed alarms are skipped
        if self.snoozed_until is not None:
            return False

        # Day check
        if self.once:
            return True

        return current_weekday in self.days

    # ------------------------------------------------------------------
    # Ordering
    # ------------------------------------------------------------------

    def __lt__(self, other: Alarm) -> bool:
        """Support sorting by alarm time."""
        if not isinstance(other, Alarm):
            return NotImplemented
        return self.time < other.time

