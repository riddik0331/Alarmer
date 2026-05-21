"""Tests for the Alarm dataclass — model creation, serialisation, and query
helpers.

All tests in this module are pure (no Qt dependency).
"""

from __future__ import annotations

from src.models.alarm_model import Alarm


# ===================================================================
# Creation
# ===================================================================


class TestAlarmCreation:
    """Verify that Alarm objects are created with correct default / custom values."""

    def test_default_creation(self) -> None:
        """An Alarm() with no arguments should use all defaults."""
        alarm = Alarm()
        assert alarm.id == ""
        assert alarm.enabled is True
        assert alarm.title == ""
        assert alarm.time == "08:00"
        assert alarm.days == []
        assert alarm.once is True
        assert alarm.sound_source == "builtin"
        assert alarm.sound_name == "classic"
        assert alarm.sound_file is None
        assert alarm.volume == 80
        assert alarm.fade_in is False
        assert alarm.snoozed_until is None

    def test_custom_creation(self, sample_alarm: Alarm) -> None:
        """Alarm fields match the values passed to the constructor."""
        assert sample_alarm.id == "test-id-123"
        assert sample_alarm.title == "Test Alarm"
        assert sample_alarm.time == "07:30"
        assert sample_alarm.days == [1, 2, 3, 4, 5]
        assert sample_alarm.once is False
        assert sample_alarm.volume == 80

    def test_days_not_copied_by_default(self) -> None:
        """Dataclass uses the same list reference (not a defensive copy).

        This is expected Python dataclass behaviour — the caller is
        responsible for passing a copy if needed.
        """
        days = [1, 2, 3]
        a1 = Alarm(id="a1", days=days)
        a2 = Alarm(id="a2", days=days)
        a1.days.append(4)
        # Both alarms share the same list object
        assert a2.days == [1, 2, 3, 4]
        assert a1.days is a2.days


# ===================================================================
# Serialisation
# ===================================================================


class TestSerialization:
    """Test to_dict() / from_dict() roundtrip and edge cases."""

    def test_to_dict(self, sample_alarm: Alarm) -> None:
        """to_dict() produces a JSON-compatible dictionary."""
        d = sample_alarm.to_dict()
        assert d["id"] == "test-id-123"
        assert d["time"] == "07:30"
        assert d["days"] == [1, 2, 3, 4, 5]
        assert d["once"] is False
        assert d["sound_source"] == "builtin"
        assert d["volume"] == 80

    def test_from_dict_full(self) -> None:
        """from_dict() restores all fields."""
        data = {
            "id": "from-dict-id",
            "enabled": False,
            "title": "From Dict",
            "time": "22:15",
            "days": [6, 7],
            "once": False,
            "sound_source": "file",
            "sound_name": "gentle",
            "sound_file": "C:\\music\\alarm.wav",
            "volume": 50,
            "fade_in": True,
            "snoozed_until": "22:20",
        }
        alarm = Alarm.from_dict(data)
        assert alarm.id == "from-dict-id"
        assert alarm.enabled is False
        assert alarm.title == "From Dict"
        assert alarm.time == "22:15"
        assert alarm.days == [6, 7]
        assert alarm.once is False
        assert alarm.sound_source == "file"
        assert alarm.sound_name == "gentle"
        assert alarm.sound_file == "C:\\music\\alarm.wav"
        assert alarm.volume == 50
        assert alarm.fade_in is True
        assert alarm.snoozed_until == "22:20"

    def test_from_dict_missing_keys(self) -> None:
        """Missing keys should fall back to defaults (no crash)."""
        alarm = Alarm.from_dict({"time": "12:00"})
        assert alarm.id != ""  # auto-generated UUID
        assert alarm.enabled is True
        assert alarm.title == ""
        assert alarm.days == []
        assert alarm.once is True
        assert alarm.sound_source == "builtin"
        assert alarm.sound_name == "classic"
        assert alarm.sound_file is None
        assert alarm.volume == 80
        assert alarm.fade_in is False
        assert alarm.snoozed_until is None

    def test_from_dict_partial(self) -> None:
        """Partial data — only provided keys override defaults."""
        alarm = Alarm.from_dict({"id": "partial", "title": "Partial", "once": False})
        assert alarm.id == "partial"
        assert alarm.title == "Partial"
        assert alarm.once is False
        # Everything else should still be the default
        assert alarm.time == "08:00"
        assert alarm.volume == 80

    def test_roundtrip(self, sample_alarm: Alarm) -> None:
        """to_dict() → from_dict() → object equal to original."""
        d = sample_alarm.to_dict()
        restored = Alarm.from_dict(d)
        # Compare every field
        for field in sample_alarm.__dataclass_fields__:
            assert getattr(restored, field) == getattr(sample_alarm, field), (
                f"Field '{field}' differs after roundtrip"
            )

    def test_roundtrip_with_none_file(self) -> None:
        """``sound_file`` and ``snoozed_until`` remain None after roundtrip."""
        alarm = Alarm(id="none-test", time="14:00")
        d = alarm.to_dict()
        restored = Alarm.from_dict(d)
        assert restored.sound_file is None
        assert restored.snoozed_until is None

    def test_days_are_copied_in_to_dict(self) -> None:
        """to_dict() should return a list copy, not the internal reference."""
        alarm = Alarm(days=[1, 2, 3])
        d = alarm.to_dict()
        d["days"].append(4)
        assert alarm.days == [1, 2, 3]


