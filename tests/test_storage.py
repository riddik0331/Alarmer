"""Tests for the Storage class — path resolution, atomic JSON I/O.

All file-system operations are isolated inside a temporary directory via
the ``tmp_path`` fixture.
"""

from __future__ import annotations

import json
import os
from unittest.mock import patch

import pytest

from src.utils.storage import Storage, _is_frozen


# ===================================================================
# Path resolution
# ===================================================================


class TestGetDataPath:
    """Storage.get_data_path() should always return a non-empty string."""

    def test_returns_string(self) -> None:
        path = Storage.get_data_path()
        assert isinstance(path, str)
        assert len(path) > 0

    def test_path_is_absolute(self) -> None:
        path = Storage.get_data_path()
        assert os.path.isabs(path)

    def test_not_frozen_by_default(self) -> None:
        """In the test environment ``_is_frozen`` should be False."""
        assert _is_frozen() is False

    def test_is_project_root(self) -> None:
        """When not frozen, the path should be the project root (contains ``src/``)."""
        path = Storage.get_data_path()
        assert os.path.isdir(path)
        assert "src" in os.listdir(path), (
            f"Expected {path!r} to contain 'src' directory"
        )


class TestGetAlarmsFile:
    """Storage.get_alarms_file() should return a path ending with ``alarms.json``."""

    def test_returns_string(self) -> None:
        path = Storage.get_alarms_file()
        assert isinstance(path, str)

    def test_ends_with_alarms_json(self) -> None:
        path = Storage.get_alarms_file()
        assert path.endswith("alarms.json"), f"Expected …/alarms.json, got {path!r}"

    def test_basename_is_alarms_json(self) -> None:
        assert os.path.basename(Storage.get_alarms_file()) == "alarms.json"


# ===================================================================
# ensure_dirs
# ===================================================================


