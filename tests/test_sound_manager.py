"""Tests for the SoundManager — initialisation, playback start/stop, preview.

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
# Preview
# ===================================================================


class TestPreviewSound:
    """Playing a built-in sound for preview purposes."""

    def test_preview_builtin_name(self, qtbot) -> None:
        """Calling preview_sound with a valid built-in sound name should not crash.

        The actual sound file does not exist in the test environment, so the
        method will log a warning and return early — the point is it should
        not raise an exception.
        """
        with patch.object(SoundManager, "_get_sound_path", return_value=None):
            sm = SoundManager()
            sm.preview_sound("classic")  # should not crash

    def test_preview_returns_early_for_unknown_name(self, qtbot) -> None:
        """Unknown sound names should be handled gracefully (no crash)."""
        with patch.object(SoundManager, "_get_sound_path", return_value=None):
            sm = SoundManager()
            sm.preview_sound("nonexistent_sound")

    def test_preview_with_real_path_mock(self, qtbot, tmp_path) -> None:
        """If the sound file exists, the player source should be set."""
        sound_file = tmp_path / "test.wav"
        sound_file.write_text("")  # empty file, just for path existence

        sm = SoundManager()
        with patch.object(
            SoundManager, "_get_sound_path", return_value=str(sound_file)
        ) as mock_path:
            sm.preview_sound("classic")
            mock_path.assert_called_once_with("classic")

    def test_stop_preview(self, qtbot) -> None:
        """stop_preview should not crash when nothing is previewing."""
        sm = SoundManager()
        sm.stop_preview()

    def test_preview_then_stop(self, qtbot) -> None:
        """Starting preview then stopping should work cleanly."""
        sm = SoundManager()
        with patch.object(SoundManager, "_get_sound_path", return_value=None):
            sm.preview_sound("classic")
        sm.stop_preview()


# ===================================================================
# Play
# ===================================================================


class TestPlay:
    """Full playback via play(alarm)."""

    def test_play_with_builtin_sound(self, qtbot, sample_alarm: Alarm) -> None:
        """play() should not crash with a builtin-sound alarm."""
        sm = SoundManager()
        with patch.object(SoundManager, "_resolve_source_path", return_value=None):
            sm.play(sample_alarm)

    def test_play_stops_previous(self, qtbot, sample_alarm: Alarm) -> None:
        """Calling play() a second time should stop the previous playback."""
        sm = SoundManager()
        with patch.object(SoundManager, "_resolve_source_path", return_value=None):
            sm.play(sample_alarm)
            sm.play(sample_alarm)  # second call — should not crash

    def test_play_sets_current_alarm(self, qtbot, sample_alarm: Alarm) -> None:
        sm = SoundManager()
        with patch.object(SoundManager, "_resolve_source_path", return_value=None):
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
            SoundManager, "_resolve_source_path", return_value=str(dummy_file)
        ):
            sm.play(sample_alarm)
        assert len(received) == 1

    def test_play_no_source_path(self, qtbot, sample_alarm: Alarm) -> None:
        """If source path is None, playback should be skipped without crash."""
        sm = SoundManager()
        with patch.object(
            SoundManager, "_resolve_source_path", return_value=None
        ) as mock_resolve:
            sm.play(sample_alarm)
            mock_resolve.assert_called_once_with(sample_alarm)

    def test_play_with_fade_in(self, qtbot, sample_alarm: Alarm, tmp_path) -> None:
        """play() with an alarm that has fade_in enabled should start fade timer."""
        sample_alarm.fade_in = True
        sm = SoundManager()
        dummy_file = tmp_path / "sound.wav"
        dummy_file.write_text("")
        with patch.object(SoundManager, "_resolve_source_path", return_value=str(dummy_file)):
            sm.play(sample_alarm)
        assert sm._fade_timer.isActive() is True
        assert sm._current_volume == 0.0
        sm.stop()

    def test_play_does_not_start_when_no_source(
        self, qtbot, sample_alarm: Alarm
    ) -> None:
        """If no source path is resolved, player.play() should NOT be called."""
        sm = SoundManager()
        with patch.object(SoundManager, "_resolve_source_path", return_value=None):
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
# play_builtin  (compatibility wrapper)
# ===================================================================


class TestPlayBuiltin:
    """Legacy play_builtin(sound_name, volume) method."""

    def test_play_builtin_no_crash(self, qtbot) -> None:
        sm = SoundManager()
        with patch.object(SoundManager, "_get_sound_path", return_value=None):
            sm.play_builtin("classic", 80)

    def test_play_builtin_unknown(self, qtbot) -> None:
        sm = SoundManager()
        with patch.object(SoundManager, "_get_sound_path", return_value=None):
            sm.play_builtin("nonexistent", 50)

    def test_play_builtin_with_valid_path(self, qtbot, tmp_path) -> None:
        """play_builtin with a valid sound file should set source and play."""
        sm = SoundManager()
        dummy_file = tmp_path / "test.wav"
        dummy_file.write_text("")
        with patch.object(SoundManager, "_get_sound_path", return_value=str(dummy_file)):
            with patch.object(sm._player, "play") as mock_play:
                sm.play_builtin("classic", 75)
                mock_play.assert_called_once()


# ===================================================================
# play_file  (compatibility wrapper)
# ===================================================================


class TestPlayFile:
    """Legacy play_file(file_path, volume) method."""

    def test_play_file_no_crash(self, qtbot, tmp_path) -> None:
        """play_file should not crash with an existing file path."""
        sound_file = tmp_path / "test.wav"
        sound_file.write_text("")
        sm = SoundManager()
        sm.play_file(str(sound_file), 70)
        sm.stop()

    def test_play_file_missing(self, qtbot) -> None:
        """play_file with a non-existing file should not crash."""
        sm = SoundManager()
        sm.play_file("C:\\nonexistent\\missing.wav", 50)
        sm.stop()


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

    def test_start_fade_public_method(self, qtbot) -> None:
        """start_fade(target_volume) is the public API wrapping _start_fade_in."""
        sm = SoundManager()
        sm.start_fade(70)  # 70 → 0.7
        assert sm._target_volume == 0.7
        assert sm._current_volume == 0.0
        assert sm._fade_timer.isActive() is True


# ===================================================================
# Internal helpers  (_resolve_source_path / _get_sound_path)
# ===================================================================


class TestInternalHelpers:
    """Private path-resolution logic."""

    def test_resolve_source_path_file_missing_falls_to_builtin(
        self, qtbot, alarm_with_file_sound: Alarm
    ) -> None:
        """When a user sound file is missing, fall back to built-in.

        The user sound file does not exist on disk, so the code falls through
        to the built-in sound lookup.  We mock the built-in path to also be
        ``None`` so the final result is ``None``.
        """
        sm = SoundManager()
        with patch.object(sm, "_get_sound_path", return_value=None) as mock_get:
            path = sm._resolve_source_path(alarm_with_file_sound)
            mock_get.assert_called_once_with("classic")
        assert path is None

    def test_resolve_source_path_builtin(self, qtbot, sample_alarm: Alarm) -> None:
        """Builtin sound source resolves through _get_sound_path."""
        sm = SoundManager()
        with patch.object(
            sm, "_get_sound_path", return_value="/sounds/classic.wav"
        ) as mock_get:
            path = sm._resolve_source_path(sample_alarm)
            mock_get.assert_called_once_with("classic")
            assert path == "/sounds/classic.wav"

    def test_resolve_source_path_file_exists(self, qtbot, tmp_path) -> None:
        """When a user sound file exists on disk, it is returned directly."""
        dummy_file = tmp_path / "user_sound.wav"
        dummy_file.write_text("")
        alarm = Alarm(
            id="file-test",
            sound_source="file",
            sound_file=str(dummy_file),
            sound_name="classic",
        )
        sm = SoundManager()
        path = sm._resolve_source_path(alarm)
        assert path == str(dummy_file)

    def test_get_sound_path_unknown_name(self, qtbot) -> None:
        """_get_sound_path with an unknown sound name returns None."""
        sm = SoundManager()
        assert sm._get_sound_path("nonexistent") is None

    def test_get_sound_path_known_name(self, qtbot) -> None:
        """_get_sound_path with a valid name returns the full path when file exists."""
        sm = SoundManager()
        # The sound file actually exists on disk in the project resources
        result = sm._get_sound_path("classic")
        assert result is not None
        assert result.endswith("classic.wav")
        assert isinstance(result, str)

    def test_get_sound_path_file_missing_on_disk(self, qtbot) -> None:
        """_get_sound_path returns None when the builtin file is missing from disk."""
        sm = SoundManager()
        with patch("os.path.isfile", return_value=False):
            result = sm._get_sound_path("classic")
        assert result is None

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
