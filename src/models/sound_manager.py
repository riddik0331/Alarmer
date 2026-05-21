"""SoundManager — audio playback, volume control, and fade-in support.

Always plays the built-in ``alarm_1.wav`` sound file.
Uses ``QMediaPlayer`` + ``QAudioOutput`` for cross-format playback.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

from PySide6.QtCore import QObject, QTimer, Signal, QUrl
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer

from src.models.alarm_model import Alarm
from src.utils.constants import FADE_INTERVAL_MS, FADE_IN_DURATION
from src.utils.storage import Storage

logger = logging.getLogger(__name__)

SOUND_FILE = "alarm_1.wav"


class SoundManager(QObject):
    """Manages playback of alarm sounds: play, stop, fade-in.

    Always plays the built-in ``alarm_1.wav``.  Volume and fade-in settings
    are read from the ``Alarm`` instance; the sound file itself is fixed.

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
        """Start playing the built-in alarm sound.

        If the alarm has ``fade_in`` enabled, a fade-in sequence is started;
        otherwise the volume jumps directly to the user's setting.

        Args:
            alarm: The alarm whose volume/fade-in settings to use.
        """
        self.stop()
        self._current_alarm = alarm

        source_path = self._get_sound_path()
        if not source_path:
            logger.error("Alarm sound file missing: alarm_1.wav")
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

    def _get_sound_path(self) -> Optional[str]:
        """Return the full path of the built-in alarm sound, or ``None``."""
        sounds_dir = Storage.get_sounds_dir()
        path = os.path.join(sounds_dir, SOUND_FILE)
        if not os.path.isfile(path):
            logger.warning("Sound file not found on disk: %s", path)
            return None
        return path

    def _on_media_status_changed(self, status: QMediaPlayer.MediaStatus) -> None:
        """Restart playback when the media ends (infinite loop via status)."""
        if status == QMediaPlayer.MediaStatus.EndOfMedia and self._current_alarm is not None:
            self._player.play()
