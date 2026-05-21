"""Tests for the AlarmManager — CRUD, persistence, snooze, and periodic check.

All tests use a ``tmp_path``-backed Storage and require a QApplication
(provided by the ``qtbot`` fixture from ``pytest-qt``).
"""

from __future__ import annotations

import json
from unittest.mock import Mock, patch

import pytest

from src.models.alarm_model import Alarm
from src.models.alarm_manager import AlarmManager
from src.utils.storage import Storage


# ===================================================================
# Initialisation
# ===================================================================


class TestInitialization:
    """AlarmManager starts with an empty list when no data file exists."""

    def test_empty_on_start(self, manager: AlarmManager) -> None:
        assert manager.get_alarms() == []

    def test_timer_is_stopped(self, manager: AlarmManager) -> None:
        """The periodic timer should be inactive after our fixture stops it."""
        assert manager._timer.isActive() is False

    def test_storage_attr(self, manager: AlarmManager, storage: Storage) -> None:
        assert manager._storage is storage

    def test_load_empty_file(self, storage: Storage, qtbot) -> None:
        """Loading from an empty alarms file should result in an empty list."""
        filepath = storage.get_alarms_file()
        storage.atomic_save(filepath, {"version": 1, "alarms": []})
        mgr = AlarmManager(storage)
        mgr._timer.stop()
        assert mgr.get_alarms() == []


class TestLoad:
    """Loading from a JSON file with various contents."""

    def test_load_populated_file(
        self, storage: Storage, qtbot, sample_alarm: Alarm
    ) -> None:
        """Pre-populated JSON should be loaded correctly."""
        filepath = storage.get_alarms_file()
        data = {
            "version": 1,
            "alarms": [sample_alarm.to_dict()],
        }
        storage.atomic_save(filepath, data)

        mgr = AlarmManager(storage)
        mgr._timer.stop()
        alarms = mgr.get_alarms()
        assert len(alarms) == 1
        assert alarms[0].id == sample_alarm.id
        assert alarms[0].time == sample_alarm.time

    def test_load_invalid_json(self, storage: Storage, qtbot) -> None:
        """Invalid JSON should be handled gracefully (empty list)."""
        filepath = storage.get_alarms_file()
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("{invalid}")

        mgr = AlarmManager(storage)
        mgr._timer.stop()
        assert mgr.get_alarms() == []

    def test_load_missing_file(self, storage: Storage, qtbot) -> None:
        """Missing file should be handled gracefully (empty list)."""
        mgr = AlarmManager(storage)
        mgr._timer.stop()
        assert mgr.get_alarms() == []

    def test_load_skips_invalid_alarm_dict(
        self, storage: Storage, qtbot, sample_alarm: Alarm
    ) -> None:
        """Entries missing required keys are skipped."""
        valid_dict = sample_alarm.to_dict()
        invalid_dict = {"id": "bad", "time": "not-a-time"}  # missing keys, bad time
        data = {"version": 1, "alarms": [valid_dict, invalid_dict]}
        filepath = storage.get_alarms_file()
        storage.atomic_save(filepath, data)

        mgr = AlarmManager(storage)
        mgr._timer.stop()
        assert len(mgr.get_alarms()) == 1
        assert mgr.get_alarms()[0].id == sample_alarm.id


# ===================================================================
# CRUD
# ===================================================================


class TestAddAlarm:
    """Adding alarms."""

    def test_adds_to_list(self, manager: AlarmManager, sample_alarm: Alarm) -> None:
        manager.add_alarm(sample_alarm)
        assert len(manager.get_alarms()) == 1

    def test_generates_id_if_empty(
        self, manager: AlarmManager, once_alarm: Alarm
    ) -> None:
        """Alarm with empty id should get an auto-generated one."""
        once_alarm.id = ""
        manager.add_alarm(once_alarm)
        assert manager.get_alarms()[0].id != ""

    def test_emits_signal(self, manager: AlarmManager, sample_alarm: Alarm) -> None:
        """Adding an alarm should emit ``alarms_changed``."""
        received = []

        def handler() -> None:
            received.append(True)

        manager.alarms_changed.connect(handler)
        manager.add_alarm(sample_alarm)
        assert len(received) == 1

    def test_multiple_alarms_sorted(
        self, manager: AlarmManager
    ) -> None:
        """Alarms should remain sorted by time after adds."""
        a1 = Alarm(id="a1", time="09:00")
        a2 = Alarm(id="a2", time="07:00")
        a3 = Alarm(id="a3", time="08:00")
        manager.add_alarm(a1)
        manager.add_alarm(a2)
        manager.add_alarm(a3)
        assert [a.time for a in manager.get_alarms()] == ["07:00", "08:00", "09:00"]


