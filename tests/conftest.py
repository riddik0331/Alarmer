"""Shared fixtures for all tests in the project."""

from __future__ import annotations

from typing import Generator

import pytest
from _pytest.fixtures import SubRequest

from src.models.alarm_model import Alarm


# ---------------------------------------------------------------------------
# Alarm model fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_alarm() -> Alarm:
    """A repeating alarm Mon-Fri at 07:30."""
    return Alarm(
        id="test-id-123",
        enabled=True,
        title="Test Alarm",
        time="07:30",
        days=[1, 2, 3, 4, 5],  # Mon-Fri
        once=False,
        sound_source="builtin",
        sound_name="classic",
        sound_file=None,
        volume=80,
        fade_in=False,
        snoozed_until=None,
    )


@pytest.fixture
def once_alarm() -> Alarm:
    """A one-shot alarm at 08:00."""
    return Alarm(
        id="once-id-456",
        enabled=True,
        title="Once Alarm",
        time="08:00",
        once=True,
        days=[],
    )


@pytest.fixture
def disabled_alarm() -> Alarm:
    """A disabled alarm (should never ring)."""
    return Alarm(
        id="disabled-id-789",
        enabled=False,
        title="Disabled",
        time="06:00",
        once=True,
    )


@pytest.fixture
def alarm_with_file_sound() -> Alarm:
    """Alarm configured to play a user-supplied file."""
    return Alarm(
        id="file-sound-id",
        enabled=True,
        title="File Sound",
        time="12:00",
        once=True,
        sound_source="file",
        sound_name="classic",
        sound_file="C:\\nonexistent\\sound.wav",
    )


# ---------------------------------------------------------------------------
# Storage fixture (uses a temporary directory)
# ---------------------------------------------------------------------------


@pytest.fixture
def storage(tmp_path: SubRequest, monkeypatch: pytest.MonkeyPatch) -> Generator:
    """Create a Storage instance backed by a temporary directory.

    The fixture monkeypatches the static path methods so that all I/O
    happens inside *tmp_path* and is automatically cleaned up by pytest.
    """
    from src.utils.storage import Storage

    # Accept *args to handle the implicit ``self`` when called as an instance method
    monkeypatch.setattr(Storage, "get_data_path", lambda *_: str(tmp_path))
    monkeypatch.setattr(
        Storage, "get_alarms_file", lambda *_: str(tmp_path / "alarms.json")
    )
    yield Storage()


# ---------------------------------------------------------------------------
# AlarmManager fixture (needs the qtbot fixture from pytest-qt)
# ---------------------------------------------------------------------------


@pytest.fixture
def manager(storage, qtbot):
    """Create an AlarmManager backed by the temporary storage.

    The periodic QTimer is stopped after creation so it does not fire during
    tests.
    """
    from src.models.alarm_manager import AlarmManager

    mgr = AlarmManager(storage)
    mgr._timer.stop()
    yield mgr
    mgr._timer.stop()
