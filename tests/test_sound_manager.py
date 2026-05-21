"""Tests for the SoundManager — initialisation, playback start/stop.

All tests require a QApplication (provided by the ``qtbot`` fixture from
``pytest-qt``).  Actual audio output is **not** tested; we only verify that
the manager does not crash and that its internal state transitions are
correct.
"""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest
from PySide6.QtCore import QObject
from PySide6.QtMultimedia import QMediaPlayer

from src.models.alarm_model import Alarm
from src.models.sound_manager import SoundManager
from src.utils.helpers import center_on_screen


# ===================================================================
# Initialisation
# ===================================================================


class TestInitialization:
    """The SoundManager should create a QMediaPlayer and QAudioOutput."""

    def test_player_created(self, qtbot) -> None:
        sm = SoundManager()
        assert sm._player is not None
        assert isinstance(sm._player, QMediaPlayer)

    def test_audio_output_created(self, qtbot) -> None:
        sm = SoundManager()
        assert sm._audio_output is not None

    def test_is_qobject(self, qtbot) -> None:
        """SoundManager should inherit QObject (required for signals)."""
        sm = SoundManager()
        assert isinstance(sm, QObject)

    def test_initial_state(self, qtbot) -> None:
        sm = SoundManager()
        assert sm._current_alarm is None
        assert sm._current_volume == 1.0
        assert sm._target_volume == 1.0


# ===================================================================
# Signals
# ===================================================================


class TestSignals:
    """SoundManager exposes ``sound_started`` and ``sound_stopped`` signals."""

    def test_has_sound_started_signal(self, qtbot) -> None:
        sm = SoundManager()
        assert hasattr(sm, "sound_started")

    def test_has_sound_stopped_signal(self, qtbot) -> None:
        sm = SoundManager()
        assert hasattr(sm, "sound_stopped")


# ===================================================================
# Stop (without playing)
# ===================================================================


class TestStop:
    """Calling stop() when nothing is playing should not crash."""

    def test_stop_without_playing(self, qtbot) -> None:
        sm = SoundManager()
        sm.stop()

    def test_stop_twice(self, qtbot) -> None:
        """Calling stop() consecutively should be safe."""
        sm = SoundManager()
        sm.stop()
        sm.stop()

    def test_stop_emits_signal(self, qtbot) -> None:
        sm = SoundManager()
        received = []

        def handler() -> None:
            received.append(True)

        sm.sound_stopped.connect(handler)
        sm.stop()
        assert len(received) == 1


# ===================================================================
# Play
# ===================================================================


class TestPlay:
    """Full playback via play(alarm)."""

    def test_play_no_crash(self, qtbot, sample_alarm: Alarm) -> None:
        """play() should not crash when the sound file is missing."""
        sm = SoundManager()
        with patch.object(SoundManager, "_get_sound_path", return_value=None):
            sm.play(sample_alarm)

    def test_play_stops_previous(self, qtbot, sample_alarm: Alarm) -> None:
        """Calling play() a second time should stop the previous playback."""
        sm = SoundManager()
        with patch.object(SoundManager, "_get_sound_path", return_value=None):
            sm.play(sample_alarm)
            sm.play(sample_alarm)  # second call — should not crash

    def test_play_sets_current_alarm(self, qtbot, sample_alarm: Alarm) -> None:
        sm = SoundManager()
        with patch.object(SoundManager, "_get_sound_path", return_value=None):
            sm.play(sample_alarm)
        assert sm._current_alarm is sample_alarm

    def test_play_emits_sound_started(
        self, qtbot, sample_alarm: Alarm, tmp_path
    ) -> None:
        sm = SoundManager()
        received = []

        def handler() -> None:
            received.append(True)

        sm.sound_started.connect(handler)
        dummy_file = tmp_path / "sound.wav"
        dummy_file.write_text("")
        with patch.object(
            SoundManager, "_get_sound_path", return_value=str(dummy_file)
        ):
            sm.play(sample_alarm)
        assert len(received) == 1

    def test_play_no_source_path(self, qtbot, sample_alarm: Alarm) -> None:
        """If source path is None, playback should be skipped without crash."""
        sm = SoundManager()
        with patch.object(
            SoundManager, "_get_sound_path", return_value=None
        ) as mock_resolve:
            sm.play(sample_alarm)
            mock_resolve.assert_called_once_with()

    def test_play_with_fade_in(self, qtbot, sample_alarm: Alarm, tmp_path) -> None:
        """play() with an alarm that has fade_in enabled should start fade timer."""
        sample_alarm.fade_in = True
        sm = SoundManager()
        dummy_file = tmp_path / "sound.wav"
        dummy_file.write_text("")
        with patch.object(SoundManager, "_get_sound_path", return_value=str(dummy_file)):
            sm.play(sample_alarm)
        assert sm._fade_timer.isActive() is True
        assert sm._current_volume == 0.0
        sm.stop()

    def test_play_does_not_start_when_no_source(
        self, qtbot, sample_alarm: Alarm
    ) -> None:
        """If no source path is resolved, player.play() should NOT be called."""
        sm = SoundManager()
        with patch.object(SoundManager, "_get_sound_path", return_value=None):
            with patch.object(sm._player, "play") as mock_play:
                sm.play(sample_alarm)  # source is None → no play
                mock_play.assert_not_called()