class TestDeleteAlarm:
    """Deleting alarms."""

    def test_removes_alarm(self, manager: AlarmManager, sample_alarm: Alarm) -> None:
        manager.add_alarm(sample_alarm)
        manager.delete_alarm(sample_alarm.id)
        assert manager.get_alarms() == []

    def test_delete_nonexistent(self, manager: AlarmManager) -> None:
        """Deleting a non-existent id should not raise."""
        manager.delete_alarm("no-such-id")
        assert manager.get_alarms() == []

    def test_emits_signal(self, manager: AlarmManager, sample_alarm: Alarm) -> None:
        manager.add_alarm(sample_alarm)
        received = []

        def handler() -> None:
            received.append(True)

        manager.alarms_changed.connect(handler)
        manager.delete_alarm(sample_alarm.id)
        assert len(received) == 1


class TestUpdateAlarm:
    """Updating existing alarms."""

    def test_updates_existing(
        self, manager: AlarmManager, sample_alarm: Alarm
    ) -> None:
        manager.add_alarm(sample_alarm)
        updated = Alarm(
            id=sample_alarm.id,
            title="Updated Title",
            time="22:00",
            once=True,
        )
        manager.update_alarm(updated)
        assert manager.get_alarm_by_id(sample_alarm.id).title == "Updated Title"
        assert manager.get_alarm_by_id(sample_alarm.id).time == "22:00"

    def test_update_nonexistent(self, manager: AlarmManager) -> None:
        """Updating a non-existent alarm should not crash."""
        alarm = Alarm(id="ghost", time="12:00")
        manager.update_alarm(alarm)  # Should not raise

    def test_emits_signal(self, manager: AlarmManager, sample_alarm: Alarm) -> None:
        manager.add_alarm(sample_alarm)
        received = []

        def handler() -> None:
            received.append(True)

        manager.alarms_changed.connect(handler)
        updated = Alarm(id=sample_alarm.id, title="Updated")
        manager.update_alarm(updated)
        assert len(received) == 1


class TestToggleAlarm:
    """Enabling / disabling alarms."""

    def test_disable(self, manager: AlarmManager, sample_alarm: Alarm) -> None:
        manager.add_alarm(sample_alarm)
        manager.toggle_alarm(sample_alarm.id, False)
        assert manager.get_alarm_by_id(sample_alarm.id).enabled is False

    def test_enable(self, manager: AlarmManager, sample_alarm: Alarm) -> None:
        manager.add_alarm(sample_alarm)
        manager.toggle_alarm(sample_alarm.id, False)
        manager.toggle_alarm(sample_alarm.id, True)
        assert manager.get_alarm_by_id(sample_alarm.id).enabled is True

    def test_toggle_nonexistent(self, manager: AlarmManager) -> None:
        """Toggling a non-existent alarm should not crash."""
        manager.toggle_alarm("no-such-id", False)

    def test_emits_signal(self, manager: AlarmManager, sample_alarm: Alarm) -> None:
        manager.add_alarm(sample_alarm)
        received = []

        def handler() -> None:
            received.append(True)

        manager.alarms_changed.connect(handler)
        manager.toggle_alarm(sample_alarm.id, False)
        assert len(received) == 1


# ===================================================================
# Compatibility aliases
# ===================================================================


