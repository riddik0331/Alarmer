"""SoundManager — audio playback, built-in / file-based sounds, volume
control, and fade-in support.

Uses ``QMediaPlayer`` + ``QAudioOutput`` for cross-format playback (MP3 / WAV).
"""

from __future__ import annotations

import logging
import os
from typing import Optional

from PySide6.QtCore import QObject, QTimer, Signal, QUrl
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer

from src.models.alarm_model import Alarm
from src.utils.constants import BUILTIN_SOUNDS, FADE_INTERVAL_MS, FADE_IN_DURATION
from src.utils.storage import Storage

logger = logging.getLogger(__name__)


class SoundManager(QObject):
    """Manages playback of alarm sounds: play, stop, preview, fade-in.

    Signals:
        sound_started: Emitted when a new sound begins playing.
        sound_stopped: Emitted when playback stops (manually or naturally).
    """

    # ------------------------------------------------------------------
    # Signals
    # ------------------------------------------------------------------
    sound_started = Signal()
    sound_stopped = Signal()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)

        self._player = QMediaPlayer(self)
        self._audio_output = QAudioOutput(self)
        self._player.setAudioOutput(self._audio_output)

        self._current_alarm: Optional[Alarm] = None
        self._fade_timer = QTimer(self)
        self._fade_timer.timeout.connect(self._fade_tick)
        self._current_volume: float = 1.0  # 0.0 … 1.0
        self._target_volume: float = 1.0
        self._fade_step: float = 0.0

        # Loop the media when it finishes
        self._player.mediaStatusChanged.connect(self._on_media_status_changed)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def play(self, alarm: Alarm) -> None:
        """Start playing the sound configured in *alarm*.

        If the alarm has ``fade_in`` enabled, a fade-in sequence is started;
        otherwise the volume jumps directly to the user's setting.
        """
        self.stop()
        self._current_alarm = alarm

        source_path = self._resolve_source_path(alarm)
        if not source_path:
            logger.error("No playable sound source for alarm %s", alarm.id)
            return

        self._player.setSource(QUrl.fromLocalFile(source_path))
        self._player.setLoops(QMediaPlayer.Infinite)

        target_vol = alarm.volume / 100.0
        if alarm.fade_in:
            self._start_fade_in(target_vol)
        else:
            self._set_volume(target_vol)

        self._player.play()
        self.sound_started.emit()
        logger.info("Playing sound: %s", source_path)

    def stop(self) -> None:
        """Stop playback and cancel any active fade-in."""
        self._fade_timer.stop()
        self._player.stop()
        self._current_alarm = None
        self.sound_stopped.emit()

    def preview_sound(self, sound_name: str) -> None:
        """Play a built-in sound once (non-looping) for preview purposes.

        The volume is set to 50 % to avoid startling the user.
        """
        self.stop_preview()
        path = self._get_sound_path(sound_name)
        if not path:
            logger.warning("Preview sound not found: %s", sound_name)
            return

        self._player.setSource(QUrl.fromLocalFile(path))
        self._player.setLoops(QMediaPlayer.Once)
        self._set_volume(0.5)
        self._player.play()
        self.sound_started.emit()

    def stop_preview(self) -> None:
        """Stop any ongoing preview playback."""
        self._fade_timer.stop()
        self._player.stop()
        self.sound_stopped.emit()

    # ------------------------------------------------------------------
    # Compatibility public methods (used by existing controllers)
    # ------------------------------------------------------------------

    def play_builtin(self, sound_name: str, volume: int) -> None:
        """Play a built-in sound at the specified volume (compatibility wrapper).

        Args:
            sound_name: Key into ``BUILTIN_SOUNDS`` (e.g. ``"classic"``).
            volume:     Volume level 0–100.
        """
        path = self._get_sound_path(sound_name)
        if not path:
            logger.warning("Built-in sound not found: %s", sound_name)
            return
        self._player.setSource(QUrl.fromLocalFile(path))
        self._player.setLoops(QMediaPlayer.Infinite)
        self._set_volume(volume / 100.0)
        self._player.play()
        self.sound_started.emit()

    def play_file(self, file_path: str, volume: int) -> None:
        """Play a user-supplied sound file at the specified volume.

        Args:
            file_path: Absolute path to a sound file.
            volume:    Volume level 0–100.
        """
        self._player.setSource(QUrl.fromLocalFile(file_path))
        self._player.setLoops(QMediaPlayer.Infinite)
        self._set_volume(volume / 100.0)
        self._player.play()
        self.sound_started.emit()

    def start_fade(self, target_volume: int) -> None:
        """Start a fade-in sequence toward *target_volume* over 30 seconds.

        Args:
            target_volume: Target volume level 0–100.
        """
        self._start_fade_in(target_volume / 100.0)

    # ------------------------------------------------------------------
    # Volume
    # ------------------------------------------------------------------

    def _set_volume(self, volume: float) -> None:
        """Set the audio output volume (0.0 … 1.0)."""
        self._current_volume = max(0.0, min(1.0, volume))
        self._audio_output.setVolume(self._current_volume)

    def _start_fade_in(self, target_volume: float) -> None:
        """Begin a fade-in sequence from 0 to *target_volume* over 30 seconds."""
        self._target_volume = max(0.0, min(1.0, target_volume))
        self._set_volume(0.0)

        steps = (FADE_IN_DURATION * 1000) / FADE_INTERVAL_MS  # e.g. 150
        self._fade_step = self._target_volume / steps if steps > 0 else self._target_volume

        self._fade_timer.start(FADE_INTERVAL_MS)

    def _fade_tick(self) -> None:
        """Increment volume by one fade step; stop the timer when target is reached."""
        new_vol = self._current_volume + self._fade_step
        if new_vol >= self._target_volume:
            new_vol = self._target_volume
            self._fade_timer.stop()
        self._set_volume(new_vol)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_source_path(self, alarm: Alarm) -> Optional[str]:
        """Return the absolute path to the sound file for *alarm*."""
        if alarm.sound_source == "file" and alarm.sound_file:
            if os.path.isfile(alarm.sound_file):
                return alarm.sound_file
            logger.warning("User sound file missing: %s", alarm.sound_file)
            # Fall through to built-in

        return self._get_sound_path(alarm.sound_name)

    def _get_sound_path(self, sound_name: str) -> Optional[str]:
        """Return the full path of a built-in sound file, or ``None``."""
        if sound_name not in BUILTIN_SOUNDS:
            logger.warning("Unknown built-in sound: %s", sound_name)
            return None

        sounds_dir = Storage.get_sounds_dir()
        # Map the key to an actual file name
        file_map = {
            "alarm_1": "alarm_1.wav",
            "classic": "classic.wav",
            "gentle": "gentle.wav",
            "nature": "nature.wav",
            "energetic": "energetic.wav",
            "lounge": "lounge.wav",
        }
        filename = file_map.get(sound_name, f"{sound_name}.wav")
        path = os.path.join(sounds_dir, filename)
        if not os.path.isfile(path):
            logger.warning("Sound file not found on disk: %s", path)
            return None
        return path

    def _on_media_status_changed(self, status: QMediaPlayer.MediaStatus) -> None:
        """Restart playback when the media ends (infinite loop via status)."""
        if status == QMediaPlayer.MediaStatus.EndOfMedia and self._current_alarm is not None:
            self._player.play()

