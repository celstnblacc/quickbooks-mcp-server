"""Environment variable loader with .env permission safety checks."""

import os
import sys
import stat
import logging
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

_PERMISSIONS_CHECKED = False


def _check_env_permissions():
    """Warn once if the .env file has overly permissive file modes."""
    global _PERMISSIONS_CHECKED
    if _PERMISSIONS_CHECKED:
        return
    _PERMISSIONS_CHECKED = True

    env_path = Path(__file__).parent / ".env"
    if not env_path.exists():
        return

    try:
        mode = env_path.stat().st_mode
        if mode & stat.S_IROTH:
            logger.warning(
                ".env file is world-readable — run: chmod 600 %s", env_path
            )
        if mode & stat.S_IWOTH:
            logger.warning(
                ".env file is world-writable — run: chmod 600 %s", env_path
            )
    except OSError as exc:
        logger.debug("Could not stat .env file: %s", exc)


class Environment:
    @staticmethod
    def get(__key, __default=None):
        _check_env_permissions()
        return os.getenv(__key, __default)