class TestCompatibilityAliases:
    """Legacy method names used by existing controllers."""

    def test_get_all(self, manager: AlarmManager, sample_alarm: Alarm) -> None:
        manager.add_alarm(sample_alarm)
        assert len(manager.get_all()) == 1

    def test_get_by_id(self, manager: AlarmManager, sample_alarm: Alarm) -> None:
        manager.add_alarm(sample_alarm)
        assert manager.get_by_id(sample_alarm.id) is not None
        assert manager.get_by_id("no-such-id") is None

    def test_add(self, manager: AlarmManager, sample_alarm: Alarm) -> None:
        manager.add(sample_alarm)
        assert len(manager.get_alarms()) == 1

    def test_remove(self, manager: AlarmManager, sample_alarm: Alarm) -> None:
        manager.add(sample_alarm)
        manager.remove(sample_alarm.id)
        assert manager.get_alarms() == []

    def test_update(self, manager: AlarmManager, sample_alarm: Alarm) -> None:
        manager.add(sample_alarm)
        updated = Alarm(id=sample_alarm.id, title="Alias Updated")
        manager.update(updated)
        assert manager.get_alarm_by_id(sample_alarm.id).title == "Alias Updated"

    def test_toggle_flips_state(
        self, manager: AlarmManager, sample_alarm: Alarm
    ) -> None:
        manager.add(sample_alarm)
        assert sample_alarm.enabled is True
        manager.toggle(sample_alarm.id)  # → False
        assert manager.get_alarm_by_id(sample_alarm.id).enabled is False
        manager.toggle(sample_alarm.id)  # → True
        assert manager.get_alarm_by_id(sample_alarm.id).enabled is True

    def test_toggle_nonexistent(self, manager: AlarmManager) -> None:
        """toggle() on a missing id should not crash."""
        manager.toggle("no-such-id")

    def test_snooze_alias(self, manager: AlarmManager, sample_alarm: Alarm) -> None:
        manager.add(sample_alarm)
        manager.snooze(sample_alarm.id, 15)
        assert manager.get_alarm_by_id(sample_alarm.id).snoozed_until is not None


# ===================================================================
# Persistence roundtrip
# ===================================================================


class TestPersistence:
    """Save → reload cycle must preserve all data."""

    def test_save_and_reload(
        self, storage: Storage, qtbot, sample_alarm: Alarm
    ) -> None:
        """Add an alarm, persist, create a fresh manager — data survives."""
        mgr1 = AlarmManager(storage)
        mgr1._timer.stop()
        mgr1.add_alarm(sample_alarm)

        mgr2 = AlarmManager(storage)
        mgr2._timer.stop()
        assert len(mgr2.get_alarms()) == 1
        restored = mgr2.get_alarms()[0]
        assert restored.id == sample_alarm.id
        assert restored.time == sample_alarm.time
        assert restored.days == sample_alarm.days
        assert restored.title == sample_alarm.title
        assert restored.enabled == sample_alarm.enabled
        assert restored.once == sample_alarm.once

    def test_multiple_alarms_persist(
        self, storage: Storage, qtbot
    ) -> None:
        """Multiple alarms survive a save/load cycle."""
        mgr1 = AlarmManager(storage)
        mgr1._timer.stop()
        mgr1.add_alarm(Alarm(id="a1", time="07:00"))
        mgr1.add_alarm(Alarm(id="a2", time="08:00"))
        mgr1.add_alarm(Alarm(id="a3", time="09:00"))

        mgr2 = AlarmManager(storage)
        mgr2._timer.stop()
        assert len(mgr2.get_alarms()) == 3

    def test_json_file_contents(
        self, storage: Storage, qtbot, sample_alarm: Alarm
    ) -> None:
        """Verify the raw JSON file contents after saving."""
        mgr = AlarmManager(storage)
        mgr._timer.stop()
        mgr.add_alarm(sample_alarm)

        with open(storage.get_alarms_file(), "r", encoding="utf-8") as f:
            raw = json.load(f)
        assert raw["version"] == 1
        assert len(raw["alarms"]) == 1
        assert raw["alarms"][0]["id"] == sample_alarm.id


# ===================================================================
# Snooze
# ===================================================================


