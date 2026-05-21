"""System tray controller — handles tray icon actions and menu events."""

import logging
from typing import Callable

from PySide6.QtCore import QObject

from src.views.main_window import MainWindow
from src.views.tray_manager import TrayManager

logger = logging.getLogger(__name__)


class TrayController(QObject):
    """Controller for system tray icon actions.

    Processes user interactions with the system tray icon
    (show window, quit application) and delegates them to
    the appropriate application-level handlers.
    """

    def __init__(
        self,
        main_window: MainWindow,
        quit_callback: Callable[[], None],
    ) -> None:
        """Initialize the tray controller.

        Args:
            main_window: The main application window to show/focus.
            quit_callback: Callback invoked when the user requests
                application exit (e.g. ``QApplication.quit``).
        """
        super().__init__()
        self._main_window: MainWindow = main_window
        self._quit_callback: Callable[[], None] = quit_callback

    def connect_tray(self, tray_manager: TrayManager) -> None:
        """Connect tray manager signals to controller slots.

        Subscribes to ``show_requested`` and ``quit_requested``
        signals emitted by the TrayManager when the user interacts
        with the system tray context menu.

        Args:
            tray_manager: The system tray manager (view) instance.
        """
        tray_manager.show_requested.connect(self._on_show_window)
        tray_manager.quit_requested.connect(self._on_quit)
        logger.debug("Tray controller connected to tray manager")

    def _on_show_window(self) -> None:
        """Show and focus the main application window.

        Ensures the window is visible, brought to the front,
        and receives keyboard focus.
        """
        self._main_window.show()
        self._main_window.raise_()
        self._main_window.activateWindow()
        logger.debug("Main window shown and focused via tray")

    def _on_quit(self) -> None:
        """Exit the application.

        Invokes the quit callback provided at initialisation,
        which should perform cleanup (stop timers, save data)
        and call ``QApplication.quit()``.
        """
        logger.info("Quit requested from system tray")
        self._quit_callback()

