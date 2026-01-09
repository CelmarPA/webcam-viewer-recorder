# utils/settings_manager.py

from __future__ import annotations

import json
import platform
import os
from pathlib import Path
from typing import Any, Optional

from utils.devices import detect_cameras, detect_microphones, save_devices


class SettingsManager:
    """
    Handles persistence of application data.

    - .webcam_recorder/settings.json : User preferences
    - .webcam_recorder/devices.json  : Hardware cache (cameras, microphones)

    The devices cache is generated ONLY if missing or empty.
    """

    def __init__(self) -> None:
        """
        Initialize settings and devices cache directories and load persisted data.
        """
        # =================================================
        # User data folder (single source of truth)
        # =================================================
        if platform.system() == "Windows":
            self.base_dir: Path = Path(os.getenv("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "WebcamRecorder"
        elif platform.system() == "Darwin":
            self.base_dir: Path = Path.home() / "Library/Application Support/WebcamRecorder"
        else:
            self.base_dir: Path = Path.home() / ".webcam_recorder"

        self.base_dir.mkdir(parents=True, exist_ok=True)

        self.settings_file: Path = self.base_dir / "settings.json"
        self.devices_file: Path = self.base_dir / "devices.json"

        self._settings: dict[str, Any] = {}
        self._devices: dict[str, Any] = {}

        self._load_settings()
        self._load_or_create_devices_cache()

    # ================= SETTINGS =================

    def _load_settings(self) -> None:
        if not self.settings_file.exists():
            return
        try:
            with open(self.settings_file, "r", encoding="utf-8") as file:
                self._settings = json.load(file)
        except Exception:
            self._settings = {}

    def save(self, data: Optional[dict[str, Any]] = None) -> None:
        self._save_settings(data)

    def _save_settings(self, data: Optional[dict[str, Any]] = None) -> None:
        if data:
            self._settings.update(data)
        try:
            with open(self.settings_file, "w", encoding="utf-8") as file:
                json.dump(self._settings, file, indent=4)
        except Exception:
            pass

    def get(self, key: str, default: Any = None) -> Any:
        return self._settings.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._settings[key] = value
        self.save()

    # ================= DEVICES CACHE =================

    def _load_or_create_devices_cache(self) -> None:
        """
        Load devices.json if it exists and update missing devices.

        If cameras or microphones are missing, detect immediately.
        Afterwards, background update will catch new devices.
        """
        self._devices = {"cameras": [], "microphones": []}

        if self.devices_file.exists():
            try:
                with open(self.devices_file, "r", encoding="utf-8") as file:
                    self._devices = json.load(file)
            except Exception:
                pass

        # 🔹 Detect devices immediately if any type is empty
        updated = False
        if not self._devices.get("cameras"):
            self._devices["cameras"] = detect_cameras()
            updated = True
        if not self._devices.get("microphones"):
            self._devices["microphones"] = detect_microphones()
            updated = True

        if updated:
            self._save_devices_cache()

        # 🔹 Continuous background updates (new cams/mics)
        from utils.devices import update_devices_background
        import threading
        threading.Thread(target=update_devices_background, daemon=True).start()


    def _save_devices_cache(self) -> None:
        """Saves the cache of the devices."""
        try:
            with open(self.devices_file, "w", encoding="utf-8") as file:
                json.dump(self._devices, file, indent=4)
        except Exception:
            pass

    def get_devices_cache(self) -> dict[str, Any]:
        """Load's devices cache."""
        return self._devices