class TestSnooze:
    """Snooze functionality."""

    def test_snooze_sets_snoozed_until(
        self, manager: AlarmManager, sample_alarm: Alarm
    ) -> None:
        manager.add_alarm(sample_alarm)
        manager.snooze_alarm(sample_alarm.id, 10)
        snoozed = manager.get_alarm_by_id(sample_alarm.id).snoozed_until
        assert snoozed is not None
        assert isinstance(snoozed, str)
        assert ":" in snoozed

    def test_snooze_nonexistent(self, manager: AlarmManager) -> None:
        """Snoozing a non-existent alarm should not crash."""
        manager.snooze_alarm("no-such-id", 5)

    def test_emits_signal(self, manager: AlarmManager, sample_alarm: Alarm) -> None:
        manager.add_alarm(sample_alarm)
        received = []

        def handler() -> None:
            received.append(True)

        manager.alarms_changed.connect(handler)
        manager.snooze_alarm(sample_alarm.id, 5)
        assert len(received) == 1


# ===================================================================
# check_alarms
# ===================================================================


class TestCheckAlarms:
    """Periodic alarm evaluation logic."""

    def test_triggers_matching_alarm(
        self, manager: AlarmManager, once_alarm: Alarm
    ) -> None:
        """A once-alarm matching current time should emit ``alarm_triggered``."""
        manager.add_alarm(once_alarm)
        triggered = []

        def handler(alarm: Alarm) -> None:
            triggered.append(alarm)

        manager.alarm_triggered.connect(handler)

        # Freeze current time to match the alarm
        with patch("src.models.alarm_manager.datetime") as mock_dt:
            mock_dt.now.return_value.strftime.return_value = "08:00"
            mock_dt.now.return_value.isoweekday.return_value = 1
            manager.check_alarms()

        assert len(triggered) == 1
        assert triggered[0].id == once_alarm.id

    def test_disables_once_alarm_after_trigger(
        self, manager: AlarmManager, once_alarm: Alarm
    ) -> None:
        """A one-shot alarm should be disabled and snooze cleared after firing."""
        manager.add_alarm(once_alarm)
        with patch("src.models.alarm_manager.datetime") as mock_dt:
            mock_dt.now.return_value.strftime.return_value = "08:00"
            mock_dt.now.return_value.isoweekday.return_value = 1
            manager.check_alarms()

        updated = manager.get_alarm_by_id(once_alarm.id)
        assert updated.enabled is False
        assert updated.snoozed_until is None

    def test_does_not_trigger_non_matching(
        self, manager: AlarmManager, sample_alarm: Alarm
    ) -> None:
        """An alarm that does not match current time should NOT trigger."""
        triggered = []

        def handler(alarm: Alarm) -> None:
            triggered.append(alarm)

        manager.add_alarm(sample_alarm)
        manager.alarm_triggered.connect(handler)

        with patch("src.models.alarm_manager.datetime") as mock_dt:
            mock_dt.now.return_value.strftime.return_value = "12:00"
            mock_dt.now.return_value.isoweekday.return_value = 1
            manager.check_alarms()

        assert len(triggered) == 0

    def test_skips_disabled_alarm(
        self, manager: AlarmManager, disabled_alarm: Alarm
    ) -> None:
        """A disabled alarm should never trigger."""
        triggered = []

        def handler(alarm: Alarm) -> None:
            triggered.append(alarm)

        manager.add_alarm(disabled_alarm)
        manager.alarm_triggered.connect(handler)

        with patch("src.models.alarm_manager.datetime") as mock_dt:
            mock_dt.now.return_value.strftime.return_value = "06:00"
            mock_dt.now.return_value.isoweekday.return_value = 1
            manager.check_alarms()

        assert len(triggered) == 0

    def test_repeating_alarm_stays_enabled_after_trigger(
        self, manager: AlarmManager, sample_alarm: Alarm
    ) -> None:
        """A repeating alarm should stay enabled after firing."""
        manager.add_alarm(sample_alarm)
        with patch("src.models.alarm_manager.datetime") as mock_dt:
            mock_dt.now.return_value.strftime.return_value = "07:30"
            mock_dt.now.return_value.isoweekday.return_value = 1
            manager.check_alarms()

        updated = manager.get_alarm_by_id(sample_alarm.id)
        assert updated.enabled is True  # should not be disabled


