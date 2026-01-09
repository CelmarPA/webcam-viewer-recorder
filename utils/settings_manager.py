# utils/settings_manager.py

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from utils.devices import get_cameras, get_microphones


class SettingsManager:
    """
    Handles persistence of application data.

    - settings.json : User preferences
    - devices.json  : Hardware cache (cameras, resolutions, microphones)

    The devices cache is generated ONLY if missing.
    """

    def __init__(self) -> None:
        """
        Initialize settings and devices cache directories and load persisted data.
        """
        self.base_dir: Path = Path.home() / ".webcam_recorder"
        self.base_dir.mkdir(exist_ok=True)

        self.settings_file: Path = self.base_dir / "settings.json"
        self.devices_file: Path = self.base_dir / "devices.json"

        self._settings: dict[str, Any] = {}
        self._devices: dict[str, Any] = {}

        self._load_settings()
        self._load_or_create_devices_cache()

    # ==================================================
    # SETTINGS (user preferences)
    # ==================================================

    def _load_settings(self) -> None:
        """
        Load user settings from settings.json if it exists.
        """
        if not self.settings_file.exists():
            return

        try:
            with open(self.settings_file, "r", encoding="utf-8") as file:
                self._settings = json.load(file)
        except Exception:
            self._settings = {}

    def save(self, data: Optional[dict[str, Any]] = None) -> None:
        """
        Public API for saving user settings.

        AppWindow MUST call this method.

        :param data: Optional dictionary with settings to update
        :type data: Optional[dict[str, Any]]
        """
        self._save_settings(data)

    def _save_settings(self, data: Optional[dict[str, Any]] = None) -> None:
        """
        Persist user settings to settings.json.

        :param data: Optional dictionary with settings to update
        :type data: Optional[dict[str, Any]]
        """
        if data:
            self._settings.update(data)

        try:
            with open(self.settings_file, "w", encoding="utf-8") as file:
                json.dump(self._settings, file, indent=4)
        except Exception:
            pass

    def get(self, key: str, default: Any = None) -> Any:
        """
        Retrieve a setting value.

        :param key: Setting key
        :type key: str
        :param default: Default value if key does not exist
        :type default: Any
        :return: Stored value or default
        :rtype: Any
        """
        return self._settings.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """
        Set a setting value and persist it.

        :param key: Setting key
        :type key: str
        :param value: Value to store
        :type value: Any
        """
        self._settings[key] = value
        self.save()

    # ==================================================
    # DEVICES CACHE (hardware)
    # ==================================================

    def _load_or_create_devices_cache(self) -> None:
        """
        Load devices.json if it exists.

        If missing or invalid, generate it using get_cameras()
        and get_microphones().
        """
        if self.devices_file.exists():
            try:
                with open(self.devices_file, "r", encoding="utf-8") as file:
                    self._devices = json.load(file)
                return
            except Exception:
                pass

        cameras = get_cameras()
        microphones = get_microphones()

        self._devices = {
            "cameras": cameras,
            "microphones": microphones,
        }

        self._save_devices_cache()

    def _save_devices_cache(self) -> None:
        """
        Persist devices cache to devices.json.

        This method is called ONLY during initial cache generation.
        """
        try:
            with open(self.devices_file, "w", encoding="utf-8") as file:
                json.dump(self._devices, file, indent=4)
        except Exception:
            pass

    def get_devices_cache(self) -> dict[str, Any]:
        """
        Return the loaded devices cache.

        :return: Devices cache dictionary
        :rtype: dict[str, Any]
        """
        return self._devices
