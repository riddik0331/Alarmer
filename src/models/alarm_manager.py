"""AlarmManager — the central business-logic model for alarm CRUD, JSON
persistence, and periodic alarm checking via a background QTimer.

Emits Qt signals so that controllers / views can react reactively.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Optional

from PySide6.QtCore import QObject, QTimer, Signal

from src.models.alarm_model import Alarm
from src.utils.constants import CHECK_INTERVAL, JSON_VERSION
from src.utils.helpers import generate_id, validate_time
from src.utils.storage import Storage

logger = logging.getLogger(__name__)


class AlarmManager(QObject):
    """Manages the list of alarms: CRUD, JSON I/O, and a periodic check timer.

    Signals:
        alarms_changed:  Emitted whenever the alarm list is mutated.
        alarm_triggered: Emitted when an alarm's time condition is met.
    """

    # ------------------------------------------------------------------
    # Signals
    # ------------------------------------------------------------------
    alarms_changed = Signal()
    alarm_triggered = Signal(Alarm)  # noqa: SIG

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def __init__(self, storage: Storage, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._storage = storage
        self._alarms: list[Alarm] = []
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_timer)

        self.load()
        self._timer.start(CHECK_INTERVAL * 1000)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def load(self) -> None:
        """Load alarms from the JSON file.  Falls back to an empty list on error."""
        filepath = self._storage.get_alarms_file()
        try:
            raw = self._storage.read_json(filepath)
            alarms_data = raw.get("alarms", []) if isinstance(raw, dict) else []
        except (FileNotFoundError, json.JSONDecodeError):
            logger.info("No alarms file found — starting with an empty list.")
            self._alarms = []
            return
        except Exception as exc:
            logger.error("Unexpected error loading alarms: %s", exc)
            self._alarms = []
            return

        loaded: list[Alarm] = []
        for item in alarms_data:
            if not self._validate_alarm_dict(item):
                logger.warning("Skipping invalid alarm entry: %s", item.get("id", "<no-id>"))
                continue
            alarm = Alarm.from_dict(item)
            # Clear expired snoozes
            if alarm.snoozed_until is not None:
                if not self._is_snooze_active(alarm.snoozed_until):
                    alarm.snoozed_until = None
            loaded.append(alarm)

        loaded.sort()
        self._alarms = loaded

    def save(self) -> None:
        """Atomically persist the current alarm list to the JSON file."""
        filepath = self._storage.get_alarms_file()
        payload = {
            "version": JSON_VERSION,
            "alarms": [a.to_dict() for a in self._alarms],
        }
        self._storage.atomic_save(filepath, payload)

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get_alarms(self) -> list[Alarm]:
        """Return a sorted copy of the current alarm list."""
        return sorted(self._alarms)

    def get_alarm_by_id(self, alarm_id: str) -> Optional[Alarm]:
        """Look up an alarm by its UUID.

        Returns:
            The matching ``Alarm`` or ``None``.
        """
        for a in self._alarms:
            if a.id == alarm_id:
                return a
        return None

    # ------------------------------------------------------------------
    # Mutations  (all emit ``alarms_changed`` after saving)
    # ------------------------------------------------------------------

    def add_alarm(self, alarm: Alarm) -> None:
        """Add a new alarm, persist, and emit ``alarms_changed``."""
        if not alarm.id:
            alarm.id = generate_id()
        self._alarms.append(alarm)
        self._alarms.sort()
        self.save()
        self.alarms_changed.emit()

    def update_alarm(self, alarm: Alarm) -> None:
        """Replace an existing alarm (matched by id), persist, emit."""
        for i, a in enumerate(self._alarms):
            if a.id == alarm.id:
                self._alarms[i] = alarm
                self._alarms.sort()
                self.save()
                self.alarms_changed.emit()
                return

    def delete_alarm(self, alarm_id: str) -> None:
        """Remove an alarm by id, persist, emit."""
        self._alarms = [a for a in self._alarms if a.id != alarm_id]
        self.save()
        self.alarms_changed.emit()

    def toggle_alarm(self, alarm_id: str, enabled: bool) -> None:
        """Set the *enabled* flag for an alarm, persist, emit."""
        alarm = self.get_alarm_by_id(alarm_id)
        if alarm is not None:
            alarm.enabled = enabled
            self.save()
            self.alarms_changed.emit()

    # ------------------------------------------------------------------
    # Snooze
    # ------------------------------------------------------------------

    def snooze_alarm(self, alarm_id: str, minutes: int) -> None:
        """Set ``snoozed_until`` for the given alarm and persist.

        Re-enables the alarm if it was disabled by a one-shot firing,
        so it can ring again after the snooze period.

        Args:
            alarm_id: Target alarm id.
            minutes:  How many minutes from now to postpone.
        """
        alarm = self.get_alarm_by_id(alarm_id)
        if alarm is None:
            return
        from src.utils.helpers import time_from_now

        alarm.snoozed_until = time_from_now(minutes)
        alarm.enabled = True  # re-enable (was turned off by once-shot logic)
        self.save()
        self.alarms_changed.emit()

    # ------------------------------------------------------------------
    # Compatibility aliases (used by existing controllers)
    # ------------------------------------------------------------------

    def get_by_id(self, alarm_id: str) -> Optional[Alarm]:
        """Alias for ``get_alarm_by_id`` — used by existing controllers."""
        return self.get_alarm_by_id(alarm_id)

    def get_all(self) -> list[Alarm]:
        """Alias for ``get_alarms`` — used by existing controllers."""
        return self.get_alarms()

    def add(self, alarm: Alarm) -> None:
        """Alias for ``add_alarm`` — used by existing controllers."""
        self.add_alarm(alarm)

    def remove(self, alarm_id: str) -> None:
        """Alias for ``delete_alarm`` — used by existing controllers."""
        self.delete_alarm(alarm_id)

    def update(self, alarm: Alarm) -> None:
        """Alias for ``update_alarm`` — used by existing controllers."""
        self.update_alarm(alarm)

    def toggle(self, alarm_id: str) -> None:
        """Toggle the enabled state of an alarm (flip current state).

        Used by existing controllers that only pass the id.
        """
        alarm = self.get_alarm_by_id(alarm_id)
        if alarm is not None:
            alarm.enabled = not alarm.enabled
            self.save()
            self.alarms_changed.emit()

    def snooze(self, alarm_id: str, minutes: int) -> None:
        """Alias for ``snooze_alarm`` — used by existing controllers."""
        self.snooze_alarm(alarm_id, minutes)

    # ------------------------------------------------------------------
    # Periodic check
    # ------------------------------------------------------------------

    def check_alarms(self) -> None:
        """Evaluate every enabled alarm against the current time.

        An alarm whose *time* matches the current ``HH:MM`` and whose day
        condition is satisfied will emit ``alarm_triggered``.

        If an alarm's snooze has just expired, it is triggered immediately
        regardless of the original alarm time, as long as it is still
        enabled and the day condition (for repeating alarms) is met.

        One-shot alarms are automatically disabled after firing.
        """
        now = datetime.now()
        current_time = now.strftime("%H:%M")
        current_weekday = now.isoweekday()  # 1=Monday … 7=Sunday
        changed = False

        for alarm in self._alarms:
            snooze_just_expired = False

            # Clear expired snoozes
            if alarm.snoozed_until is not None:
                if not self._is_snooze_active(alarm.snoozed_until):
                    alarm.snoozed_until = None
                    snooze_just_expired = True
                    changed = True

            if not alarm.enabled:
                continue

            # Snooze just expired → trigger regardless of original time
            if snooze_just_expired:
                if alarm.once or current_weekday in alarm.days:
                    logger.info("Alarm triggered (snooze): %s (%s)", alarm.id, alarm.time)
                    self.alarm_triggered.emit(alarm)
                    if alarm.once:
                        alarm.enabled = False
                    self.save()
                    self.alarms_changed.emit()
                continue

            # Normal check: time and day match
            if not alarm.should_ring(current_time, current_weekday):
                continue

            logger.info("Alarm triggered: %s (%s)", alarm.id, alarm.time)
            self.alarm_triggered.emit(alarm)

            if alarm.once:
                alarm.enabled = False
                self.save()
                self.alarms_changed.emit()

        # Persist if any snoozes were cleared (without triggering)
        if changed:
            self.save()
            self.alarms_changed.emit()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _on_timer(self) -> None:
        """Slot called by the periodic QTimer."""
        self.check_alarms()

    @staticmethod
    def _validate_alarm_dict(data: dict) -> bool:
        """Basic sanity check for a deserialised alarm dictionary."""
        required = {"id", "enabled", "time", "days", "once", "sound_source", "volume", "fade_in"}
        if not required.issubset(data.keys()):
            return False
        time_val = data.get("time", "")
        if not isinstance(time_val, str) or not validate_time(time_val):
            return False
        return True

    @staticmethod
    def _is_snooze_active(snoozed_until: str) -> bool:
        """Return ``True`` if the snoozed time is still in the future."""
        if not validate_time(snoozed_until):
            return False
        now = datetime.now()
        try:
            snooze_dt = now.replace(
                hour=int(snoozed_until[:2]),
                minute=int(snoozed_until[3:]),
                second=0,
                microsecond=0,
            )
        except ValueError:
            return False
        # If snooze time > now, it's still active
        return snooze_dt > now