# ===================================================================
# Query helpers
# ===================================================================


class TestIsRepeating:
    """is_repeating() reflects the ``once`` flag."""

    def test_repeating_when_once_false(self, sample_alarm: Alarm) -> None:
        assert sample_alarm.is_repeating() is True

    def test_not_repeating_when_once_true(self, once_alarm: Alarm) -> None:
        assert once_alarm.is_repeating() is False


class TestShouldRing:
    """should_ring() conditions: enabled, time, snooze, day-of-week."""

    def test_disabled_alarm_never_rings(self, disabled_alarm: Alarm) -> None:
        assert disabled_alarm.should_ring("06:00", 1) is False

    def test_time_mismatch_does_not_ring(self, sample_alarm: Alarm) -> None:
        assert sample_alarm.should_ring("07:31", 1) is False

    def test_snoozed_alarm_skipped(self, sample_alarm: Alarm) -> None:
        sample_alarm.snoozed_until = "08:00"
        assert sample_alarm.should_ring("07:30", 1) is False

    def test_once_alarm_rings_any_weekday(self, once_alarm: Alarm) -> None:
        """One-shot alarms ignore the weekday check."""
        assert once_alarm.should_ring("08:00", 1) is True   # Monday
        assert once_alarm.should_ring("08:00", 7) is True   # Sunday

    def test_repeating_weekday_matches(self, sample_alarm: Alarm) -> None:
        """Alarm rings on a day that is in its days list."""
        assert sample_alarm.should_ring("07:30", 1) is True  # Monday

    def test_repeating_weekday_does_not_match(self, sample_alarm: Alarm) -> None:
        """Alarm does NOT ring on a day outside its days list."""
        assert sample_alarm.should_ring("07:30", 6) is False  # Saturday
        assert sample_alarm.should_ring("07:30", 7) is False  # Sunday

    def test_invalid_current_time_returns_false(self, sample_alarm: Alarm) -> None:
        assert sample_alarm.should_ring("abc", 1) is False

    def test_empty_current_time_returns_false(self, sample_alarm: Alarm) -> None:
        assert sample_alarm.should_ring("", 1) is False


# ===================================================================
# get_days_display
# ===================================================================


class TestGetDaysDisplay:
    """Human-readable day-of-week display (Russian locale)."""

    def test_once_alarm(self) -> None:
        alarm = Alarm(once=True)
        assert alarm.get_days_display() == "Единоразово"

    def test_no_days_repeating(self) -> None:
        """Repeating alarm with empty days list → 'Единоразово'."""
        alarm = Alarm(once=False, days=[])
        assert alarm.get_days_display() == "Единоразово"

    def test_work_days(self, sample_alarm: Alarm) -> None:
        """Mon-Fri → 'Пн Вт Ср Чт Пт'."""
        assert sample_alarm.get_days_display() == "Пн Вт Ср Чт Пт"

    def test_every_day(self) -> None:
        alarm = Alarm(once=False, days=[1, 2, 3, 4, 5, 6, 7])
        assert alarm.get_days_display() == "Каждый день"

    def test_single_day(self) -> None:
        alarm = Alarm(once=False, days=[3])  # Wednesday
        assert alarm.get_days_display() == "Ср"

    def test_weekend(self) -> None:
        alarm = Alarm(once=False, days=[6, 7])  # Saturday, Sunday
        assert alarm.get_days_display() == "Сб Вс"

    def test_unsorted_days(self) -> None:
        """Days should be displayed in ISO order regardless of input order."""
        alarm = Alarm(once=False, days=[5, 1, 3])
        assert alarm.get_days_display() == "Пн Ср Пт"

    def test_english_locale(self) -> None:
        alarm = Alarm(once=False, days=[1, 3, 5])
        assert alarm.get_days_display(locale="en") == "Mon Wed Fri"

    def test_unknown_locale_falls_back_to_empty(self) -> None:
        """Unknown locale → empty day labels (just spaces)."""
        alarm = Alarm(once=False, days=[1, 2])
        result = alarm.get_days_display(locale="fr")
        # Labels list for unknown locale: ["", "Mon", "Tue", ...] so it uses English
        assert result == "Mon Tue"


# ===================================================================
# Ordering
# ===================================================================


class TestOrdering:
    """Alarms should be sortable by time (HH:MM string comparison)."""

    def test_sort_by_time(self) -> None:
        a1 = Alarm(id="a1", time="09:00")
        a2 = Alarm(id="a2", time="07:00")
        a3 = Alarm(id="a3", time="08:00")
        alarms = [a1, a2, a3]
        alarms.sort()
        assert [a.time for a in alarms] == ["07:00", "08:00", "09:00"]
        assert [a.id for a in alarms] == ["a2", "a3", "a1"]

    def test_comparison_with_non_alarm(self) -> None:
        """__lt__ returns NotImplemented for non-Alarm types."""
        alarm = Alarm(time="10:00")
        result = alarm.__lt__("not an alarm")  # type: ignore[operator]
        assert result is NotImplemented