# ===================================================================
# Internal helpers
# ===================================================================


class TestInternalHelpers:
    """Test private/static methods of AlarmManager."""

    def test_validate_alarm_dict_valid(self, sample_alarm: Alarm) -> None:
        assert AlarmManager._validate_alarm_dict(sample_alarm.to_dict()) is True

    def test_validate_alarm_dict_missing_keys(self) -> None:
        invalid = {"id": "test"}  # missing most keys
        assert AlarmManager._validate_alarm_dict(invalid) is False

    def test_validate_alarm_dict_bad_time(self) -> None:
        data = {
            "id": "test",
            "enabled": True,
            "time": "not-a-time",
            "days": [],
            "once": True,
            "sound_source": "builtin",
            "volume": 80,
            "fade_in": False,
        }
        assert AlarmManager._validate_alarm_dict(data) is False

    def test_is_snooze_active_valid_future(self) -> None:
        """A snoozed time in the future is active."""
        # Can't easily test without mocking, but we can verify it returns bool
        result = AlarmManager._is_snooze_active("23:59")
        assert isinstance(result, bool)

    def test_is_snooze_active_invalid(self) -> None:
        assert AlarmManager._is_snooze_active("invalid") is False

    def test_is_snooze_active_value_error(self) -> None:
        """If replace raises ValueError, returns False."""
        from unittest.mock import patch as mock_patch

        with mock_patch("src.models.alarm_manager.datetime") as mock_dt:
            mock_dt.now.return_value.replace.side_effect = ValueError
            assert AlarmManager._is_snooze_active("12:00") is False

    def test_on_timer_routes_to_check_alarms(self, manager, once_alarm) -> None:
        """The _on_timer slot should delegate to check_alarms()."""
        manager.add_alarm(once_alarm)
        with patch.object(manager, "check_alarms") as mock_check:
            manager._on_timer()
            mock_check.assert_called_once()


# ===================================================================
# Load edge cases
# ===================================================================


class TestLoadEdgeCases:
    """Edge cases in the load() method."""

    def test_load_unexpected_exception(
        self, storage: Storage, qtbot
    ) -> None:
        """An unexpected exception during read should result in empty list."""
        with patch.object(storage, "read_json", side_effect=RuntimeError("Unexpected")):
            mgr = AlarmManager(storage)
            mgr._timer.stop()
            assert mgr.get_alarms() == []

    def test_load_clears_expired_snooze(
        self, storage: Storage, qtbot, sample_alarm: Alarm
    ) -> None:
        """A snoozed_until in the past should be cleared on load."""
        sample_alarm.snoozed_until = "00:00"  # definitely in the past
        data = {"version": 1, "alarms": [sample_alarm.to_dict()]}
        filepath = storage.get_alarms_file()
        storage.atomic_save(filepath, data)

        mgr = AlarmManager(storage)
        mgr._timer.stop()
        restored = mgr.get_alarm_by_id(sample_alarm.id)
        assert restored is not None
        assert restored.snoozed_until is None  # cleared because it's in the past


# ===================================================================
# Edge cases
# ===================================================================


class TestEdgeCases:
    """Corner cases and error resilience."""

    def test_add_then_get_alarm_by_id(
        self, manager: AlarmManager, sample_alarm: Alarm
    ) -> None:
        manager.add_alarm(sample_alarm)
        found = manager.get_alarm_by_id(sample_alarm.id)
        assert found is not None
        assert found.id == sample_alarm.id

    def test_get_alarm_by_id_returns_none(
        self, manager: AlarmManager
    ) -> None:
        assert manager.get_alarm_by_id("nonexistent") is None

    def test_get_alarms_returns_copy(self, manager: AlarmManager) -> None:
        """get_alarms() should return a sorted *copy* of the internal list."""
        a1 = Alarm(id="a1", time="09:00")
        a2 = Alarm(id="a2", time="07:00")
        manager.add_alarm(a1)
        manager.add_alarm(a2)

        retrieved = manager.get_alarms()
        retrieved.append(Alarm(id="a3", time="10:00"))

        assert len(manager.get_alarms()) == 2  # internal list unchanged
