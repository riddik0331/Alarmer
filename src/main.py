"""Application entry point.

Creates the QApplication, loads the dark QSS theme, and launches
the BudilnikApp orchestrator.
"""

from __future__ import annotations

import logging
import os
import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

# Ensure the project root is on sys.path (works when run as python src/main.py)
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from src.app import BudilnikApp


def main() -> None:
    """Initialise the application and start the event loop."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    app = QApplication(sys.argv)
    app.setApplicationName("Budilnik")
    app.setOrganizationName("Budilnik")
    # Do NOT quit when the last window is closed � stay in the system tray
    app.setQuitOnLastWindowClosed(False)

    # High-DPI support (Qt 6 enables it by default, but be explicit)
    app.setStyle("Fusion")

    budilnik = BudilnikApp(sys.argv)
    exit_code = budilnik.run()

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