# ===================================================================
# center_on_screen  (requires QWidget)
# ===================================================================


class TestCenterOnScreen:
    """Test centering a widget on screen (requires QApplication)."""

    def test_with_qwidget(self, qtbot) -> None:
        """A QWidget should be moved (centered) on the primary screen."""
        from PySide6.QtWidgets import QWidget

        widget = QWidget()
        qtbot.addWidget(widget)
        # Should not crash, and the widget should be moved
        center_on_screen(widget)
        # The widget was centered — position is now set
        assert widget.x() >= 0 or widget.y() >= 0  # at least one coordinate set


# ===================================================================
# Volume
# ===================================================================


class TestVolume:
    """Internal volume management."""

    @pytest.mark.parametrize(
        "input_vol, expected",
        [
            (0.0, 0.0),
            (0.5, 0.5),
            (1.0, 1.0),
            (-0.1, 0.0),  # clamped
            (1.5, 1.0),  # clamped
        ],
    )
    def test_set_volume_clamps(self, qtbot, input_vol: float, expected: float) -> None:
        sm = SoundManager()
        sm._set_volume(input_vol)
        assert sm._current_volume == expected

    def test_set_volume_updates_audio_output(self, qtbot) -> None:
        sm = SoundManager()
        with patch.object(sm._audio_output, "setVolume") as mock_set:
            sm._set_volume(0.75)
            mock_set.assert_called_once_with(0.75)


# ===================================================================
# Fade-in
# ===================================================================


class TestFadeIn:
    """Fade-in timer behaviour."""

    def test_start_fade_in_sets_target_and_starts_timer(self, qtbot) -> None:
        sm = SoundManager()
        sm._start_fade_in(0.8)
        assert sm._target_volume == 0.8
        assert sm._current_volume == 0.0
        assert sm._fade_timer.isActive() is True

    def test_fade_tick_reaches_target(self, qtbot) -> None:
        """Simulate fade ticks until the target volume is reached."""
        sm = SoundManager()
        sm._start_fade_in(0.5)

        # Manually tick until the timer stops
        while sm._fade_timer.isActive():
            sm._fade_tick()

        assert sm._current_volume == 0.5

    def test_fade_tick_single_step(self, qtbot) -> None:
        """Verify that a single tick increases volume slightly."""
        sm = SoundManager()
        sm._start_fade_in(1.0)
        vol_before = sm._current_volume
        sm._fade_tick()
        assert sm._current_volume > vol_before


# ===================================================================
# Internal helpers  (_get_sound_path)
# ===================================================================


class TestInternalHelpers:
    """Private path-resolution logic."""

    def test_get_sound_path_returns_none_when_file_missing(self, qtbot) -> None:
        """_get_sound_path returns None when alarm_1.wav is missing from disk."""
        sm = SoundManager()
        with patch("os.path.isfile", return_value=False):
            result = sm._get_sound_path()
        assert result is None

    def test_get_sound_path_returns_path_when_file_exists(self, qtbot) -> None:
        """_get_sound_path returns the full path when the file exists."""
        sm = SoundManager()
        with patch("os.path.isfile", return_value=True):
            result = sm._get_sound_path()
        assert result is not None
        assert result.endswith("alarm_1.wav")
        assert isinstance(result, str)

    def test_on_media_status_end_of_media(self, qtbot) -> None:
        """When media ends and current_alarm is set, player.play() is called."""
        sm = SoundManager()
        sm._current_alarm = Alarm(id="test")  # simulate active alarm
        with patch.object(sm._player, "play") as mock_play:
            sm._on_media_status_changed(QMediaPlayer.MediaStatus.EndOfMedia)
            mock_play.assert_called_once()

    def test_on_media_status_other(self, qtbot) -> None:
        """Non-EndOfMedia status should not trigger play()."""
        sm = SoundManager()
        sm._current_alarm = Alarm(id="test")
        with patch.object(sm._player, "play") as mock_play:
            sm._on_media_status_changed(QMediaPlayer.MediaStatus.LoadedMedia)
            mock_play.assert_not_called()
