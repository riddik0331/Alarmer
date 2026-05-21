"""BudilnikApp — the top-level orchestrator (Application Controller).

Initialises all layers (Model, View, Controller), wires them together
via Qt signals/slots, loads the dark theme, and runs the event loop.
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Any

from PySide6.QtCore import QTimer
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QApplication

from src.controllers.alarm_controller import AlarmController
from src.controllers.tray_controller import TrayController
from src.models.alarm_manager import AlarmManager
from src.models.sound_manager import SoundManager
from src.utils.constants import APP_NAME, ORGANIZATION
from src.utils.storage import Storage
from src.views.main_window import MainWindow
from src.views.tray_manager import TrayManager

logger = logging.getLogger(__name__)


class BudilnikApp:
    """Orchestrates the entire application lifecycle.

    Creates the model, view, and controller layers, connects signals,
    loads the QSS theme, and runs the Qt event loop.
    """

    def __init__(self, argv: list[str]) -> None:
        self._argv = argv

        # --- Model layer ---
        self.storage = Storage()
        self.sound_manager = SoundManager()
        self.alarm_manager = AlarmManager(self.storage)

        # --- View layer ---
        self.main_window = MainWindow()
        self.tray_manager = TrayManager()

        # --- Controller layer ---
        self.alarm_controller = AlarmController(
            alarm_manager=self.alarm_manager,
            sound_manager=self.sound_manager,
        )
        self.tray_controller = TrayController(
            main_window=self.main_window,
            quit_callback=self.quit_application,
        )

    def _on_about_to_quit(self) -> None:
        """Ensure alarms are saved when the application quits."""
        self.alarm_manager.save()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self) -> int:
        """Initialise everything and enter the Qt event loop.

        Returns:
            The exit code returned to the operating system.
        """
        self._init_storage()
        self._load_theme()
        self._wire_signals()
        self._refresh_from_model()

        # Save alarms on graceful shutdown
        QApplication.instance().aboutToQuit.connect(self._on_about_to_quit)  # type: ignore

        self.main_window.show()
        logger.info("Application started.")

        return QApplication.exec()

    def show_window(self) -> None:
        """Show, raise, and activate the main window."""
        self.main_window.show()
        self.main_window.raise_()
        self.main_window.activateWindow()

    def quit_application(self) -> None:
        """Cleanly shut down the application."""
        logger.info("Shutting down...")
        self.sound_manager.stop()
        self.alarm_manager.save()
        QApplication.quit()

    # ------------------------------------------------------------------
    # Internal initialisation
    # ------------------------------------------------------------------

    def _init_storage(self) -> None:
        """Ensure required directories exist."""
        self.storage.ensure_dirs()

    def _load_theme(self) -> None:
        """Read the QSS theme file and apply it to the application."""
        theme_path = self.storage.get_resource_path("styles/theme.qss")
        if os.path.isfile(theme_path):
            try:
                with open(theme_path, "r", encoding="utf-8") as f:
                    qss = f.read()
                QApplication.instance().setStyleSheet(qss)  # type: ignore[union-attr]
                logger.info("Theme loaded from %s", theme_path)
            except Exception as exc:
                logger.warning("Failed to load theme QSS: %s", exc)
        else:
            logger.info("No theme QSS found at %s — using default Fusion style.", theme_path)

    def _wire_signals(self) -> None:
        """Connect all cross-layer signals."""
        # Connect controller to view
        self.alarm_controller.connect_view(self.main_window)
        self.alarm_controller.connect_tray(self.tray_manager)
        self.tray_controller.connect_tray(self.tray_manager)

        # Tray signals → app-level handlers
        self.tray_manager.show_window_requested.connect(self.show_window)
        self.tray_manager.quit_requested.connect(self.quit_application)

    def _refresh_from_model(self) -> None:
        """Synchronise the main window and tray with the current model state."""
        alarms = self.alarm_manager.get_alarms()
        has_active = any(a.enabled for a in alarms)
        self.main_window.refresh_list(alarms)
        self.tray_manager.update_icon(has_active)

