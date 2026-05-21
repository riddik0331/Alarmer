"""Tests for helper / utility functions (pure, no Qt dependency).

Most tests are deterministic; time-dependent functions (``is_time_match``,
``time_from_now``) use ``unittest.mock`` to control ``datetime.now()``.
"""

from __future__ import annotations

import re
from unittest.mock import MagicMock, Mock, patch

import pytest

from src.utils.helpers import (
    center_on_screen,
    clamp,
    current_weekday,
    format_days,
    generate_id,
    is_time_match,
    time_from_now,
    validate_time,
)


# ===================================================================
# generate_id
# ===================================================================


class TestGenerateId:
    """UUID v4 generation."""

    UUID_RE = re.compile(
        r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
        re.IGNORECASE,
    )

    def test_returns_string(self) -> None:
        assert isinstance(generate_id(), str)

    def test_uuid_format(self) -> None:
        assert self.UUID_RE.match(generate_id()) is not None

    def test_unique(self) -> None:
        ids = {generate_id() for _ in range(100)}
        assert len(ids) == 100


# ===================================================================
# validate_time
# ===================================================================


class TestValidateTime:
    """HH:MM format validation."""

    @pytest.mark.parametrize(
        "time_str",
        [
            "00:00",
            "08:00",
            "12:30",
            "23:59",
            "00:01",
            "09:05",
            "14:00",
            "23:00",
            "00:59",
        ],
    )
    def test_valid(self, time_str: str) -> None:
        assert validate_time(time_str) is True, f"{time_str!r} should be valid"

    @pytest.mark.parametrize(
        "time_str",
        [
            "",
            "abc",
            "24:00",  # hour out of range
            "23:60",  # minute out of range
            "12:00:00",  # too many parts
            "9:00",  # missing leading zero
            " 08:00",  # leading space
            "-1:00",  # negative hour
            "12:1",  # single-digit minute
            "12.00",  # wrong separator
        ],
    )
    def test_invalid(self, time_str: str) -> None:
        assert validate_time(time_str) is False, f"{time_str!r} should be invalid"

    def test_none_raises_type_error(self) -> None:
        """None raises ``TypeError`` (``re.match`` requires a string)."""
        with pytest.raises(TypeError):
            validate_time(None)  # type: ignore[arg-type]


# ===================================================================
# is_time_match  (requires mocking datetime.now)
# ===================================================================


class TestIsTimeMatch:
    """Time comparison with ±30 s tolerance.

    Uses ``MagicMock`` for mock datetime objects so that magic methods
    (``__sub__``) can be configured.
    """

    @patch("src.utils.helpers.datetime")
    def test_exact_match(self, mock_dt_module) -> None:
        """Current time exactly equals the alarm time."""
        mock_now = MagicMock()
        mock_now.strftime.return_value = "14:30"
        mock_alarm_dt = MagicMock()
        mock_now.replace.return_value = mock_alarm_dt
        # (now - alarm_dt).total_seconds() == 0.0
        diff_mock = MagicMock()
        diff_mock.total_seconds.return_value = 0.0
        mock_now.__sub__.return_value = diff_mock
        mock_dt_module.now.return_value = mock_now

        assert is_time_match("14:30") is True

    @patch("src.utils.helpers.datetime")
    def test_within_30_seconds_positive(self, mock_dt_module) -> None:
        """Alarm is 15 seconds in the past — still within tolerance."""
        mock_now = MagicMock()
        mock_now.strftime.return_value = "14:30"
        mock_alarm_dt = MagicMock()
        mock_now.replace.return_value = mock_alarm_dt
        diff_mock = MagicMock()
        diff_mock.total_seconds.return_value = 15.0
        mock_now.__sub__.return_value = diff_mock
        mock_dt_module.now.return_value = mock_now

        assert is_time_match("14:30") is True

    @patch("src.utils.helpers.datetime")
    def test_within_30_seconds_negative(self, mock_dt_module) -> None:
        """Alarm is 15 seconds in the future — still within tolerance."""
        mock_now = MagicMock()
        mock_now.strftime.return_value = "14:30"
        mock_alarm_dt = MagicMock()
        mock_now.replace.return_value = mock_alarm_dt
        diff_mock = MagicMock()
        diff_mock.total_seconds.return_value = -15.0
        mock_now.__sub__.return_value = diff_mock
        mock_dt_module.now.return_value = mock_now

        assert is_time_match("14:30") is True

    @patch("src.utils.helpers.datetime")
    def test_exceeds_30_seconds(self, mock_dt_module) -> None:
        """Alarm is 45 seconds away — outside tolerance."""
        mock_now = MagicMock()
        mock_now.strftime.return_value = "14:30"
        mock_alarm_dt = MagicMock()
        mock_now.replace.return_value = mock_alarm_dt
        diff_mock = MagicMock()
        diff_mock.total_seconds.return_value = 45.0
        mock_now.__sub__.return_value = diff_mock
        mock_dt_module.now.return_value = mock_now

        assert is_time_match("14:30") is False

    @patch("src.utils.helpers.datetime")
    def test_at_boundary_30_seconds(self, mock_dt_module) -> None:
        """Exactly 30 seconds should match."""
        mock_now = MagicMock()
        mock_now.strftime.return_value = "14:30"
        mock_alarm_dt = MagicMock()
        mock_now.replace.return_value = mock_alarm_dt
        diff_mock = MagicMock()
        diff_mock.total_seconds.return_value = 30.0
        mock_now.__sub__.return_value = diff_mock
        mock_dt_module.now.return_value = mock_now

        assert is_time_match("14:30") is True

    @patch("src.utils.helpers.datetime")
    def test_value_error_on_replace(self, mock_dt_module) -> None:
        """If ``replace()`` raises ``ValueError`` the function returns ``False``."""
        mock_now = MagicMock()
        mock_now.strftime.return_value = "14:30"
        mock_now.replace.side_effect = ValueError("bad time")
        mock_dt_module.now.return_value = mock_now

        assert is_time_match("14:30") is False

    def test_invalid_alarm_time(self) -> None:
        """Invalid alarm_time should return False without mocking."""
        assert is_time_match("invalid") is False