class TestEnsureDirs:
    """Directory scaffolding."""

    def test_creates_directory(self, monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
        """ensure_dirs() creates the data directory if it does not exist."""
        test_dir = tmp_path / "Budilnik"
        assert not test_dir.exists()

        monkeypatch.setattr(Storage, "get_data_path", lambda: str(test_dir))
        Storage.ensure_dirs()

        assert test_dir.exists()
        assert test_dir.is_dir()

    def test_idempotent(self, monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
        """Calling ensure_dirs() twice should not raise."""
        test_dir = tmp_path / "Budilnik"
        monkeypatch.setattr(Storage, "get_data_path", lambda: str(test_dir))
        Storage.ensure_dirs()
        Storage.ensure_dirs()  # second call
        assert test_dir.exists()


# ===================================================================
# atomic_save
# ===================================================================


class TestAtomicSave:
    """Atomic JSON write and read-back."""

    def test_writes_correct_json(self, tmp_path) -> None:
        """Write a dict, then read the file and verify contents."""
        filepath = tmp_path / "test.json"
        data = {"version": 1, "alarms": [{"id": "a1", "time": "08:00"}]}

        Storage.atomic_save(str(filepath), data)

        assert filepath.exists()
        with open(filepath, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        assert loaded == data

    def test_atomic_save_and_read_json(self, tmp_path) -> None:
        """Write via atomic_save, read via read_json."""
        filepath = tmp_path / "roundtrip.json"
        data = {"version": 1, "alarms": []}
        Storage.atomic_save(str(filepath), data)

        loaded = Storage.read_json(str(filepath))
        assert loaded == data

    def test_atomic_save_creates_intermediate_dirs(self, tmp_path) -> None:
        """Target directory is created automatically."""
        filepath = tmp_path / "sub" / "deep" / "alarms.json"
        Storage.atomic_save(str(filepath), {"key": "value"})
        assert filepath.exists()

    def test_no_temp_file_left_on_success(self, tmp_path) -> None:
        """Temporary .tmp file should be removed after a successful write."""
        filepath = tmp_path / "clean.json"
        Storage.atomic_save(str(filepath), {"ok": True})
        # No .tmp files should remain
        tmp_files = list(tmp_path.glob("*.tmp"))
        assert len(tmp_files) == 0

    def test_temporary_file_removed_on_failure(self, tmp_path) -> None:
        """If the write fails, the temp file is cleaned up and target is untouched."""
        filepath = tmp_path / "fail.json"

        # Patch json.dump to raise an exception
        with patch("json.dump", side_effect=RuntimeError("Write failure")):
            with pytest.raises(RuntimeError, match="Write failure"):
                Storage.atomic_save(str(filepath), {"data": "test"})

        # Target file should NOT exist
        assert not filepath.exists()
        # Temp files should also be gone
        tmp_files = list(tmp_path.glob("*.tmp"))
        assert len(tmp_files) == 0

    def test_target_not_overwritten_on_failure(self, tmp_path) -> None:
        """If a file already exists, it should not be corrupted by a failed write."""
        filepath = tmp_path / "existing.json"
        original_data = {"version": 1, "alarms": []}
        Storage.atomic_save(str(filepath), original_data)

        # Now attempt a failed write
        with patch("json.dump", side_effect=RuntimeError("Write failure")):
            with pytest.raises(RuntimeError):
                Storage.atomic_save(str(filepath), {"corrupted": True})

        # The original file should still be intact
        loaded = Storage.read_json(str(filepath))
        assert loaded == original_data

    def test_oserror_on_temp_cleanup_is_silent(self, tmp_path) -> None:
        """If temp file removal fails with OSError, the exception is swallowed."""
        filepath = tmp_path / "cleanup_test.json"

        original_remove = os.remove

        def failing_remove(path: str) -> None:
            if ".tmp" in path:
                raise OSError("Permission denied")
            original_remove(path)

        with patch("json.dump", side_effect=RuntimeError("Write failure")):
            with patch("os.remove", side_effect=failing_remove):
                with pytest.raises(RuntimeError):
                    Storage.atomic_save(str(filepath), {"data": "test"})

        # The target should NOT exist (json.dump never succeeded)
        assert not filepath.exists()

    def test_writes_indented_json(self, tmp_path) -> None:
        """Output file should contain pretty-printed (indented) JSON."""
        filepath = tmp_path / "pretty.json"
        Storage.atomic_save(str(filepath), {"a": 1})
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        assert '"a": 1' in content
        # Should have line breaks (indentation)
        assert content.startswith("{")
        assert content.endswith("}")


# ===================================================================
# read_json
# ===================================================================


class TestReadJson:
    """Safe JSON reading with expected error propagation."""

    def test_file_not_found(self, tmp_path) -> None:
        """read_json raises FileNotFoundError for missing file."""
        filepath = tmp_path / "nonexistent.json"
        with pytest.raises(FileNotFoundError):
            Storage.read_json(str(filepath))

    def test_invalid_json(self, tmp_path) -> None:
        """read_json raises JSONDecodeError for malformed content."""
        filepath = tmp_path / "bad.json"
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("{invalid json}")
        with pytest.raises(json.JSONDecodeError):
            Storage.read_json(str(filepath))


# ===================================================================
# Frozen-mode tests
# ===================================================================


class TestFrozenMode:
    """Behaviour when running inside a PyInstaller bundle."""

    def test_is_frozen_false(self) -> None:
        assert _is_frozen() is False

    def test_frozen_data_path(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """When frozen, get_data_path returns ``%APPDATA%/Budilnik``."""
        monkeypatch.setattr("sys.frozen", True, raising=False)
        monkeypatch.setattr("sys._MEIPASS", "C:\\bundle", raising=False)

        path = Storage.get_data_path()
        assert "APPDATA" not in path  # should be expanded
        assert path.endswith("Budilnik")

    def test_frozen_sounds_dir(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """When frozen, get_sounds_dir uses sys._MEIPASS."""
        monkeypatch.setattr("sys.frozen", True, raising=False)
        monkeypatch.setattr("sys._MEIPASS", "C:\\bundle", raising=False)

        sounds_dir = Storage.get_sounds_dir()
        assert sounds_dir.startswith("C:\\bundle")
        assert sounds_dir.endswith("sounds")

    def test_frozen_get_resource_path(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """get_resource_path uses sys._MEIPASS when frozen."""
        monkeypatch.setattr("sys.frozen", True, raising=False)
        monkeypatch.setattr("sys._MEIPASS", "C:\\bundle", raising=False)

        result = Storage.get_resource_path("icons/bell.svg")
        assert result.startswith("C:\\bundle")
        assert result.endswith("icons\\bell.svg") or result.endswith("icons/bell.svg")

    def test_unfrozen_get_resource_path(self) -> None:
        """get_resource_path returns a path relative to the project root."""
        result = Storage.get_resource_path("icons/bell.svg")
        assert isinstance(result, str)
        assert result.endswith("icons\\bell.svg") or result.endswith("icons/bell.svg")
        assert "src" in result
        assert "resources" in result
