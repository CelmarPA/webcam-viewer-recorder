from pathlib import Path
import sys


def resource_path(relative_path: str) -> Path:
    """
    Resolve resource paths for both development and PyInstaller builds.

    :param relative_path: Relative path inside the project
    :return: Absolute resolved Path
    """
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / relative_path
    return Path(relative_path).resolve()
