"""Tests for environment.py — .env permission checks (F-05)."""

import os
import stat
import logging
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


def _reset_environment_module():
    """Force-reimport environment module so the permission check reruns."""
    import sys
    for name in list(sys.modules):
        if name == "environment":
            del sys.modules[name]
    import environment
    environment._PERMISSIONS_CHECKED = False
    return environment


def _patch_env_path(MockPath, real_file):
    """Configure MockPath so Path(__file__).parent / '.env' returns a mock with real stat."""
    mock_env_path = MagicMock()
    mock_env_path.exists.return_value = True
    mock_env_path.stat.return_value = real_file.stat()
    # Path(__file__) returns MockPath.return_value
    # .parent returns MockPath.return_value.parent
    # / ".env" calls MockPath.return_value.parent.__truediv__(".env")
    MockPath.return_value.parent.__truediv__.return_value = mock_env_path


class TestWorldReadableWarning:
    def test_warns_when_file_world_readable(self, tmp_path, caplog):
        """If .env is 644, a 'world-readable' warning should be logged."""
        env_file = tmp_path / ".env"
        env_file.write_text("KEY=val\n")
        env_file.chmod(0o644)

        env_mod = _reset_environment_module()

        with patch("environment.Path") as MockPath, \
             caplog.at_level(logging.WARNING, logger="environment"):
            _patch_env_path(MockPath, env_file)
            env_mod._check_env_permissions()

        assert any("world-readable" in r.message for r in caplog.records)


class TestWorldWritableWarning:
    def test_warns_when_file_world_writable(self, tmp_path, caplog):
        """If .env is 666, a 'world-writable' warning should fire."""
        env_file = tmp_path / ".env"
        env_file.write_text("KEY=val\n")
        env_file.chmod(0o666)

        env_mod = _reset_environment_module()

        with patch("environment.Path") as MockPath, \
             caplog.at_level(logging.WARNING, logger="environment"):
            _patch_env_path(MockPath, env_file)
            env_mod._check_env_permissions()

        assert any("world-writable" in r.message for r in caplog.records)


class TestRestrictedPermissions:
    def test_no_warning_when_restricted(self, tmp_path, caplog):
        """If .env is 600, no warning should appear."""
        env_file = tmp_path / ".env"
        env_file.write_text("KEY=val\n")
        env_file.chmod(0o600)

        env_mod = _reset_environment_module()

        with patch("environment.Path") as MockPath, \
             caplog.at_level(logging.WARNING, logger="environment"):
            _patch_env_path(MockPath, env_file)
            caplog.clear()
            env_mod._check_env_permissions()

        env_warnings = [
            r for r in caplog.records
            if r.levelno >= logging.WARNING and r.name == "environment"
        ]
        assert len(env_warnings) == 0


class TestMissingEnv:
    def test_no_crash_when_missing(self):
        """If .env doesn't exist, the check completes without error."""
        env_mod = _reset_environment_module()

        mock_env_path = MagicMock()
        mock_env_path.exists.return_value = False

        with patch("environment.Path") as MockPath:
            MockPath.return_value.parent.__truediv__.return_value = mock_env_path
            env_mod._check_env_permissions()  # should not raise


class TestRunsOnce:
    def test_check_only_runs_once(self, tmp_path, caplog):
        """The permission check should only execute on the first call."""
        env_file = tmp_path / ".env"
        env_file.write_text("KEY=val\n")
        env_file.chmod(0o644)

        env_mod = _reset_environment_module()

        with patch("environment.Path") as MockPath, \
             caplog.at_level(logging.WARNING, logger="environment"):
            _patch_env_path(MockPath, env_file)
            caplog.clear()

            env_mod._check_env_permissions()
            count_first = len(caplog.records)

            env_mod._check_env_permissions()
            count_second = len(caplog.records)

        assert count_second == count_first  # no new warnings on second call
