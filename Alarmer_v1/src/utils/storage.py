"""Filesystem abstraction — paths, directory creation, atomic JSON I/O.

Handles the distinction between development mode (files next to ``main.py``)
and a PyInstaller-bundled executable (data in ``%APPDATA%/Budilnik/``).
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from typing import Any


def _is_frozen() -> bool:
    """Return ``True`` when running inside a PyInstaller bundle."""
    return getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS")


class Storage:
    """Utility for file-system operations (paths, atomic saves, resource resolution)."""

    # ------------------------------------------------------------------
    # Path resolution
    # ------------------------------------------------------------------

    @staticmethod
    def get_data_path() -> str:
        """Return the directory where application data (``alarms.json``) lives.

        In development (unfrozen) this is the project root (next to ``main.py``).
        In a frozen PyInstaller build this is ``%APPDATA%/Budilnik/``.
        """
        if _is_frozen():
            appdata = os.path.expandvars("%APPDATA%")
            path = os.path.join(appdata, "Budilnik")
        else:
            # Project root: two levels up from this file (src/utils/storage.py)
            path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        return path

    @staticmethod
    def get_alarms_file() -> str:
        """Return the full path to the ``alarms.json`` file."""
        return os.path.join(Storage.get_data_path(), "alarms.json")

    @staticmethod
    def get_sounds_dir() -> str:
        """Return the directory containing built-in sound files.

        Respects PyInstaller's ``sys._MEIPASS`` when frozen.
        """
        if _is_frozen():
            base = sys._MEIPASS  # type: ignore[attr-defined]
        else:
            base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        return os.path.join(base, "src", "resources", "sounds")

    @staticmethod
    def get_resource_path(relative: str) -> str:
        """Return the absolute path of a resource file, accounting for PyInstaller.

        Args:
            relative: Relative path under the ``src/resources/`` tree,
                      e.g. ``"icons/bell.svg"`` or ``"styles/theme.qss"``.

        Returns:
            The absolute file-system path.
        """
        if _is_frozen():
            base = sys._MEIPASS  # type: ignore[attr-defined]
        else:
            base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        return os.path.join(base, "src", "resources", relative)

    # ------------------------------------------------------------------
    # Directory scaffolding
    # ------------------------------------------------------------------

    @staticmethod
    def ensure_dirs() -> None:
        """Create all required directories if they do not exist."""
        os.makedirs(Storage.get_data_path(), exist_ok=True)
        # Sound directory is bundled with the app, no need to create.

    # ------------------------------------------------------------------
    # Atomic JSON write
    # ------------------------------------------------------------------

    @staticmethod
    def atomic_save(filepath: str, data: dict[str, Any]) -> None:
        """Atomically write a JSON-serialisable dictionary to *filepath* as JSON.

        The write goes through a temporary file next to the target, then
        an atomic rename (``os.replace``) is performed.  This prevents
        data corruption if the process crashes mid-write.

        Args:
            filepath: Destination JSON file.
            data:     Serializable dictionary (e.g. ``{"version": 1, "alarms": [...]}``).
        """
        dir_name = os.path.dirname(filepath)
        os.makedirs(dir_name, exist_ok=True)

        # Write to a temporary file first
        fd, tmp_path = tempfile.mkstemp(
            suffix=".tmp",
            prefix=".alarms_",
            dir=dir_name,
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())  # force flush to disk
            # Atomic rename (NTFS / POSIX)
            os.replace(tmp_path, filepath)
        except Exception:
            # Clean up the temp file on failure
            try:
                os.remove(tmp_path)
            except OSError:
                pass
            raise

    # ------------------------------------------------------------------
    # Safe JSON read
    # ------------------------------------------------------------------

    @staticmethod
    def read_json(filepath: str) -> dict[str, Any]:
        """Read and parse a JSON file.

        Args:
            filepath: Path to the JSON file.

        Returns:
            Parsed content (usually a dict with ``"version"`` and ``"alarms"`` keys).

        Raises:
            FileNotFoundError: If the file does not exist.
            json.JSONDecodeError: If the file contains invalid JSON.
        """
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)  # type: ignore[no-any-return]