# ===================================================================
# time_from_now
# ===================================================================


class TestTimeFromNow:
    """Compute a future HH:MM string."""

    @patch("src.utils.helpers.datetime")
    def test_normal_case(self, mock_dt_module) -> None:
        """15 minutes from 10:00 → '10:15'."""
        mock_now = MagicMock()
        mock_future = MagicMock()
        mock_future.strftime.return_value = "10:15"
        mock_now.__add__.return_value = mock_future
        mock_dt_module.now.return_value = mock_now

        result = time_from_now(15)
        assert result == "10:15"
        mock_now.__add__.assert_called_once()

    @patch("src.utils.helpers.datetime")
    def test_zero_minutes(self, mock_dt_module) -> None:
        """0 minutes from now → the same time."""
        mock_now = MagicMock()
        mock_future = MagicMock()
        mock_future.strftime.return_value = "10:00"
        mock_now.__add__.return_value = mock_future
        mock_dt_module.now.return_value = mock_now

        result = time_from_now(0)
        assert result == "10:00"

    @patch("src.utils.helpers.datetime")
    def test_negative_minutes(self, mock_dt_module) -> None:
        """Negative minutes → a past time."""
        mock_now = MagicMock()
        mock_past = MagicMock()
        mock_past.strftime.return_value = "09:45"
        mock_now.__add__.return_value = mock_past
        mock_dt_module.now.return_value = mock_now

        result = time_from_now(-15)
        assert result == "09:45"

    @patch("src.utils.helpers.datetime")
    def test_wraps_to_next_day(self, mock_dt_module) -> None:
        """Adding minutes may wrap to the next calendar day (still returns HH:MM)."""
        mock_now = MagicMock()
        mock_future = MagicMock()
        mock_future.strftime.return_value = "00:05"
        mock_now.__add__.return_value = mock_future
        mock_dt_module.now.return_value = mock_now

        result = time_from_now(5)
        assert result == "00:05"

    def test_returns_string(self) -> None:
        """Without mocking, just verify it returns a string in HH:MM format."""
        result = time_from_now(1)
        assert isinstance(result, str)
        assert re.match(r"^\d{2}:\d{2}$", result) is not None


# ===================================================================
# format_days
# ===================================================================


class TestFormatDays:
    """Human-readable day-of-week formatting."""

    def test_empty(self) -> None:
        assert format_days([]) == ""

    def test_single_day_ru(self) -> None:
        assert format_days([3], "ru") == "Ср"

    def test_multiple_days_ru(self) -> None:
        assert format_days([1, 3, 5], "ru") == "Пн Ср Пт"

    def test_all_days_ru(self) -> None:
        assert format_days([1, 2, 3, 4, 5, 6, 7], "ru") == "Каждый день"

    def test_english_locale(self) -> None:
        assert format_days([1, 3, 5], locale="en") == "Mon Wed Fri"

    def test_unsorted_input(self) -> None:
        """Output is always in ISO order regardless of input order."""
        assert format_days([5, 1, 3], "ru") == "Пн Ср Пт"

    def test_invalid_day_numbers_are_filtered(self) -> None:
        """Day numbers outside 1-7 are ignored."""
        assert format_days([0, 8, 1], "ru") == "Пн"

    def test_all_days_out_of_order(self) -> None:
        """All seven days in any order → 'Каждый день'."""
        assert format_days([7, 1, 6, 2, 5, 3, 4], "ru") == "Каждый день"


# ===================================================================
# clamp
# ===================================================================


class TestClamp:
    """Value clamping."""

    def test_within_range(self) -> None:
        assert clamp(5, 0, 10) == 5

    def test_below_range(self) -> None:
        assert clamp(-5, 0, 10) == 0

    def test_above_range(self) -> None:
        assert clamp(15, 0, 10) == 10

    def test_at_lower_bound(self) -> None:
        assert clamp(0, 0, 10) == 0

    def test_at_upper_bound(self) -> None:
        assert clamp(10, 0, 10) == 10

    def test_equal_bounds(self) -> None:
        assert clamp(100, 5, 5) == 5

    def test_negative_bounds(self) -> None:
        assert clamp(-10, -5, 0) == -5


# ===================================================================
# current_weekday
# ===================================================================


class TestCurrentWeekday:
    """ISO weekday (1=Monday … 7=Sunday)."""

    def test_returns_valid_iso_weekday(self) -> None:
        wd = current_weekday()
        assert isinstance(wd, int)
        assert 1 <= wd <= 7


# ===================================================================
# center_on_screen  (smoke-level tests — no real screen required)
# ===================================================================


class TestCenterOnScreen:
    """These tests verify the function does not crash on edge inputs."""

    def test_with_none(self) -> None:
        """None input should be silently ignored."""
        center_on_screen(None)

    def test_with_string(self) -> None:
        """Non-widget inputs should be silently ignored."""
        center_on_screen("not a widget")

    def test_with_int(self) -> None:
        """Integer input should not crash."""
        center_on_screen(42)
